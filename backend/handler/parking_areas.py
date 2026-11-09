from fastapi import HTTPException
from backend.dao.parking_areas import ParkingAreaDAO, ParkingAreaCreate, ParkingAreaUpdate


class ParkingAreaHandler:
    def create_parking_area(self, payload: ParkingAreaCreate):
        if not payload.name.strip():
            raise HTTPException(status_code=400, detail="name is required and must be non-empty")
        
        if payload.capacity is not None and payload.capacity < 0:
            raise HTTPException(status_code=400, detail="capacity must be greater than or equal to 0")
        
        if not payload.geom or payload.geom.get("type") != "Polygon":
            raise HTTPException(status_code=400, detail="geom is required and must be a valid Polygon")

        try:
            dao = ParkingAreaDAO()
            parking_area_id = dao.create_parking_area(payload)
            return dao.get_parking_area_by_id(parking_area_id)
        except Exception:
            raise HTTPException(status_code=400, detail="Malformed geometry or invalid JSON payload")

    def get_parking_areas(self, limit: int, offset: int, bbox_str: str | None, name: str | None):
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

        dao = ParkingAreaDAO()
        items, count = dao.get_parking_areas(limit, offset, bbox, name)
        
        return {
            "items": items,
            "limit": limit,
            "offset": offset,
            "count": count
        }

    def get_parking_area_by_id(self, parking_area_id: int):
        if parking_area_id <= 0:
            raise HTTPException(status_code=400, detail="parking_area_id must be a positive integer")
            
        dao = ParkingAreaDAO()
        result = dao.get_parking_area_by_id(parking_area_id)
        if result is None:
            raise HTTPException(status_code=404, detail="Parking area not found")
        return result

    def update_parking_area(self, parking_area_id: int, payload: ParkingAreaUpdate):
        if parking_area_id <= 0:
            raise HTTPException(status_code=400, detail="parking_area_id must be a positive integer")
        
        if not payload.model_dump(exclude_unset=True):
            raise HTTPException(status_code=400, detail="At least one updatable field must be present")
            
        if payload.capacity is not None and payload.capacity < 0:
            raise HTTPException(status_code=400, detail="capacity must be >= 0")
            
        if payload.geom is not None and payload.geom.get("type") != "Polygon":
            raise HTTPException(status_code=400, detail="geom must remain a valid Polygon")
            
        try:
            dao = ParkingAreaDAO()
            result = dao.update_parking_area(parking_area_id, payload)
        except Exception:
            raise HTTPException(status_code=400, detail="Malformed geometry or invalid JSON payload")

        if result is None:
            raise HTTPException(status_code=404, detail="Parking area not found")
        return result

    def delete_parking_area(self, parking_area_id: int):
        if parking_area_id <= 0:
            raise HTTPException(status_code=400, detail="parking_area_id must be a positive integer")
            
        dao = ParkingAreaDAO()
        deleted = dao.delete_parking_area(parking_area_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Parking area not found")
            
        return {"message": "Parking area deleted successfully.", "parking_area_id": parking_area_id}