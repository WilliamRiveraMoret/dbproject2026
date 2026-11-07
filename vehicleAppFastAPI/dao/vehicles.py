from config.dbconfig import PG_DB_CONFIG, POOL_CONFIG, SCHEMA
from psycopg2.pool import SimpleConnectionPool
from psycopg2.extras import DictCursor, RealDictCursor
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import psycopg2


class VehicleCreate(BaseModel):
    vehicle_type_id: int
    vehicle_status_id: int
    plate_number: str
    make: Optional[str] = None
    model: Optional[str] = None
    year: int


class VehicleUpdate(BaseModel):
    vehicle_type_id: Optional[int] = None
    vehicle_status_id: Optional[int] = None
    plate_number: Optional[str] = None
    make: Optional[str] = None
    model: Optional[str] = None
    year: Optional[int] = None


class VehicleResponse(BaseModel):
    vehicle_id: int
    vehicle_type_id: int
    vehicle_status_id: int
    plate_number: str
    make: Optional[str] = None
    model: Optional[str] = None
    year: int
    created_at: datetime


class CurrentLocationResponse(BaseModel):
    vehicle_id: int
    plate_number: str
    status: Optional[str] = None
    vehicle_kind: Optional[str] = None
    fuel_type: Optional[str] = None
    emissions_rating: Optional[float] = None
    last_ts: Optional[datetime] = None
    last_geom: Optional[dict] = None
    speed_kph: Optional[float] = None
    heading_deg: Optional[float] = None


