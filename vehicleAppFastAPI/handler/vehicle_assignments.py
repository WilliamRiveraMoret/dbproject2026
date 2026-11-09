from fastapi import HTTPException
from vehicleAppFastAPI.dao.vehicle_assignments import (
    VehicleAssignmentDAO,
    VehicleAssignmentCreate,
    VehicleAssignmentUpdate,
)


class VehicleAssignmentHandler:
    def create_assignment(self, payload: VehicleAssignmentCreate):
        if payload.vehicle_id <= 0 or payload.driver_id <= 0:
            raise HTTPException(status_code=400, detail="vehicle_id and driver_id must be positive integers")
        try:
            dao = VehicleAssignmentDAO()
            aid = dao.create_assignment(payload)
        except LookupError as e:
            raise HTTPException(status_code=404, detail=f"{e.args[0]} does not exist")
        except ArithmeticError:
            raise HTTPException(status_code=422, detail="assigned_to must be later than assigned_from")
        return dao.get_assignment_by_id(aid)

    def get_assignments(
        self,
        limit: int,
        offset: int,
        vehicle_id: int | None,
        driver_id: int | None,
        active: bool | None,
    ):
        if limit < 0 or offset < 0:
            raise HTTPException(status_code=400, detail="limit and offset must be non-negative")
        if vehicle_id is not None and vehicle_id <= 0:
            raise HTTPException(status_code=400, detail="vehicle_id must be a positive integer")
        if driver_id is not None and driver_id <= 0:
            raise HTTPException(status_code=400, detail="driver_id must be a positive integer")
        dao = VehicleAssignmentDAO()
        items, count = dao.get_assignments(limit, offset, vehicle_id, driver_id, active)
        return {"items": items, "limit": limit, "offset": offset, "count": count}

    def get_assignment_by_id(self, assignment_id: int):
        if assignment_id <= 0:
            raise HTTPException(status_code=400, detail="assignment_id must be a positive integer")
        dao = VehicleAssignmentDAO()
        result = dao.get_assignment_by_id(assignment_id)
        if result is None:
            raise HTTPException(status_code=404, detail="Vehicle assignment not found")
        return result

    def update_assignment(self, assignment_id: int, payload: VehicleAssignmentUpdate):
        if assignment_id <= 0:
            raise HTTPException(status_code=400, detail="assignment_id must be a positive integer")
        if not payload.model_dump(exclude_unset=True):
            raise HTTPException(status_code=400, detail="At least one updatable field is required")
        try:
            dao = VehicleAssignmentDAO()
            result = dao.update_assignment(assignment_id, payload)
        except LookupError as e:
            raise HTTPException(status_code=404, detail=f"{e.args[0]} does not exist")
        except ArithmeticError:
            raise HTTPException(status_code=422, detail="assigned_to must be later than assigned_from")

        if result is None:
            raise HTTPException(status_code=404, detail="Vehicle assignment not found")
        return result

    def delete_assignment(self, assignment_id: int):
        if assignment_id <= 0:
            raise HTTPException(status_code=400, detail="assignment_id must be a positive integer")
        dao = VehicleAssignmentDAO()
        ok = dao.delete_assignment(assignment_id)
        if not ok:
            raise HTTPException(status_code=404, detail="Vehicle assignment not found")
        return {"message": "Vehicle assignment deleted successfully.", "assignment_id": assignment_id}