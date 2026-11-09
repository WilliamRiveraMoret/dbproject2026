from backend.config.dbconfig import PG_DB_CONFIG, POOL_CONFIG, SCHEMA
from psycopg2.pool import SimpleConnectionPool
from psycopg2.extras import DictCursor
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import psycopg2
import json


class ParkingAreaCreate(BaseModel):
    name: str
    capacity: Optional[int] = None
    geom: dict


class ParkingAreaUpdate(BaseModel):
    name: Optional[str] = None
    capacity: Optional[int] = None
    geom: Optional[dict] = None


class ParkingAreaResponse(BaseModel):
    parking_area_id: int
    name: str
    capacity: Optional[int] = None
    geom: Optional[dict] = None
    created_at: datetime


class ParkingAreaDAO:
    def __init__(self):
        self.pool = SimpleConnectionPool(
            POOL_CONFIG["minconn"],
            POOL_CONFIG["maxconn"],
            **PG_DB_CONFIG,
        )

    def create_parking_area(self, payload: ParkingAreaCreate) -> int:
        conn = self.pool.getconn()
        try:
            cursor = conn.cursor(cursor_factory=DictCursor)
            
            geom_str = json.dumps(payload.geom)
            
            cursor.execute(
                f"""
                INSERT INTO {SCHEMA}.parking_area
                    (name, capacity, geom, created_at)
                VALUES (%s, %s, ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326), NOW())
                RETURNING parking_area_id
                """,
                (
                    payload.name,
                    payload.capacity,
                    geom_str,
                ),
            )
            parking_area_id = cursor.fetchone()[0]
            conn.commit()
            cursor.close()
            return parking_area_id
        except Exception:
            conn.rollback()
            raise
        finally:
            self.pool.putconn(conn)

    def get_parking_areas(
        self,
        limit: int,
        offset: int,
        bbox: Optional[tuple[float, float, float, float]] = None,
        name: Optional[str] = None,
    ) -> tuple[list[dict], int]:
        conn = self.pool.getconn()
        try:
            cursor = conn.cursor(cursor_factory=DictCursor)
            clauses = []
            params: list = []

            if name:
                clauses.append("name ILIKE %s")
                params.append(f"%{name}%")
            if bbox:
                minLon, minLat, maxLon, maxLat = bbox
                clauses.append("geom && ST_MakeEnvelope(%s, %s, %s, %s, 4326)")
                params.extend([minLon, minLat, maxLon, maxLat])

            where_sql = (" WHERE " + " AND ".join(clauses)) if clauses else ""

            # count
            cursor.execute(
                f"SELECT COUNT(*) FROM {SCHEMA}.parking_area {where_sql}",
                tuple(params),
            )
            count = cursor.fetchone()[0]

            # data (geom is omitted in list based on spec example)
            cursor.execute(
                f"""
                SELECT parking_area_id, name, capacity, created_at
                FROM {SCHEMA}.parking_area
                {where_sql}
                ORDER BY parking_area_id
                LIMIT %s OFFSET %s
                """,
                tuple(params) + (limit, offset),
            )
            items = [dict(row) for row in cursor.fetchall()]
            
            # Format datetime for JSON response explicitly like the spec, or rely on FastAPI
            for item in items:
                if isinstance(item.get("created_at"), datetime):
                    item["created_at"] = item["created_at"].isoformat() + "Z"

            cursor.close()
            return items, count
        finally:
            self.pool.putconn(conn)

    def get_parking_area_by_id(self, parking_area_id: int) -> Optional[ParkingAreaResponse]:
        conn = self.pool.getconn()
        try:
            cursor = conn.cursor(cursor_factory=DictCursor)
            cursor.execute(
                f"""
                SELECT parking_area_id, name, capacity, 
                       ST_AsGeoJSON(geom)::json AS geom, created_at
                FROM {SCHEMA}.parking_area
                WHERE parking_area_id = %s
                """,
                (parking_area_id,),
            )
            row = cursor.fetchone()
            cursor.close()
            return ParkingAreaResponse(**row) if row else None
        finally:
            self.pool.putconn(conn)

    def update_parking_area(self, parking_area_id: int, payload: ParkingAreaUpdate) -> Optional[ParkingAreaResponse]:
        data = payload.model_dump(exclude_unset=True)
        if not data:
            raise ValueError("empty")

        conn = self.pool.getconn()
        try:
            cursor = conn.cursor(cursor_factory=DictCursor)
            
            cursor.execute(
                f"SELECT 1 FROM {SCHEMA}.parking_area WHERE parking_area_id = %s",
                (parking_area_id,),
            )
            if cursor.fetchone() is None:
                cursor.close()
                return None

            set_parts = []
            for k in data.keys():
                if k == "geom":
                    data["geom"] = json.dumps(data["geom"])
                    set_parts.append("geom = ST_SetSRID(ST_GeomFromGeoJSON(%(geom)s), 4326)")
                else:
                    set_parts.append(f"{k} = %({k})s")
            
            set_sql = ", ".join(set_parts)
            data["parking_area_id"] = parking_area_id

            cursor.execute(
                f"""
                UPDATE {SCHEMA}.parking_area
                SET {set_sql}
                WHERE parking_area_id = %(parking_area_id)s
                """,
                data,
            )
            conn.commit()

            cursor.execute(
                f"""
                SELECT parking_area_id, name, capacity, 
                       ST_AsGeoJSON(geom)::json AS geom, created_at
                FROM {SCHEMA}.parking_area
                WHERE parking_area_id = %s
                """,
                (parking_area_id,),
            )
            row = cursor.fetchone()
            cursor.close()
            return ParkingAreaResponse(**row) if row else None
        except Exception:
            conn.rollback()
            raise
        finally:
            self.pool.putconn(conn)

    def delete_parking_area(self, parking_area_id: int) -> bool:
        conn = self.pool.getconn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                f"DELETE FROM {SCHEMA}.parking_area WHERE parking_area_id = %s",
                (parking_area_id,),
            )
            deleted = cursor.rowcount > 0
            conn.commit()
            cursor.close()
            return deleted
        except Exception:
            conn.rollback()
            raise
        finally:
            self.pool.putconn(conn)