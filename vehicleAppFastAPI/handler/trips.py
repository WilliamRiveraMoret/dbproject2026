from fastapi import HTTPException
from datetime import datetime, timezone
from vehicleAppFastAPI.dao.trips import TripDAO, TripCreate, TripUpdate
 
 
def _naive(dt: datetime | None):
  if dt is not None and dt.tzinfo is not None:
    return dt.astimezone(timezone.utc).replace(tzinfo=None)
  return dt
 
 
class TripHandler:
  def _check_point(self, geom: dict, field: str):
    if geom.get("type") != "Point":
      raise HTTPException(status_code=422, detail=f"{field} must be a valid Point")

    coords = geom.get("coordinates")
    if not isinstance(coords, list) or len(coords) != 2:
      raise HTTPException(status_code=422, detail=f"{field} coordinates must be [longitude, latitude]")
    if not all(isinstance(c, (int, float)) for c in coords):
      raise HTTPException(status_code=422, detail=f"{field} coordinates must be numbers")

    lon, lat = coords
    if not (-180 <= lon <= 180 and -90 <= lat <= 90):
      raise HTTPException(status_code=422, detail=f"{field} coordinates are out of range")

  def _check_distance(self, distance_km: float | None):
    if distance_km is not None and distance_km < 0:
      raise HTTPException(status_code=422, detail="distance_km must be >= 0")

  def _check_time_range(self, from_ts: datetime | None, to_ts: datetime | None):
    from_ts = _naive(from_ts)
    to_ts = _naive(to_ts)
    if from_ts is not None and to_ts is not None and from_ts > to_ts:
      raise HTTPException(status_code=422, detail="from_ts must be earlier than or equal to to_ts")
    return from_ts, to_ts

  def create_trip(self, payload: TripCreate):
    if payload.vehicle_id <= 0:
      raise HTTPException(status_code=422, detail="vehicle_id must be a positive integer")

    payload.start_ts = _naive(payload.start_ts)
    payload.end_ts = _naive(payload.end_ts)
    if payload.end_ts <= payload.start_ts:
      raise HTTPException(status_code=422, detail="end_ts must be later than start_ts")

    if payload.start_geom is not None:
      self._check_point(payload.start_geom, "start_geom")
    if payload.end_geom is not None:
      self._check_point(payload.end_geom, "end_geom")
    self._check_distance(payload.distance_km)

    try:
      dao = TripDAO()
      trip_id = dao.create_trip(payload)
      return dao.get_trip_by_id(trip_id)
    except LookupError as e:
      raise HTTPException(status_code=404, detail=f"{e.args[0]} does not exist")
    except Exception:
      raise HTTPException(status_code=422, detail="Malformed geometry or invalid JSON payload")

  def get_trips(
    self,
    limit: int,
    offset: int,
    vehicle_id: int | None,
    from_ts: datetime | None,
    to_ts: datetime | None,
  ):
    if limit < 0 or offset < 0:
      raise HTTPException(status_code=400, detail="limit and offset must be non-negative")
    if vehicle_id is not None and vehicle_id <= 0:
      raise HTTPException(status_code=422, detail="vehicle_id must be a positive integer")
    from_ts, to_ts = self._check_time_range(from_ts, to_ts)

    dao = TripDAO()
    items, count = dao.get_trips(limit, offset, vehicle_id, from_ts, to_ts)
    return {"items": items, "limit": limit, "offset": offset, "count": count}

  def get_trip_by_id(self, trip_id: int):
    if trip_id <= 0:
      raise HTTPException(status_code=400, detail="trip_id must be a positive integer")
    dao = TripDAO()
    result = dao.get_trip_by_id(trip_id)
    if result is None:
      raise HTTPException(status_code=404, detail="Trip not found")
    return result

  def update_trip(self, trip_id: int, payload: TripUpdate):
    if trip_id <= 0:
      raise HTTPException(status_code=400, detail="trip_id must be a positive integer")

    data = payload.model_dump(exclude_unset=True)
    if not data:
      raise HTTPException(status_code=422, detail="At least one updatable field is required")

    for field in ("vehicle_id", "start_ts", "end_ts"):
      if field in data and data[field] is None:
        raise HTTPException(status_code=422, detail=f"{field} cannot be null")

    if payload.vehicle_id is not None and payload.vehicle_id <= 0:
      raise HTTPException(status_code=422, detail="vehicle_id must be a positive integer")
    if payload.start_geom is not None:
      self._check_point(payload.start_geom, "start_geom")
    if payload.end_geom is not None:
      self._check_point(payload.end_geom, "end_geom")
    self._check_distance(payload.distance_km)

    if payload.start_ts is not None:
      payload.start_ts = _naive(payload.start_ts)
    if payload.end_ts is not None:
      payload.end_ts = _naive(payload.end_ts)

    try:
      dao = TripDAO()
      result = dao.update_trip(trip_id, payload)
    except LookupError as e:
      raise HTTPException(status_code=404, detail=f"{e.args[0]} does not exist")
    except ValueError as e:
      if e.args and e.args[0] == "end_ts":
        raise HTTPException(status_code=422, detail="end_ts must be later than start_ts")
      raise HTTPException(status_code=422, detail="Invalid payload")
    except Exception:
      raise HTTPException(status_code=422, detail="Malformed geometry or invalid JSON payload")

    if result is None:
      raise HTTPException(status_code=404, detail="Trip not found")
    return result

  def delete_trip(self, trip_id: int):
    if trip_id <= 0:
      raise HTTPException(status_code=400, detail="trip_id must be a positive integer")
    dao = TripDAO()
    deleted = dao.delete_trip(trip_id)
    if not deleted:
      raise HTTPException(status_code=404, detail="Trip not found")
    return {"message": "Trip deleted successfully.", "trip_id": trip_id}

  def get_vehicle_trips(
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

    dao = TripDAO()
    result = dao.get_vehicle_trips(vehicle_id, limit, offset, from_ts, to_ts)
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