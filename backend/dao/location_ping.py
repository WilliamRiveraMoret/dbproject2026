from backend.config.dbconfig import PG_DB_CONFIG, POOL_CONFIG, SCHEMA
from psycopg2.pool import SimpleConnectionPool
from psycopg2.extras import DictCursor
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import json


class LocationPingCreate(BaseModel):
  vehicle_id: int
  ts: datetime
  geom: dict
  speed_kph: Optional[float] = None
  heading_deg: Optional[float] = None


class LocationPingUpdate(BaseModel):
  vehicle_id: Optional[int] = None
  ts: Optional[datetime] = None
  geom: Optional[dict] = None
  speed_kph: Optional[float] = None
  heading_deg: Optional[float] = None


class LocationPingResponse(BaseModel):
  ping_id: int
  vehicle_id: int
  ts: datetime
  geom: Optional[dict] = None
  speed_kph: Optional[float] = None
  heading_deg: Optional[float] = None


class LocationPingDAO:
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
    bbox: Optional[tuple[float, float, float, float]],
  ):
    clauses = []
    params: list = []

    if vehicle_id is not None:
      clauses.append("vehicle_id = %s")
      params.append(vehicle_id)
    if from_ts is not None:
      clauses.append("ts >= %s")
      params.append(from_ts)
    if to_ts is not None:
      clauses.append("ts <= %s")
      params.append(to_ts)
    if bbox:
      minLon, minLat, maxLon, maxLat = bbox
      clauses.append("geom && ST_MakeEnvelope(%s, %s, %s, %s, 4326)")
      params.extend([minLon, minLat, maxLon, maxLat])

    where_sql = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    return where_sql, params

  def create_ping(self, payload: LocationPingCreate) -> int:
    conn = self.pool.getconn()
    try:
      cursor = conn.cursor(cursor_factory=DictCursor)
      if not self._vehicle_exists(cursor, payload.vehicle_id):
        cursor.close()
        raise LookupError("vehicle_id")

      geom_str = json.dumps(payload.geom)

      cursor.execute(
        f"""
        INSERT INTO {SCHEMA}.location_ping
          (vehicle_id, ts, geom, speed_kph, heading_deg)
        VALUES (%s, %s, ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326), %s, %s)
        RETURNING ping_id
        """,
        (
          payload.vehicle_id,
          payload.ts,
          geom_str,
          payload.speed_kph,
          payload.heading_deg,
        ),
      )
      ping_id = cursor.fetchone()[0]
      conn.commit()
      cursor.close()
      return ping_id
    except Exception:
      conn.rollback()
      raise
    finally:
      self.pool.putconn(conn)

  def get_pings(
    self,
    limit: int,
    offset: int,
    vehicle_id: Optional[int] = None,
    from_ts: Optional[datetime] = None,
    to_ts: Optional[datetime] = None,
    bbox: Optional[tuple[float, float, float, float]] = None,
  ) -> tuple[list[dict], int]:
    conn = self.pool.getconn()
    try:
      cursor = conn.cursor(cursor_factory=DictCursor)
      where_sql, params = self._build_filters(vehicle_id, from_ts, to_ts, bbox)

      cursor.execute(
        f"SELECT COUNT(*) FROM {SCHEMA}.location_ping {where_sql}",
        tuple(params),
      )
      count = cursor.fetchone()[0]

      cursor.execute(
        f"""
        SELECT ping_id, vehicle_id, ts, speed_kph, heading_deg
        FROM {SCHEMA}.location_ping
        {where_sql}
        ORDER BY ping_id
        LIMIT %s OFFSET %s
        """,
        tuple(params) + (limit, offset),
      )
      items = [dict(row) for row in cursor.fetchall()]
      cursor.close()
      return items, count
    finally:
      self.pool.putconn(conn)

  def get_ping_by_id(self, ping_id: int) -> Optional[LocationPingResponse]:
    conn = self.pool.getconn()
    try:
      cursor = conn.cursor(cursor_factory=DictCursor)
      cursor.execute(
        f"""
        SELECT ping_id, vehicle_id, ts,
          ST_AsGeoJSON(geom)::json AS geom,
          speed_kph, heading_deg
        FROM {SCHEMA}.location_ping
        WHERE ping_id = %s
        """,
        (ping_id,),
      )
      row = cursor.fetchone()
      cursor.close()
      return LocationPingResponse(**row) if row else None
    finally:
      self.pool.putconn(conn)

  def update_ping(self, ping_id: int, payload: LocationPingUpdate) -> Optional[LocationPingResponse]:
    data = payload.model_dump(exclude_unset=True)
    if not data:
      raise ValueError("empty")

    conn = self.pool.getconn()
    try:
      cursor = conn.cursor(cursor_factory=DictCursor)

      cursor.execute(
        f"SELECT 1 FROM {SCHEMA}.location_ping WHERE ping_id = %s",
        (ping_id,),
      )
      if cursor.fetchone() is None:
        cursor.close()
        return None

      if "vehicle_id" in data and not self._vehicle_exists(cursor, data["vehicle_id"]):
        cursor.close()
        raise LookupError("vehicle_id")

      set_parts = []
      for k in data.keys():
        if k == "geom":
          data["geom"] = json.dumps(data["geom"])
          set_parts.append("geom = ST_SetSRID(ST_GeomFromGeoJSON(%(geom)s), 4326)")
        else:
          set_parts.append(f"{k} = %({k})s")

      set_sql = ", ".join(set_parts)
      data["ping_id"] = ping_id

      cursor.execute(
        f"""
        UPDATE {SCHEMA}.location_ping
        SET {set_sql}
        WHERE ping_id = %(ping_id)s
        """,
        data,
      )
      conn.commit()

      cursor.execute(
        f"""
        SELECT ping_id, vehicle_id, ts,
          ST_AsGeoJSON(geom)::json AS geom,
          speed_kph, heading_deg
        FROM {SCHEMA}.location_ping
        WHERE ping_id = %s
        """,
        (ping_id,),
      )
      row = cursor.fetchone()
      cursor.close()
      return LocationPingResponse(**row) if row else None
    except Exception:
      conn.rollback()
      raise
    finally:
      self.pool.putconn(conn)

  def delete_ping(self, ping_id: int) -> bool:
    conn = self.pool.getconn()
    try:
      cursor = conn.cursor()
      cursor.execute(
        f"DELETE FROM {SCHEMA}.location_ping WHERE ping_id = %s",
        (ping_id,),
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

  def get_vehicle_pings(
    self,
    vehicle_id: int,
    limit: int,
    offset: int,
    from_ts: Optional[datetime] = None,
    to_ts: Optional[datetime] = None,
  ) -> Optional[tuple[list[dict], int]]:
    """Returns None if the vehicle does not exist."""
    conn = self.pool.getconn()
    try:
      cursor = conn.cursor(cursor_factory=DictCursor)
      if not self._vehicle_exists(cursor, vehicle_id):
        cursor.close()
        return None

      where_sql, params = self._build_filters(vehicle_id, from_ts, to_ts, None)

      cursor.execute(
        f"SELECT COUNT(*) FROM {SCHEMA}.location_ping {where_sql}",
        tuple(params),
      )
      count = cursor.fetchone()[0]

      cursor.execute(
        f"""
        SELECT ping_id, ts,
                ST_AsGeoJSON(geom)::json AS geom,
                speed_kph, heading_deg
        FROM {SCHEMA}.location_ping
        {where_sql}
        ORDER BY ts, ping_id
        LIMIT %s OFFSET %s
        """,
        tuple(params) + (limit, offset),
      )
      items = [dict(row) for row in cursor.fetchall()]
      cursor.close()
      return items, count
    finally:
      self.pool.putconn(conn)