class VehicleDAO:
    def __init__(self):
        self.pool = SimpleConnectionPool(
            POOL_CONFIG["minconn"],
            POOL_CONFIG["maxconn"],
            **PG_DB_CONFIG,
        )

    def _type_exists(self, cursor, vehicle_type_id: int) -> bool:
        cursor.execute(
            f"SELECT 1 FROM {SCHEMA}.vehicle_type WHERE vehicle_type_id = %s",
            (vehicle_type_id,),
        )
        return cursor.fetchone() is not None

    def _status_exists(self, cursor, vehicle_status_id: int) -> bool:
        cursor.execute(
            f"SELECT 1 FROM {SCHEMA}.vehicle_status WHERE vehicle_status_id = %s",
            (vehicle_status_id,),
        )
        return cursor.fetchone() is not None

    def _plate_exists(self, cursor, plate_number: str, exclude_id: Optional[int] = None) -> bool:
        if exclude_id is None:
            cursor.execute(
                f"SELECT 1 FROM {SCHEMA}.vehicle WHERE plate_number = %s",
                (plate_number,),
            )
        else:
            cursor.execute(
                f"SELECT 1 FROM {SCHEMA}.vehicle WHERE plate_number = %s AND vehicle_id <> %s",
                (plate_number, exclude_id),
            )
        return cursor.fetchone() is not None

    def create_vehicle(self, payload: VehicleCreate) -> int:
        conn = self.pool.getconn()
        try:
            cursor = conn.cursor(cursor_factory=DictCursor)
            if not self._type_exists(cursor, payload.vehicle_type_id):
                cursor.close()
                raise LookupError("vehicle_type_id")
            if not self._status_exists(cursor, payload.vehicle_status_id):
                cursor.close()
                raise LookupError("vehicle_status_id")
            if self._plate_exists(cursor, payload.plate_number):
                cursor.close()
                raise ValueError("plate_number")

            make  = payload.make.strip()  if payload.make  is not None else None
            model = payload.model.strip() if payload.model is not None else None

            cursor.execute(
                f"""
                INSERT INTO {SCHEMA}.vehicle
                    (vehicle_type_id, vehicle_status_id, plate_number,
                     make, model, year, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, NOW())
                RETURNING vehicle_id
                """,
                (
                    payload.vehicle_type_id,
                    payload.vehicle_status_id,
                    payload.plate_number,
                    make,
                    model,
                    payload.year,
                ),
            )
            vehicle_id = cursor.fetchone()[0]
            conn.commit()
            cursor.close()
            return vehicle_id
        except Exception:
            conn.rollback()
            raise
        finally:
            self.pool.putconn(conn)

    def get_vehicle_by_id(self, vehicle_id: int) -> Optional[VehicleResponse]:
        conn = self.pool.getconn()
        try:
            cursor = conn.cursor(cursor_factory=DictCursor)
            cursor.execute(
                f"""
                SELECT vehicle_id, vehicle_type_id, vehicle_status_id,
                       plate_number, make, model, year, created_at
                FROM {SCHEMA}.vehicle
                WHERE vehicle_id = %s
                """,
                (vehicle_id,),
            )
            row = cursor.fetchone()
            cursor.close()
            return VehicleResponse(**row) if row else None
        finally:
            self.pool.putconn(conn)

    def get_vehicles(
        self,
        limit: int,
        offset: int,
        status: Optional[str] = None,
        plate_number: Optional[str] = None,
    ) -> tuple[list[VehicleResponse], int]:
        conn = self.pool.getconn()
        try:
            cursor = conn.cursor(cursor_factory=DictCursor)
            clauses = []
            params: list = []

            if status is not None:
                if status.isdigit():
                    clauses.append("v.vehicle_status_id = %s")
                    params.append(int(status))
                else:
                    clauses.append("vs.name ILIKE %s")
                    params.append(f"%{status}%")

            if plate_number is not None:
                clauses.append("v.plate_number ILIKE %s")
                params.append(f"%{plate_number}%")

            where_sql = (" WHERE " + " AND ".join(clauses)) if clauses else ""

            # total count
            cursor.execute(
                f"""
                SELECT COUNT(*)
                FROM {SCHEMA}.vehicle v
                JOIN {SCHEMA}.vehicle_status vs
                     ON vs.vehicle_status_id = v.vehicle_status_id
                {where_sql}
                """,
                tuple(params),
            )
            count = cursor.fetchone()[0]

            cursor.execute(
                f"""
                SELECT v.vehicle_id, v.vehicle_type_id, v.vehicle_status_id,
                       v.plate_number, v.make, v.model, v.year, v.created_at
                FROM {SCHEMA}.vehicle v
                JOIN {SCHEMA}.vehicle_status vs
                     ON vs.vehicle_status_id = v.vehicle_status_id
                {where_sql}
                ORDER BY v.vehicle_id
                LIMIT %s OFFSET %s
                """,
                tuple(params) + (limit, offset),
            )
            items = [VehicleResponse(**row) for row in cursor.fetchall()]
            cursor.close()
            return items, count
        finally:
            self.pool.putconn(conn)

    def update_vehicle(self, vehicle_id: int, payload: VehicleUpdate) -> Optional[VehicleResponse]:
        data = payload.model_dump(exclude_unset=True)
        if not data:
            raise ValueError("empty")

        conn = self.pool.getconn()
        try:
            cursor = conn.cursor(cursor_factory=DictCursor)
            # existence
            cursor.execute(
                f"SELECT 1 FROM {SCHEMA}.vehicle WHERE vehicle_id = %s",
                (vehicle_id,),
            )
            if cursor.fetchone() is None:
                cursor.close()
                return None

            if "vehicle_type_id" in data and not self._type_exists(cursor, data["vehicle_type_id"]):
                cursor.close()
                raise LookupError("vehicle_type_id")
            if "vehicle_status_id" in data and not self._status_exists(cursor, data["vehicle_status_id"]):
                cursor.close()
                raise LookupError("vehicle_status_id")
            if "plate_number" in data and self._plate_exists(cursor, data["plate_number"], exclude_id=vehicle_id):
                cursor.close()
                raise ValueError("plate_number")

            for text_field in ("make", "model"):
                if text_field in data and data[text_field] is not None:
                    data[text_field] = data[text_field].strip()

            set_parts = [f"{k} = %({k})s" for k in data.keys()]
            set_sql = ", ".join(set_parts)
            data["vehicle_id"] = vehicle_id

            cursor.execute(
                f"""
                UPDATE {SCHEMA}.vehicle
                SET {set_sql}
                WHERE vehicle_id = %(vehicle_id)s
                """,
                data,
            )
            conn.commit()

            cursor.execute(
                f"""
                SELECT vehicle_id, vehicle_type_id, vehicle_status_id,
                       plate_number, make, model, year, created_at
                FROM {SCHEMA}.vehicle
                WHERE vehicle_id = %s
                """,
                (vehicle_id,),
            )
            row = cursor.fetchone()
            cursor.close()
            return VehicleResponse(**row) if row else None
        except Exception:
            conn.rollback()
            raise
        finally:
            self.pool.putconn(conn)

    def delete_vehicle(self, vehicle_id: int) -> str:
        """Returns 'ok', 'not_found', or 'conflict'."""
        conn = self.pool.getconn()
        try:
            cursor = conn.cursor(cursor_factory=DictCursor)
            cursor.execute(
                f"SELECT 1 FROM {SCHEMA}.vehicle WHERE vehicle_id = %s",
                (vehicle_id,),
            )
            if cursor.fetchone() is None:
                cursor.close()
                return "not_found"

            try:
                cursor.execute(
                    f"DELETE FROM {SCHEMA}.vehicle WHERE vehicle_id = %s",
                    (vehicle_id,),
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

    def get_current_location(self, vehicle_id: int) -> Optional[CurrentLocationResponse]:
        """Returns None if vehicle not found. Returns an object with
        last_ts/last_geom None if vehicle exists but has no pings."""
        conn = self.pool.getconn()
        try:
            cursor = conn.cursor(cursor_factory=DictCursor)

            cursor.execute(
                f"""
                SELECT v.vehicle_id, v.plate_number,
                       vs.name          AS status,
                       vk.name          AS vehicle_kind,
                       ft.name          AS fuel_type,
                       vt.emissions_rating AS emissions_rating
                FROM {SCHEMA}.vehicle v
                JOIN {SCHEMA}.vehicle_status vs ON vs.vehicle_status_id = v.vehicle_status_id
                JOIN {SCHEMA}.vehicle_type   vt ON vt.vehicle_type_id   = v.vehicle_type_id
                JOIN {SCHEMA}.vehicle_kind   vk ON vk.vehicle_kind_id   = vt.vehicle_kind_id
                JOIN {SCHEMA}.fuel_type      ft ON ft.fuel_type_id      = vt.fuel_type_id
                WHERE v.vehicle_id = %s
                """,
                (vehicle_id,),
            )
            base = cursor.fetchone()
            if base is None:
                cursor.close()
                return None

            cursor.execute(
                f"""
                SELECT lp.ts, lp.speed_kph, lp.heading_deg,
                       ST_AsGeoJSON(lp.geom)::json AS last_geom
                FROM {SCHEMA}.location_ping lp
                WHERE lp.vehicle_id = %s
                ORDER BY lp.ts DESC
                LIMIT 1
                """,
                (vehicle_id,),
            )
            ping = cursor.fetchone()
            cursor.close()

            return CurrentLocationResponse(
                vehicle_id=base["vehicle_id"],
                plate_number=base["plate_number"],
                status=base["status"],
                vehicle_kind=base["vehicle_kind"],
                fuel_type=base["fuel_type"],
                emissions_rating=base["emissions_rating"],
                last_ts=ping["ts"] if ping else None,
                last_geom=ping["last_geom"] if ping else None,
                speed_kph=ping["speed_kph"] if ping else None,
                heading_deg=ping["heading_deg"] if ping else None,
            )
        finally:
            self.pool.putconn(conn)