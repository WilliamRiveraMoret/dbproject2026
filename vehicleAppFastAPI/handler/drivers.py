from fastapi import HTTPException
from dao.drivers import DriverDAO, DriverCreate, DriverUpdate


class DriverHandler:
    def create_driver(self, payload: DriverCreate):
        for field in ("first_name", "last_name", "license_number"):
            v = getattr(payload, field)
            if v is None or not v.strip():
                raise HTTPException(status_code=422, detail=f"{field} is required and non-empty")
        try:
            dao = DriverDAO()
            driver_id = dao.create_driver(payload)
        except ValueError:
            raise HTTPException(status_code=409, detail="license_number already exists")
        return dao.get_driver_by_id(driver_id)

    def get_drivers(self, limit: int, offset: int, name: str | None, license_number: str | None):
        if limit < 0 or offset < 0:
            raise HTTPException(status_code=400, detail="limit and offset must be non-negative")
        dao = DriverDAO()
        items, count = dao.get_drivers(limit, offset, name, license_number)
        return {"items": items, "limit": limit, "offset": offset, "count": count}

    def get_driver_by_id(self, driver_id: int):
        if driver_id <= 0:
            raise HTTPException(status_code=400, detail="driver_id must be a positive integer")
        dao = DriverDAO()
        result = dao.get_driver_by_id(driver_id)
        if result is None:
            raise HTTPException(status_code=404, detail="Driver not found")
        return result

    def update_driver(self, driver_id: int, payload: DriverUpdate):
        if driver_id <= 0:
            raise HTTPException(status_code=400, detail="driver_id must be a positive integer")
        if not payload.model_dump(exclude_unset=True):
            raise HTTPException(status_code=400, detail="At least one updatable field is required")

        for field in ("first_name", "last_name", "license_number"):
            v = getattr(payload, field)
            if v is not None and not v.strip():
                raise HTTPException(status_code=422, detail=f"{field} cannot be empty")

        try:
            dao = DriverDAO()
            result = dao.update_driver(driver_id, payload)
        except ValueError:
            raise HTTPException(status_code=409, detail="license_number conflicts with another driver")

        if result is None:
            raise HTTPException(status_code=404, detail="Driver not found")
        return result

    def delete_driver(self, driver_id: int):
        if driver_id <= 0:
            raise HTTPException(status_code=400, detail="driver_id must be a positive integer")
        dao = DriverDAO()
        result = dao.delete_driver(driver_id)
        if result == "not_found":
            raise HTTPException(status_code=404, detail="Driver not found")
        if result == "conflict":
            raise HTTPException(
                status_code=409,
                detail="Driver is referenced by a vehicle assignment",
            )
        return {"message": "Driver deleted successfully.", "driver_id": driver_id}