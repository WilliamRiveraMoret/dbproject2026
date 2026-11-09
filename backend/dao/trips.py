from backend.config.dbconfig import PG_DB_CONFIG, POOL_CONFIG, SCHEMA
from psycopg2.pool import SimpleConnectionPool
from psycopg2.extras import DictCursor
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import json
 
 
class TripCreate(BaseModel):
  vehicle_id: int
  start_ts: datetime
  end_ts: datetime
  start_geom: Optional[dict] = None
  end_geom: Optional[dict] = None
  distance_km: Optional[float] = None
 
 
class TripUpdate(BaseModel):
  vehicle_id: Optional[int] = None
  start_ts: Optional[datetime] = None
  end_ts: Optional[datetime] = None
  start_geom: Optional[dict] = None
  end_geom: Optional[dict] = None
  distance_km: Optional[float] = None
 
 
class TripResponse(BaseModel):
  trip_id: int
  vehicle_id: int
  start_ts: datetime
  end_ts: datetime
  start_geom: Optional[dict] = None
  end_geom: Optional[dict] = None
  distance_km: Optional[float] = None
 
 
class TripDAO:
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

  def _build_filters(
    self,
    vehicle_id: Optional[int],
    from_ts: Optional[datetime],
    to_ts: Optional[datetime],
  ):
    clauses = []
    params: list = []

    if vehicle_id is not None:
      clauses.append("vehicle_id = %s")
      params.append(vehicle_id)
    if from_ts is not None:
      clauses.append("start_ts >= %s")
      params.append(from_ts)
    if to_ts is not None:
      clauses.append("start_ts <= %s")
      params.append(to_ts)

    where_sql = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    return where_sql, params

  def create_trip(self, payload: TripCreate) -> int:
    conn = self.pool.getconn()
    try:
      cursor = conn.cursor(cursor_factory=DictCursor)
      if not self._vehicle_exists(cursor, payload.vehicle_id):
        cursor.close()
        raise LookupError("vehicle_id")

      start_geom = json.dumps(payload.start_geom) if payload.start_geom is not None else None
      end_geom = json.dumps(payload.end_geom) if payload.end_geom is not None else None

      cursor.execute(
        f"""
        INSERT INTO {SCHEMA}.trip
          (vehicle_id, start_ts, end_ts, start_geom, end_geom, distance_km)
        VALUES (
          %s, %s, %s,
          ST_SetSRID(ST_GeomFromGeoJSON(%s::text), 4326),
          ST_SetSRID(ST_GeomFromGeoJSON(%s::text), 4326),
          %s
        )
        RETURNING trip_id
        """,
        (
          payload.vehicle_id,
          payload.start_ts,
          payload.end_ts,
          start_geom,
          end_geom,
          payload.distance_km,
        ),
      )
      trip_id = cursor.fetchone()[0]
      conn.commit()
      cursor.close()
      return trip_id
    except Exception:
      conn.rollback()
      raise
    finally:
      self.pool.putconn(conn)

  def get_trips(
    self,
    limit: int,
    offset: int,
    vehicle_id: Optional[int] = None,
    from_ts: Optional[datetime] = None,
    to_ts: Optional[datetime] = None,
  ) -> tuple[list[dict], int]:
    conn = self.pool.getconn()
    try:
      cursor = conn.cursor(cursor_factory=DictCursor)
      where_sql, params = self._build_filters(vehicle_id, from_ts, to_ts)

      cursor.execute(
        f"SELECT COUNT(*) FROM {SCHEMA}.trip {where_sql}",
        tuple(params),
      )
      count = cursor.fetchone()[0]

      cursor.execute(
        f"""
        SELECT trip_id, vehicle_id, start_ts, end_ts, distance_km
        FROM {SCHEMA}.trip
        {where_sql}
        ORDER BY trip_id
        LIMIT %s OFFSET %s
        """,
        tuple(params) + (limit, offset),
      )
      items = [dict(row) for row in cursor.fetchall()]
      cursor.close()
      return items, count
    finally:
      self.pool.putconn(conn)

  def get_trip_by_id(self, trip_id: int) -> Optional[TripResponse]:
    conn = self.pool.getconn()
    try:
      cursor = conn.cursor(cursor_factory=DictCursor)
      cursor.execute(
        f"""
        SELECT trip_id, vehicle_id, start_ts, end_ts,
          ST_AsGeoJSON(start_geom)::json AS start_geom,
          ST_AsGeoJSON(end_geom)::json AS end_geom,
          distance_km
        FROM {SCHEMA}.trip
        WHERE trip_id = %s
        """,
        (trip_id,),
      )
      row = cursor.fetchone()
      cursor.close()
      return TripResponse(**row) if row else None
    finally:
      self.pool.putconn(conn)

  def update_trip(self, trip_id: int, payload: TripUpdate) -> Optional[TripResponse]:
    data = payload.model_dump(exclude_unset=True)
    if not data:
      raise ValueError("empty")

    conn = self.pool.getconn()
    try:
      cursor = conn.cursor(cursor_factory=DictCursor)

      cursor.execute(
        f"SELECT start_ts, end_ts FROM {SCHEMA}.trip WHERE trip_id = %s",
        (trip_id,),
      )
      current = cursor.fetchone()
      if current is None:
        cursor.close()
        return None

      if "vehicle_id" in data and not self._vehicle_exists(cursor, data["vehicle_id"]):
        cursor.close()
        raise LookupError("vehicle_id")

      new_start = data.get("start_ts", current["start_ts"])
      new_end = data.get("end_ts", current["end_ts"])
      if new_end <= new_start:
        cursor.close()
        raise ValueError("end_ts")

      set_parts = []
      for k in data.keys():
        if k in ("start_geom", "end_geom") and data[k] is not None:
          data[k] = json.dumps(data[k])
          set_parts.append(f"{k} = ST_SetSRID(ST_GeomFromGeoJSON(%({k})s), 4326)")
        else:
          set_parts.append(f"{k} = %({k})s")

      set_sql = ", ".join(set_parts)
      data["trip_id"] = trip_id

      cursor.execute(
        f"""
        UPDATE {SCHEMA}.trip
        SET {set_sql}
        WHERE trip_id = %(trip_id)s
        """,
        data,
      )
      conn.commit()

      cursor.execute(
        f"""
        SELECT trip_id, vehicle_id, start_ts, end_ts,
          ST_AsGeoJSON(start_geom)::json AS start_geom,
          ST_AsGeoJSON(end_geom)::json AS end_geom,
          distance_km
        FROM {SCHEMA}.trip
        WHERE trip_id = %s
        """,
        (trip_id,),
      )
      row = cursor.fetchone()
      cursor.close()
      return TripResponse(**row) if row else None
    except Exception:
      conn.rollback()
      raise
    finally:
      self.pool.putconn(conn)

  def delete_trip(self, trip_id: int) -> bool:
    conn = self.pool.getconn()
    try:
      cursor = conn.cursor()
      cursor.execute(
        f"DELETE FROM {SCHEMA}.trip WHERE trip_id = %s",
        (trip_id,),
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

  def get_vehicle_trips(
    self,
    vehicle_id: int,
    limit: int,
    offset: int,
    from_ts: Optional[datetime] = None,
    to_ts: Optional[datetime] = None,
  ) -> Optional[tuple[list[dict], int]]:
    conn = self.pool.getconn()
    try:
      cursor = conn.cursor(cursor_factory=DictCursor)
      if not self._vehicle_exists(cursor, vehicle_id):
        cursor.close()
        return None

      where_sql, params = self._build_filters(vehicle_id, from_ts, to_ts)

      cursor.execute(
        f"SELECT COUNT(*) FROM {SCHEMA}.trip {where_sql}",
        tuple(params),
      )
      count = cursor.fetchone()[0]

      cursor.execute(
        f"""
        SELECT trip_id, start_ts, end_ts, distance_km
        FROM {SCHEMA}.trip
        {where_sql}
        ORDER BY start_ts, trip_id
        LIMIT %s OFFSET %s
        """,
        tuple(params) + (limit, offset),
      )
      items = [dict(row) for row in cursor.fetchall()]
      cursor.close()
      return items, count
    finally:
      self.pool.putconn(conn)