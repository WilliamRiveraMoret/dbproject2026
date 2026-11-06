from fastapi import HTTPException
from dao.vehicles import (
    VehicleDAO,
    VehicleCreate,
    VehicleUpdate,
    VehicleResponse,
    CurrentLocationResponse,
)


class VehicleHandler:
    def create_vehicle(self, payload: VehicleCreate):
        # basic validation
        if not payload.plate_number or not payload.plate_number.strip():
            raise HTTPException(status_code=400, detail="plate_number must be non-empty")
        if payload.year < 1950 or payload.year > 2100:
            raise HTTPException(status_code=400, detail="year must be between 1950 and 2100")

        try:
            dao = VehicleDAO()
            vehicle_id = dao.create_vehicle(payload)
        except LookupError as e:
            raise HTTPException(status_code=404, detail=f"{e.args[0]} does not exist")
        except ValueError:
            raise HTTPException(status_code=409, detail="plate_number already exists")

        return dao.get_vehicle_by_id(vehicle_id)

    def get_vehicles(self, limit: int, offset: int, status: str | None, plate_number: str | None):
        if limit < 0 or offset < 0:
            raise HTTPException(status_code=400, detail="limit and offset must be non-negative")
        dao = VehicleDAO()
        items, count = dao.get_vehicles(limit, offset, status, plate_number)
        return {"items": items, "limit": limit, "offset": offset, "count": count}

    def get_vehicle_by_id(self, vehicle_id: int):
        if vehicle_id <= 0:
            raise HTTPException(status_code=400, detail="vehicle_id must be a positive integer")
        dao = VehicleDAO()
        result = dao.get_vehicle_by_id(vehicle_id)
        if result is None:
            raise HTTPException(status_code=404, detail="Vehicle not found")
        return result

    def update_vehicle(self, vehicle_id: int, payload: VehicleUpdate):
        if vehicle_id <= 0:
            raise HTTPException(status_code=400, detail="vehicle_id must be a positive integer")
        if not payload.model_dump(exclude_unset=True):
            raise HTTPException(status_code=400, detail="At least one updatable field is required")
        if payload.year is not None and (payload.year < 1950 or payload.year > 2100):
            raise HTTPException(status_code=400, detail="year must be between 1950 and 2100")

        try:
            dao = VehicleDAO()
            result = dao.update_vehicle(vehicle_id, payload)
        except LookupError as e:
            raise HTTPException(status_code=404, detail=f"{e.args[0]} does not exist")
        except ValueError as e:
            if e.args and e.args[0] == "plate_number":
                raise HTTPException(status_code=409, detail="plate_number conflicts with another vehicle")
            raise HTTPException(status_code=400, detail="Invalid payload")

        if result is None:
            raise HTTPException(status_code=404, detail="Vehicle not found")
        return result

    def delete_vehicle(self, vehicle_id: int):
        if vehicle_id <= 0:
            raise HTTPException(status_code=400, detail="vehicle_id must be a positive integer")
        dao = VehicleDAO()
        result = dao.delete_vehicle(vehicle_id)
        if result == "not_found":
            raise HTTPException(status_code=404, detail="Vehicle not found")
        if result == "conflict":
            raise HTTPException(
                status_code=409,
                detail="Vehicle is referenced by location_ping, trip, or vehicle_assignment",
            )
        return {"message": "Vehicle deleted successfully.", "vehicle_id": vehicle_id}

    def get_current_location(self, vehicle_id: int):
        if vehicle_id <= 0:
            raise HTTPException(status_code=400, detail="vehicle_id must be a positive integer")
        dao = VehicleDAO()
        result = dao.get_current_location(vehicle_id)
        if result is None:
            raise HTTPException(status_code=404, detail="Vehicle not found")
        if result.last_ts is None:
            # Vehicle exists but no pings yet
            from fastapi.responses import Response
            return Response(status_code=204)
        return result