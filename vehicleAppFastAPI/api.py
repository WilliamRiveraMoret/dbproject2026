from fastapi import FastAPI, Query, Response
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional

from dao.vehicles import VehicleCreate, VehicleUpdate
from handler.vehicles import VehicleHandler

from dao.drivers import DriverCreate, DriverUpdate
from handler.drivers import DriverHandler

from dao.vehicle_assignments import VehicleAssignmentCreate, VehicleAssignmentUpdate
from handler.vehicle_assignments import VehicleAssignmentHandler

from dao.road_segments import RoadSegmentCreate, RoadSegmentUpdate
from handler.road_segments import RoadSegmentHandler

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

API = "/api/v1"

# Vehicle
@app.post(f"{API}/vehicles", status_code=201)
async def create_vehicle(payload: VehicleCreate):
    return VehicleHandler().create_vehicle(payload)


@app.get(f"{API}/vehicles")
async def get_vehicles(
    limit: int = Query(20, ge=0),
    offset: int = Query(0, ge=0),
    status: Optional[str] = None,
    plate_number: Optional[str] = None,
):
    return VehicleHandler().get_vehicles(limit, offset, status, plate_number)


@app.get(f"{API}/vehicles/{{vehicle_id}}/current-location")
async def get_current_location(vehicle_id: int):
    result = VehicleHandler().get_current_location(vehicle_id)
    if isinstance(result, Response):
        return result
    return result


@app.get(f"{API}/vehicles/{{vehicle_id}}")
async def get_vehicle(vehicle_id: int):
    return VehicleHandler().get_vehicle_by_id(vehicle_id)


@app.put(f"{API}/vehicles/{{vehicle_id}}")
async def update_vehicle(vehicle_id: int, payload: VehicleUpdate):
    return VehicleHandler().update_vehicle(vehicle_id, payload)


@app.delete(f"{API}/vehicles/{{vehicle_id}}")
async def delete_vehicle(vehicle_id: int):
    return VehicleHandler().delete_vehicle(vehicle_id)



# Driver
@app.post(f"{API}/drivers", status_code=201)
async def create_driver(payload: DriverCreate):
    return DriverHandler().create_driver(payload)


@app.get(f"{API}/drivers")
async def get_drivers(
    limit: int = Query(20, ge=0),
    offset: int = Query(0, ge=0),
    name: Optional[str] = None,
    license_number: Optional[str] = None,
):
    return DriverHandler().get_drivers(limit, offset, name, license_number)


@app.get(f"{API}/drivers/{{driver_id}}")
async def get_driver(driver_id: int):
    return DriverHandler().get_driver_by_id(driver_id)


@app.put(f"{API}/drivers/{{driver_id}}")
async def update_driver(driver_id: int, payload: DriverUpdate):
    return DriverHandler().update_driver(driver_id, payload)


@app.delete(f"{API}/drivers/{{driver_id}}")
async def delete_driver(driver_id: int):
    return DriverHandler().delete_driver(driver_id)



# Vehicle Assignments
@app.post(f"{API}/vehicle-assignments", status_code=201)
async def create_vehicle_assignment(payload: VehicleAssignmentCreate):
    return VehicleAssignmentHandler().create_assignment(payload)


@app.get(f"{API}/vehicle-assignments")
async def get_vehicle_assignments(
    limit: int = Query(20, ge=0),
    offset: int = Query(0, ge=0),
    vehicle_id: Optional[int] = None,
    driver_id: Optional[int] = None,
    active: Optional[bool] = None,
):
    return VehicleAssignmentHandler().get_assignments(
        limit, offset, vehicle_id, driver_id, active
    )


@app.get(f"{API}/vehicle-assignments/{{assignment_id}}")
async def get_vehicle_assignment(assignment_id: int):
    return VehicleAssignmentHandler().get_assignment_by_id(assignment_id)


@app.put(f"{API}/vehicle-assignments/{{assignment_id}}")
async def update_vehicle_assignment(assignment_id: int, payload: VehicleAssignmentUpdate):
    return VehicleAssignmentHandler().update_assignment(assignment_id, payload)


@app.delete(f"{API}/vehicle-assignments/{{assignment_id}}")
async def delete_vehicle_assignment(assignment_id: int):
    return VehicleAssignmentHandler().delete_assignment(assignment_id)

# Road Segments
@app.post(f"{API}/road-segments", status_code=201)
async def create_road_segment(payload: RoadSegmentCreate):
    return RoadSegmentHandler().create_road_segment(payload)

@app.get(f"{API}/road-segments")
async def get_road_segments(
    limit: int = Query(20, ge=0),
    offset: int = Query(0, ge=0),
    bbox: Optional[str] = None,
    name: Optional[str] = None,
    min_speed_kph: Optional[float] = None,
    max_speed_kph: Optional[float] = None,
):
    return RoadSegmentHandler().get_road_segments(limit, offset, bbox, name, min_speed_kph, max_speed_kph)

@app.get(f"{API}/road-segments/geojson", response_class=Response)
async def get_road_segments_geojson(
    limit: int = Query(15000, ge=0),
    offset: int = Query(0, ge=0),
    name: Optional[str] = None,
    min_speed_kph: Optional[float] = None,
    max_speed_kph: Optional[float] = None,
):
    import json
    data = RoadSegmentHandler().get_geojson(limit, offset, name, min_speed_kph, max_speed_kph)

    return Response(content=json.dumps(data), media_type="application/geo+json")

@app.get(f"{API}/road-segments/{{road_id}}")
async def get_road_segment(road_id: int):
    return RoadSegmentHandler().get_road_segment_by_id(road_id)

@app.put(f"{API}/road-segments/{{road_id}}")
async def update_road_segment(road_id: int, payload: RoadSegmentUpdate):
    return RoadSegmentHandler().update_road_segment(road_id, payload)

@app.delete(f"{API}/road-segments/{{road_id}}")
async def delete_road_segment(road_id: int):
    return RoadSegmentHandler().delete_road_segment(road_id)