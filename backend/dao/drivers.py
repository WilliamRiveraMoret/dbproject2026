from backend.config.dbconfig import PG_DB_CONFIG, POOL_CONFIG, SCHEMA
from psycopg2.pool import SimpleConnectionPool
from psycopg2.extras import DictCursor
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import psycopg2


class DriverCreate(BaseModel):
    first_name: str
    last_name: str
    license_number: str
    hired_at: datetime


class DriverUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    license_number: Optional[str] = None
    hired_at: Optional[datetime] = None


class DriverResponse(BaseModel):
    driver_id: int
    first_name: str
    last_name: str
    license_number: str
    hired_at: datetime


class DriverDAO:
    def __init__(self):
        self.pool = SimpleConnectionPool(
            POOL_CONFIG["minconn"],
            POOL_CONFIG["maxconn"],
            **PG_DB_CONFIG,
        )

    def _license_exists(self, cursor, license_number: str, exclude_id: Optional[int] = None) -> bool:
        if exclude_id is None:
            cursor.execute(
                f"SELECT 1 FROM {SCHEMA}.driver WHERE license_number = %s",
                (license_number,),
            )
        else:
            cursor.execute(
                f"SELECT 1 FROM {SCHEMA}.driver WHERE license_number = %s AND driver_id <> %s",
                (license_number, exclude_id),
            )
        return cursor.fetchone() is not None

    def create_driver(self, payload: DriverCreate) -> int:
        conn = self.pool.getconn()
        try:
            cursor = conn.cursor(cursor_factory=DictCursor)
            if self._license_exists(cursor, payload.license_number):
                cursor.close()
                raise ValueError("license_number")

            cursor.execute(
                f"""
                INSERT INTO {SCHEMA}.driver
                    (first_name, last_name, license_number, hired_at)
                VALUES (%s, %s, %s, %s)
                RETURNING driver_id
                """,
                (
                    payload.first_name.strip(),
                    payload.last_name.strip(),
                    payload.license_number.strip(),
                    payload.hired_at,
                ),
            )
            driver_id = cursor.fetchone()[0]
            conn.commit()
            cursor.close()
            return driver_id
        except Exception:
            conn.rollback()
            raise
        finally:
            self.pool.putconn(conn)

    def get_driver_by_id(self, driver_id: int) -> Optional[DriverResponse]:
        conn = self.pool.getconn()
        try:
            cursor = conn.cursor(cursor_factory=DictCursor)
            cursor.execute(
                f"""
                SELECT driver_id, first_name, last_name, license_number, hired_at
                FROM {SCHEMA}.driver
                WHERE driver_id = %s
                """,
                (driver_id,),
            )
            row = cursor.fetchone()
            cursor.close()
            return DriverResponse(**row) if row else None
        finally:
            self.pool.putconn(conn)

    def get_drivers(
        self,
        limit: int,
        offset: int,
        name: Optional[str] = None,
        license_number: Optional[str] = None,
    ) -> tuple[list[DriverResponse], int]:
        conn = self.pool.getconn()
        try:
            cursor = conn.cursor(cursor_factory=DictCursor)
            clauses, params = [], []

            if name:
                clauses.append("(first_name ILIKE %s OR last_name ILIKE %s)")
                params.extend([f"%{name}%", f"%{name}%"])
            if license_number:
                clauses.append("license_number ILIKE %s")
                params.append(f"%{license_number}%")

            where_sql = (" WHERE " + " AND ".join(clauses)) if clauses else ""

            cursor.execute(
                f"SELECT COUNT(*) FROM {SCHEMA}.driver {where_sql}",
                tuple(params),
            )
            count = cursor.fetchone()[0]

            cursor.execute(
                f"""
                SELECT driver_id, first_name, last_name, license_number, hired_at
                FROM {SCHEMA}.driver
                {where_sql}
                ORDER BY driver_id
                LIMIT %s OFFSET %s
                """,
                tuple(params) + (limit, offset),
            )
            items = [DriverResponse(**row) for row in cursor.fetchall()]
            cursor.close()
            return items, count
        finally:
            self.pool.putconn(conn)

    def update_driver(self, driver_id: int, payload: DriverUpdate) -> Optional[DriverResponse]:
        data = payload.model_dump(exclude_unset=True)
        if not data:
            raise ValueError("empty")

        conn = self.pool.getconn()
        try:
            cursor = conn.cursor(cursor_factory=DictCursor)
            cursor.execute(
                f"SELECT 1 FROM {SCHEMA}.driver WHERE driver_id = %s",
                (driver_id,),
            )
            if cursor.fetchone() is None:
                cursor.close()
                return None

            if "license_number" in data and self._license_exists(
                cursor, data["license_number"], exclude_id=driver_id
            ):
                cursor.close()
                raise ValueError("license_number")

            # Trim text fields
            for k in ("first_name", "last_name", "license_number"):
                if k in data and data[k] is not None:
                    data[k] = data[k].strip()

            set_sql = ", ".join(f"{k} = %({k})s" for k in data.keys())
            data["driver_id"] = driver_id

            cursor.execute(
                f"""
                UPDATE {SCHEMA}.driver
                SET {set_sql}
                WHERE driver_id = %(driver_id)s
                """,
                data,
            )
            conn.commit()

            cursor.execute(
                f"""
                SELECT driver_id, first_name, last_name, license_number, hired_at
                FROM {SCHEMA}.driver
                WHERE driver_id = %s
                """,
                (driver_id,),
            )
            row = cursor.fetchone()
            cursor.close()
            return DriverResponse(**row) if row else None
        except Exception:
            conn.rollback()
            raise
        finally:
            self.pool.putconn(conn)

    def delete_driver(self, driver_id: int) -> str:
        conn = self.pool.getconn()
        try:
            cursor = conn.cursor(cursor_factory=DictCursor)
            cursor.execute(
                f"SELECT 1 FROM {SCHEMA}.driver WHERE driver_id = %s",
                (driver_id,),
            )
            if cursor.fetchone() is None:
                cursor.close()
                return "not_found"

            try:
                cursor.execute(
                    f"DELETE FROM {SCHEMA}.driver WHERE driver_id = %s",
                    (driver_id,),
                )
                conn.commit()
                cursor.close()
                return "ok"
            except psycopg2.errors.ForeignKeyViolation:
                conn.rollback()
                cursor.close()
                return "conflict"
        finally:
            self.pool.putconn(conn)