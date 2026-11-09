from fastapi import HTTPException
from vehicleAppFastAPI.dao.road_segments import RoadSegmentDAO, RoadSegmentCreate, RoadSegmentUpdate


class RoadSegmentHandler:
    def create_road_segment(self, payload: RoadSegmentCreate):
        if not payload.name.strip():
            raise HTTPException(status_code=400, detail="name is required and must be non-empty")
        
        if payload.speed_limit_kph is not None and payload.speed_limit_kph < 0:
            raise HTTPException(status_code=400, detail="speed_limit_kph must be greater than or equal to 0")
        
        if payload.direction not in ["both", "forward"]:
            raise HTTPException(status_code=400, detail="direction must be 'both' or 'forward'")
        
        if not payload.geom or payload.geom.get("type") != "LineString":
            raise HTTPException(status_code=400, detail="geom is required and must be a valid LineString")

        try:
            dao = RoadSegmentDAO()
            road_id = dao.create_road_segment(payload)
            return dao.get_road_segment_by_id(road_id)
        except Exception as e:
            raise HTTPException(status_code=400, detail="Malformed geometry or invalid payload shape")

    def get_road_segments(self, limit: int, offset: int, bbox_str: str | None, name: str | None, min_speed: float | None, max_speed: float | None):
        if limit < 0 or offset < 0:
            raise HTTPException(status_code=400, detail="limit and offset must be non-negative integers")
        
        bbox = None
        if bbox_str:
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
                bbox = (minLon, minLat, maxLon, maxLat)
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid bbox format or range. Expected minLon,minLat,maxLon,maxLat")

        if min_speed is not None and max_speed is not None and min_speed > max_speed:
            raise HTTPException(status_code=400, detail="min_speed_kph cannot exceed max_speed_kph")

        dao = RoadSegmentDAO()
        items, count = dao.get_road_segments(limit, offset, bbox, name, min_speed, max_speed)
        
        return {
            "items": items,
            "limit": limit,
            "offset": offset,
            "count": count
        }

    def get_road_segment_by_id(self, road_id: int):
        if road_id <= 0:
            raise HTTPException(status_code=400, detail="road_id must be a positive integer")
            
        dao = RoadSegmentDAO()
        result = dao.get_road_segment_by_id(road_id)
        if result is None:
            raise HTTPException(status_code=404, detail="Road segment not found")
        return result

    def update_road_segment(self, road_id: int, payload: RoadSegmentUpdate):
        if road_id <= 0:
            raise HTTPException(status_code=400, detail="road_id must be a positive integer")
        
        if not payload.model_dump(exclude_unset=True):
            raise HTTPException(status_code=400, detail="At least one updatable field must be present")
            
        if payload.speed_limit_kph is not None and payload.speed_limit_kph < 0:
            raise HTTPException(status_code=400, detail="speed_limit_kph must be >= 0")
            
        if payload.geom is not None and payload.geom.get("type") != "LineString":
            raise HTTPException(status_code=400, detail="geom must remain a valid LineString")
            
        try:
            dao = RoadSegmentDAO()
            result = dao.update_road_segment(road_id, payload)
        except Exception:
            raise HTTPException(status_code=400, detail="Malformed geometry or invalid JSON payload")

        if result is None:
            raise HTTPException(status_code=404, detail="Road segment not found")
        return result

    def delete_road_segment(self, road_id: int):
        if road_id <= 0:
            raise HTTPException(status_code=400, detail="road_id must be a positive integer")
            
        dao = RoadSegmentDAO()
        deleted = dao.delete_road_segment(road_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Road segment not found")
            
        return {"message": "Road segment deleted successfully.", "road_id": road_id}

    def get_geojson(self, limit: int, offset: int, name: str | None, min_speed_kph: float | None, max_speed_kph: float | None):
        if limit < 0 or offset < 0:
            raise HTTPException(status_code=400, detail="limit and offset must be non-negative integers")
            
        if min_speed_kph is not None and max_speed_kph is not None and min_speed_kph > max_speed_kph:
            raise HTTPException(status_code=400, detail="min_speed_kph cannot exceed max_speed_kph")

        dao = RoadSegmentDAO()
        items, count = dao.get_road_segments(limit, offset, bbox=None, name=name, min_speed_kph=min_speed_kph, max_speed_kph=max_speed_kph)
        
        features = []
        for item in items:
            features.append({
                "type": "Feature",
                "geometry": item.geom,
                "properties": {
                    "road_id": item.road_id,
                    "name": item.name,
                    "speed_limit_kph": item.speed_limit_kph,
                    "is_oneway": item.is_oneway,
                    "direction": item.direction,
                    "created_at": item.created_at.isoformat() + "Z" if item.created_at else None
                }
            })
            
        return {
            "type": "FeatureCollection",
            "count": count,
            "limit": limit,
            "offset": offset,
            "features": features
        }