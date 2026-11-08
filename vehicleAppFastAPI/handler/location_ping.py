from fastapi import HTTPException
from datetime import datetime, timezone
from dao.location_ping import LocationPingDAO, LocationPingCreate, LocationPingUpdate
 
 
def _naive(dt: datetime | None):
  """The ts column is a plain timestamp, so drop any timezone (converted to UTC first)."""
  if dt is not None and dt.tzinfo is not None:
    return dt.astimezone(timezone.utc).replace(tzinfo=None)
  return dt
 
 
class LocationPingHandler:
 
  def _check_point(self, geom: dict):
    if geom.get("type") != "Point":
      raise HTTPException(status_code=422, detail="geom must be a valid Point")

    coords = geom.get("coordinates")
    if not isinstance(coords, list) or len(coords) != 2:
      raise HTTPException(status_code=422, detail="geom coordinates must be [longitude, latitude]")
    if not all(isinstance(c, (int, float)) for c in coords):
      raise HTTPException(status_code=422, detail="geom coordinates must be numbers")

    lon, lat = coords
    if not (-180 <= lon <= 180 and -90 <= lat <= 90):
      raise HTTPException(status_code=422, detail="geom coordinates are out of range")

  def _check_speed_heading(self, speed_kph: float | None, heading_deg: float | None):
    if speed_kph is not None and speed_kph < 0:
      raise HTTPException(status_code=422, detail="speed_kph must be >= 0")
    if heading_deg is not None and (heading_deg < 0 or heading_deg >= 360):
      raise HTTPException(status_code=422, detail="heading_deg must be >= 0 and < 360")

  def _check_time_range(self, from_ts: datetime | None, to_ts: datetime | None):
    from_ts = _naive(from_ts)
    to_ts = _naive(to_ts)
    if from_ts is not None and to_ts is not None and from_ts > to_ts:
      raise HTTPException(status_code=422, detail="from_ts must be earlier than or equal to to_ts")
    return from_ts, to_ts

  def _parse_bbox(self, bbox_str: str):
    try:
      parts = [float(x.strip()) for x in bbox_str.split(",")]
      if len(parts) != 4:
        raise ValueError
      minLon, minLat, maxLon, maxLat = parts
      if not (-180 <= minLon <= 180 and -180 <= maxLon <= 180 and
          -90 <= minLat <= 90 and -90 <= maxLat <= 90):
        raise ValueError
      if minLon >= maxLon or minLat >= maxLat:
        raise ValueError
      return (minLon, minLat, maxLon, maxLat)
    except ValueError:
        raise HTTPException(
          status_code=422,
          detail="Invalid bbox format or range. Expected minLon,minLat,maxLon,maxLat",
        )


  def create_ping(self, payload: LocationPingCreate):
    if payload.vehicle_id <= 0:
      raise HTTPException(status_code=422, detail="vehicle_id must be a positive integer")
    self._check_point(payload.geom)
    self._check_speed_heading(payload.speed_kph, payload.heading_deg)
    payload.ts = _naive(payload.ts)

    try:
      dao = LocationPingDAO()
      ping_id = dao.create_ping(payload)
      return dao.get_ping_by_id(ping_id)
    except LookupError as e:
      raise HTTPException(status_code=404, detail=f"{e.args[0]} does not exist")
    except Exception:
      raise HTTPException(status_code=422, detail="Malformed geometry or invalid JSON payload")

  def get_pings(
    self,
    limit: int,
    offset: int,
    vehicle_id: int | None,
    from_ts: datetime | None,
    to_ts: datetime | None,
    bbox_str: str | None,
  ):
    if limit < 0 or offset < 0:
      raise HTTPException(status_code=400, detail="limit and offset must be non-negative")
    if vehicle_id is not None and vehicle_id <= 0:
      raise HTTPException(status_code=422, detail="vehicle_id must be a positive integer")
    from_ts, to_ts = self._check_time_range(from_ts, to_ts)

    bbox = None
    if bbox_str:
      bbox = self._parse_bbox(bbox_str)

    dao = LocationPingDAO()
    items, count = dao.get_pings(limit, offset, vehicle_id, from_ts, to_ts, bbox)
    return {"items": items, "limit": limit, "offset": offset, "count": count}

  def get_ping_by_id(self, ping_id: int):
    if ping_id <= 0:
      raise HTTPException(status_code=400, detail="ping_id must be a positive integer")
    dao = LocationPingDAO()
    result = dao.get_ping_by_id(ping_id)
    if result is None:
      raise HTTPException(status_code=404, detail="Location ping not found")
    return result

  def update_ping(self, ping_id: int, payload: LocationPingUpdate):
    if ping_id <= 0:
      raise HTTPException(status_code=400, detail="ping_id must be a positive integer")

    data = payload.model_dump(exclude_unset=True)
    if not data:
      raise HTTPException(status_code=422, detail="At least one updatable field is required")

    for field in ("vehicle_id", "ts", "geom"):
      if field in data and data[field] is None:
        raise HTTPException(status_code=422, detail=f"{field} cannot be null")

    if payload.vehicle_id is not None and payload.vehicle_id <= 0:
      raise HTTPException(status_code=422, detail="vehicle_id must be a positive integer")
    if payload.geom is not None:
      self._check_point(payload.geom)
    self._check_speed_heading(payload.speed_kph, payload.heading_deg)
    if payload.ts is not None:
      payload.ts = _naive(payload.ts)

    try:
      dao = LocationPingDAO()
      result = dao.update_ping(ping_id, payload)
    except LookupError as e:
      raise HTTPException(status_code=404, detail=f"{e.args[0]} does not exist")
    except Exception:
      raise HTTPException(status_code=422, detail="Malformed geometry or invalid JSON payload")

    if result is None:
      raise HTTPException(status_code=404, detail="Location ping not found")
    return result

  def delete_ping(self, ping_id: int):
    if ping_id <= 0:
      raise HTTPException(status_code=400, detail="ping_id must be a positive integer")
    dao = LocationPingDAO()
    deleted = dao.delete_ping(ping_id)
    if not deleted:
      raise HTTPException(status_code=404, detail="Location ping not found")
    return {"message": "Location ping deleted successfully.", "ping_id": ping_id}

  def get_vehicle_pings(
    self,
    vehicle_id: int,
    limit: int,
    offset: int,
    from_ts: datetime | None,
    to_ts: datetime | None,
  ):
    if vehicle_id <= 0:
      raise HTTPException(status_code=400, detail="vehicle_id must be a positive integer")
    if limit < 0 or offset < 0:
      raise HTTPException(status_code=400, detail="limit and offset must be non-negative")
    from_ts, to_ts = self._check_time_range(from_ts, to_ts)

    dao = LocationPingDAO()
    result = dao.get_vehicle_pings(vehicle_id, limit, offset, from_ts, to_ts)
    if result is None:
      raise HTTPException(status_code=404, detail="Vehicle not found")

    items, count = result
    return {
      "vehicle_id": vehicle_id,
      "items": items,
      "limit": limit,
      "offset": offset,
      "count": count,
    }