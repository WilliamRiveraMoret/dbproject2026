from fastapi import FastAPI, Query, Response
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional
from datetime import datetime

from vehicleAppFastAPI.dao.vehicles import VehicleCreate, VehicleUpdate
from vehicleAppFastAPI.handler.vehicles import VehicleHandler

from vehicleAppFastAPI.dao.drivers import DriverCreate, DriverUpdate
from vehicleAppFastAPI.handler.drivers import DriverHandler

from vehicleAppFastAPI.dao.vehicle_assignments import VehicleAssignmentCreate, VehicleAssignmentUpdate
from vehicleAppFastAPI.handler.vehicle_assignments import VehicleAssignmentHandler

from vehicleAppFastAPI.dao.road_segments import RoadSegmentCreate, RoadSegmentUpdate
from vehicleAppFastAPI.handler.road_segments import RoadSegmentHandler

from vehicleAppFastAPI.handler.parking_areas import ParkingAreaHandler
from vehicleAppFastAPI.dao.parking_areas import ParkingAreaCreate, ParkingAreaUpdate

from vehicleAppFastAPI.dao.location_ping import LocationPingCreate, LocationPingUpdate
from vehicleAppFastAPI.handler.location_ping import LocationPingHandler

from vehicleAppFastAPI.dao.trips import TripCreate, TripUpdate
from vehicleAppFastAPI.handler.trips import TripHandler

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

# Parking Areas
@app.post(f"{API}/parking-areas", status_code=201)
async def create_parking_area(payload: ParkingAreaCreate):
    return ParkingAreaHandler().create_parking_area(payload)

@app.get(f"{API}/parking-areas")
async def get_parking_areas(
    limit: int = Query(20, ge=0),
    offset: int = Query(0, ge=0),
    bbox: Optional[str] = None,
    name: Optional[str] = None,
):
    return ParkingAreaHandler().get_parking_areas(limit, offset, bbox, name)

@app.get(f"{API}/parking-areas/{{parking_area_id}}")
async def get_parking_area(parking_area_id: int):
    return ParkingAreaHandler().get_parking_area_by_id(parking_area_id)

@app.put(f"{API}/parking-areas/{{parking_area_id}}")
async def update_parking_area(parking_area_id: int, payload: ParkingAreaUpdate):
    return ParkingAreaHandler().update_parking_area(parking_area_id, payload)

@app.delete(f"{API}/parking-areas/{{parking_area_id}}")
async def delete_parking_area(parking_area_id: int):
    return ParkingAreaHandler().delete_parking_area(parking_area_id)

# Location Pings
@app.post(f"{API}/location-pings", status_code=201)
async def create_location_ping(payload: LocationPingCreate):
    return LocationPingHandler().create_ping(payload)
 
 
@app.get(f"{API}/location-pings")
async def get_location_pings(
    limit: int = Query(20, ge=0),
    offset: int = Query(0, ge=0),
    vehicle_id: Optional[int] = None,
    from_ts: Optional[datetime] = None,
    to_ts: Optional[datetime] = None,
    bbox: Optional[str] = None,
):
    return LocationPingHandler().get_pings(limit, offset, vehicle_id, from_ts, to_ts, bbox)
 
 
@app.get(f"{API}/location-pings/{{ping_id}}")
async def get_location_ping(ping_id: int):
    return LocationPingHandler().get_ping_by_id(ping_id)
 
 
@app.put(f"{API}/location-pings/{{ping_id}}")
async def update_location_ping(ping_id: int, payload: LocationPingUpdate):
    return LocationPingHandler().update_ping(ping_id, payload)
 
 
@app.delete(f"{API}/location-pings/{{ping_id}}")
async def delete_location_ping(ping_id: int):
    return LocationPingHandler().delete_ping(ping_id)
 
 
@app.get(f"{API}/vehicles/{{vehicle_id}}/pings")
async def get_vehicle_pings(
    vehicle_id: int,
    limit: int = Query(20, ge=0),
    offset: int = Query(0, ge=0),
    from_ts: Optional[datetime] = None,
    to_ts: Optional[datetime] = None,
):
    return LocationPingHandler().get_vehicle_pings(vehicle_id, limit, offset, from_ts, to_ts)

#Trips
@app.post(f"{API}/trips", status_code=201)
async def create_trip(payload: TripCreate):
    return TripHandler().create_trip(payload)
 
 
@app.get(f"{API}/trips")
async def get_trips(
    limit: int = Query(20, ge=0),
    offset: int = Query(0, ge=0),
    vehicle_id: Optional[int] = None,
    from_ts: Optional[datetime] = None,
    to_ts: Optional[datetime] = None,
):
    return TripHandler().get_trips(limit, offset, vehicle_id, from_ts, to_ts)
 
 
@app.get(f"{API}/trips/{{trip_id}}")
async def get_trip(trip_id: int):
    return TripHandler().get_trip_by_id(trip_id)
 
 
@app.put(f"{API}/trips/{{trip_id}}")
async def update_trip(trip_id: int, payload: TripUpdate):
    return TripHandler().update_trip(trip_id, payload)
 
 
@app.delete(f"{API}/trips/{{trip_id}}")
async def delete_trip(trip_id: int):
    return TripHandler().delete_trip(trip_id)
 
 
@app.get(f"{API}/vehicles/{{vehicle_id}}/trips")
async def get_vehicle_trips(
    vehicle_id: int,
    limit: int = Query(20, ge=0),
    offset: int = Query(0, ge=0),
    from_ts: Optional[datetime] = None,
    to_ts: Optional[datetime] = None,
):
    return TripHandler().get_vehicle_trips(vehicle_id, limit, offset, from_ts, to_ts)