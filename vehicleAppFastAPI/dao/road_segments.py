from vehicleAppFastAPI.config.dbconfig import PG_DB_CONFIG, POOL_CONFIG, SCHEMA
from psycopg2.pool import SimpleConnectionPool
from psycopg2.extras import DictCursor
from pydantic import BaseModel, Field
from typing import Optional, Any
from datetime import datetime
import psycopg2
import json


class RoadSegmentCreate(BaseModel):
    name: str
    speed_limit_kph: Optional[float] = None
    is_oneway: bool = False
    direction: Optional[str] = "both"
    geom: dict


class RoadSegmentUpdate(BaseModel):
    name: Optional[str] = None
    speed_limit_kph: Optional[float] = None
    is_oneway: Optional[bool] = None
    direction: Optional[str] = None
    geom: Optional[dict] = None


class RoadSegmentResponse(BaseModel):
    road_id: int
    name: str
    speed_limit_kph: Optional[float] = None
    is_oneway: Optional[bool] = None
    direction: Optional[str] = None
    geom: Optional[dict] = None
    created_at: datetime


class RoadSegmentDAO:
    def __init__(self):
        self.pool = SimpleConnectionPool(
            POOL_CONFIG["minconn"],
            POOL_CONFIG["maxconn"],
            **PG_DB_CONFIG,
        )

    def create_road_segment(self, payload: RoadSegmentCreate) -> int:
        conn = self.pool.getconn()
        try:
            cursor = conn.cursor(cursor_factory=DictCursor)
            
            geom_str = json.dumps(payload.geom)
            
            cursor.execute(
                f"""
                INSERT INTO {SCHEMA}.road_segment
                    (name, speed_limit_kph, is_oneway, direction, geom, created_at)
                VALUES (%s, %s, %s, %s, ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326), NOW())
                RETURNING road_id
                """,
                (
                    payload.name,
                    payload.speed_limit_kph,
                    payload.is_oneway,
                    payload.direction,
                    geom_str,
                ),
            )
            road_id = cursor.fetchone()[0]
            conn.commit()
            cursor.close()
            return road_id
        except Exception:
            conn.rollback()
            raise
        finally:
            self.pool.putconn(conn)

    def get_road_segments(
        self,
        limit: int,
        offset: int,
        bbox: Optional[tuple[float, float, float, float]] = None,
        name: Optional[str] = None,
        min_speed_kph: Optional[float] = None,
        max_speed_kph: Optional[float] = None,
    ) -> tuple[list[RoadSegmentResponse], int]:
        conn = self.pool.getconn()
        try:
            cursor = conn.cursor(cursor_factory=DictCursor)
            clauses = []
            params: list = []

            if name:
                clauses.append("name ILIKE %s")
                params.append(f"%{name}%")
            if min_speed_kph is not None:
                clauses.append("speed_limit_kph >= %s")
                params.append(min_speed_kph)
            if max_speed_kph is not None:
                clauses.append("speed_limit_kph <= %s")
                params.append(max_speed_kph)
            if bbox:
                minLon, minLat, maxLon, maxLat = bbox
                clauses.append("geom && ST_MakeEnvelope(%s, %s, %s, %s, 4326)")
                params.extend([minLon, minLat, maxLon, maxLat])

            where_sql = (" WHERE " + " AND ".join(clauses)) if clauses else ""

            # count
            cursor.execute(
                f"SELECT COUNT(*) FROM {SCHEMA}.road_segment {where_sql}",
                tuple(params),
            )
            count = cursor.fetchone()[0]

            # data
            cursor.execute(
                f"""
                SELECT road_id, name, speed_limit_kph, is_oneway, direction, 
                       ST_AsGeoJSON(geom)::json AS geom, created_at
                FROM {SCHEMA}.road_segment
                {where_sql}
                ORDER BY road_id
                LIMIT %s OFFSET %s
                """,
                tuple(params) + (limit, offset),
            )
            items = [RoadSegmentResponse(**row) for row in cursor.fetchall()]
            cursor.close()
            return items, count
        finally:
            self.pool.putconn(conn)

    def get_road_segment_by_id(self, road_id: int) -> Optional[RoadSegmentResponse]:
        conn = self.pool.getconn()
        try:
            cursor = conn.cursor(cursor_factory=DictCursor)
            cursor.execute(
                f"""
                SELECT road_id, name, speed_limit_kph, is_oneway, direction, 
                       ST_AsGeoJSON(geom)::json AS geom, created_at
                FROM {SCHEMA}.road_segment
                WHERE road_id = %s
                """,
                (road_id,),
            )
            row = cursor.fetchone()
            cursor.close()
            return RoadSegmentResponse(**row) if row else None
        finally:
            self.pool.putconn(conn)

    def update_road_segment(self, road_id: int, payload: RoadSegmentUpdate) -> Optional[RoadSegmentResponse]:
        data = payload.model_dump(exclude_unset=True)
        if not data:
            raise ValueError("empty")

        conn = self.pool.getconn()
        try:
            cursor = conn.cursor(cursor_factory=DictCursor)
            
            cursor.execute(
                f"SELECT 1 FROM {SCHEMA}.road_segment WHERE road_id = %s",
                (road_id,),
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
            data["road_id"] = road_id

            cursor.execute(
                f"""
                UPDATE {SCHEMA}.road_segment
                SET {set_sql}
                WHERE road_id = %(road_id)s
                """,
                data,
            )
            conn.commit()

            cursor.execute(
                f"""
                SELECT road_id, name, speed_limit_kph, is_oneway, direction, 
                       ST_AsGeoJSON(geom)::json AS geom, created_at
                FROM {SCHEMA}.road_segment
                WHERE road_id = %s
                """,
                (road_id,),
            )
            row = cursor.fetchone()
            cursor.close()
            return RoadSegmentResponse(**row) if row else None
        except Exception:
            conn.rollback()
            raise
        finally:
            self.pool.putconn(conn)

    def delete_road_segment(self, road_id: int) -> bool:
        conn = self.pool.getconn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                f"DELETE FROM {SCHEMA}.road_segment WHERE road_id = %s",
                (road_id,),
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