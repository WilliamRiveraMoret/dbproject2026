from config.dbconfig import PG_DB_CONFIG, POOL_CONFIG, SCHEMA
from psycopg2.pool import SimpleConnectionPool
from psycopg2.extras import DictCursor
from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class VehicleAssignmentCreate(BaseModel):
    vehicle_id: int
    driver_id: int
    assigned_from: datetime
    assigned_to: Optional[datetime] = None


class VehicleAssignmentUpdate(BaseModel):
    vehicle_id: Optional[int] = None
    driver_id: Optional[int] = None
    assigned_from: Optional[datetime] = None
    assigned_to: Optional[datetime] = None


class VehicleAssignmentResponse(BaseModel):
    assignment_id: int
    vehicle_id: int
    driver_id: int
    assigned_from: datetime
    assigned_to: Optional[datetime] = None


class VehicleAssignmentDAO:
    def __init__(self):
        self.pool = SimpleConnectionPool(
            POOL_CONFIG["minconn"],
            POOL_CONFIG["maxconn"],
            **PG_DB_CONFIG,
        )

    def _vehicle_exists(self, cursor, vehicle_id: int) -> bool:
        cursor.execute(
            f"SELECT 1 FROM {SCHEMA}.vehicle WHERE vehicle_id = %s",
            (vehicle_id,),
        )
        return cursor.fetchone() is not None

    def _driver_exists(self, cursor, driver_id: int) -> bool:
        cursor.execute(
            f"SELECT 1 FROM {SCHEMA}.driver WHERE driver_id = %s",
            (driver_id,),
        )
        return cursor.fetchone() is not None


    def create_assignment(self, payload: VehicleAssignmentCreate) -> int:
        conn = self.pool.getconn()
        try:
            cursor = conn.cursor(cursor_factory=DictCursor)
            if not self._vehicle_exists(cursor, payload.vehicle_id):
                cursor.close()
                raise LookupError("vehicle_id")
            if not self._driver_exists(cursor, payload.driver_id):
                cursor.close()
                raise LookupError("driver_id")

            if payload.assigned_to is not None and payload.assigned_to <= payload.assigned_from:
                cursor.close()
                raise ArithmeticError("assigned_to must be later than assigned_from")

            cursor.execute(
                f"""
                INSERT INTO {SCHEMA}.vehicle_assignment
                    (vehicle_id, driver_id, assigned_from, assigned_to)
                VALUES (%s, %s, %s, %s)
                RETURNING assignment_id
                """,
                (
                    payload.vehicle_id,
                    payload.driver_id,
                    payload.assigned_from,
                    payload.assigned_to,
                ),
            )
            assignment_id = cursor.fetchone()[0]
            conn.commit()
            cursor.close()
            return assignment_id
        except Exception:
            conn.rollback()
            raise
        finally:
            self.pool.putconn(conn)

    def get_assignment_by_id(self, assignment_id: int) -> Optional[VehicleAssignmentResponse]:
        conn = self.pool.getconn()
        try:
            cursor = conn.cursor(cursor_factory=DictCursor)
            cursor.execute(
                f"""
                SELECT assignment_id, vehicle_id, driver_id,
                       assigned_from, assigned_to
                FROM {SCHEMA}.vehicle_assignment
                WHERE assignment_id = %s
                """,
                (assignment_id,),
            )
            row = cursor.fetchone()
            cursor.close()
            return VehicleAssignmentResponse(**row) if row else None
        finally:
            self.pool.putconn(conn)

    def get_assignments(
        self,
        limit: int,
        offset: int,
        vehicle_id: Optional[int] = None,
        driver_id: Optional[int] = None,
        active: Optional[bool] = None,
    ) -> tuple[list[VehicleAssignmentResponse], int]:
        conn = self.pool.getconn()
        try:
            cursor = conn.cursor(cursor_factory=DictCursor)
            clauses, params = [], []

            if vehicle_id is not None:
                clauses.append("vehicle_id = %s")
                params.append(vehicle_id)
            if driver_id is not None:
                clauses.append("driver_id = %s")
                params.append(driver_id)
            if active is True:
                clauses.append("assigned_to IS NULL")
            elif active is False:
                clauses.append("assigned_to IS NOT NULL")

            where_sql = (" WHERE " + " AND ".join(clauses)) if clauses else ""

            cursor.execute(
                f"SELECT COUNT(*) FROM {SCHEMA}.vehicle_assignment {where_sql}",
                tuple(params),
            )
            count = cursor.fetchone()[0]

            cursor.execute(
                f"""
                SELECT assignment_id, vehicle_id, driver_id,
                       assigned_from, assigned_to
                FROM {SCHEMA}.vehicle_assignment
                {where_sql}
                ORDER BY assignment_id
                LIMIT %s OFFSET %s
                """,
                tuple(params) + (limit, offset),
            )
            items = [VehicleAssignmentResponse(**row) for row in cursor.fetchall()]
            cursor.close()
            return items, count
        finally:
            self.pool.putconn(conn)

    def update_assignment(self, assignment_id: int, payload: VehicleAssignmentUpdate) -> Optional[VehicleAssignmentResponse]:
        data = payload.model_dump(exclude_unset=True)
        if not data:
            raise ValueError("empty")

        conn = self.pool.getconn()
        try:
            cursor = conn.cursor(cursor_factory=DictCursor)
            cursor.execute(
                f"""
                SELECT assignment_id, vehicle_id, driver_id, assigned_from, assigned_to
                FROM {SCHEMA}.vehicle_assignment
                WHERE assignment_id = %s
                """,
                (assignment_id,),
            )
            existing = cursor.fetchone()
            if existing is None:
                cursor.close()
                return None

            if "vehicle_id" in data and data["vehicle_id"] is not None:
                if not self._vehicle_exists(cursor, data["vehicle_id"]):
                    cursor.close()
                    raise LookupError("vehicle_id")
            if "driver_id" in data and data["driver_id"] is not None:
                if not self._driver_exists(cursor, data["driver_id"]):
                    cursor.close()
                    raise LookupError("driver_id")

            new_from = data.get("assigned_from", existing["assigned_from"])
            new_to   = data.get("assigned_to",   existing["assigned_to"])
            if new_to is not None and new_to <= new_from:
                cursor.close()
                raise ArithmeticError("assigned_to must be later than assigned_from")

            set_sql = ", ".join(f"{k} = %({k})s" for k in data.keys())
            data["assignment_id"] = assignment_id

            cursor.execute(
                f"""
                UPDATE {SCHEMA}.vehicle_assignment
                SET {set_sql}
                WHERE assignment_id = %(assignment_id)s
                """,
                data,
            )
            conn.commit()

            cursor.execute(
                f"""
                SELECT assignment_id, vehicle_id, driver_id, assigned_from, assigned_to
                FROM {SCHEMA}.vehicle_assignment
                WHERE assignment_id = %s
                """,
                (assignment_id,),
            )
            row = cursor.fetchone()
            cursor.close()
            return VehicleAssignmentResponse(**row) if row else None
        except Exception:
            conn.rollback()
            raise
        finally:
            self.pool.putconn(conn)

    def delete_assignment(self, assignment_id: int) -> bool:
        conn = self.pool.getconn()
        try:
            cursor = conn.cursor(cursor_factory=DictCursor)
            cursor.execute(
                f"DELETE FROM {SCHEMA}.vehicle_assignment WHERE assignment_id = %s",
                (assignment_id,),
            )
            rows = cursor.rowcount
            conn.commit()
            cursor.close()
            return rows == 1
        finally:
            self.pool.putconn(conn)