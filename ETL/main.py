from load import FileAndQuery, load_tables
from initializes import reset_schema, _create_tables, sync_identity_sequences
import psycopg

conn = psycopg.connect(
    host="localhost",
    port= 5432,
    dbname="vehicle_database",
    user="user",
    password="password"
)

FilesAndQueries = [
    # (1) Fuel Type
    FileAndQuery(
        file="data/fuel_type.parquet",
        query="INSERT INTO fuel_type (fuel_type_id, name) VALUES (%s, %s)"
    ),
    # (2) Vehicle Kind
    FileAndQuery(
        file="data/vehicle_kind.parquet",
        query="INSERT INTO vehicle_kind (vehicle_kind_id, name) VALUES (%s, %s)"
    ),
    # (3) Vehicle Status
    FileAndQuery(
        file="data/vehicle_status.parquet",
        query="INSERT INTO vehicle_status (vehicle_status_id, name) VALUES (%s, %s)"
    ),
    # (4)  Vehicle Type
    FileAndQuery(
        file="data/vehicle_type.parquet",
        query="""INSERT INTO vehicle_type
                 (vehicle_type_id, vehicle_kind_id, fuel_type_id, emissions_rating, created_at)
                 VALUES (%s, %s, %s, %s, %s)"""
    ),
    # (5)
    FileAndQuery(
        file="data/vehicle.parquet",
        query="""INSERT INTO vehicle
                 (vehicle_id, vehicle_type_id, vehicle_status_id, plate_number, make, model, year, created_at)
                 VALUES (%s, %s, %s, %s, %s, %s, %s, %s)"""
    ),
    # (6) Driver
    FileAndQuery(
        file="data/driver.parquet",
        query="""INSERT INTO driver
                 (driver_id, first_name, last_name, license_number, hired_at)
                 VALUES (%s, %s, %s, %s, %s)""",
        rows_to_transform=["driver_id", "first_name", "last_name", "license_number", "hired_at"]
    ),
    # (7) Vehicle Assignment
    FileAndQuery(
        file="data/vehicle_assignment.parquet",
        query="""INSERT INTO vehicle_assignment
                 (assignment_id, vehicle_id, driver_id, assigned_from, assigned_to)
                 VALUES (%s, %s, %s, %s, %s)""",
        rows_to_transform=["assignment_id", "vehicle_id", "driver_id", "assigned_from", "assigned_to"]
    ),
    # (8)
    FileAndQuery(
        file="data/road_segment.parquet",
        query="""INSERT INTO road_segment
                 (road_id, name, speed_limit_kph, geom, created_at, is_oneway, direction)
                 VALUES (%s, %s, %s, %s, %s, %s, %s)""",
        rows_to_transform=["road_id", "name", "speed_limit_kph", "geom","created_at", "is_oneway","direction"]
    ),
    # (9) Parking Area
    FileAndQuery(
        file="data/parking_area.parquet",
        query="""INSERT INTO parking_area
                 (parking_area_id, name, capacity, geom, created_at)
                 VALUES (%s, %s, %s, %s, %s)""",
        rows_to_transform=["parking_area_id", "name", "capacity", "geom", "created_at"]
    ),
    # (10) Location Ping
    FileAndQuery(
        file="data/location_ping.parquet",
        query="""INSERT INTO location_ping
                 (ping_id, vehicle_id, ts, geom, speed_kph, heading_deg)
                 VALUES (%s, %s, %s, %s, %s, %s)""",
        rows_to_transform=["ping_id", "vehicle_id", "ts", "geom", "speed_kph", "heading_deg"]
    ),
    # (11) Trip
    FileAndQuery(
        file="data/trip.parquet",
        query="""
            INSERT INTO trip
            (trip_id, vehicle_id, start_ts, end_ts, start_geom, end_geom, distance_km)
            VALUES (%s, %s, %s, %s, %s, %s, %s)""",
        rows_to_transform=["trip_id", "vehicle_id", "start_ts", "end_ts", "start_geom", "end_geom", "distance_km"]
    ),
]

reset_schema(conn)
conn.commit()
# _create_tables(conn)
# conn.commit()
load_tables(conn, FilesAndQueries)
conn.commit()

sync_identity_sequences(conn)
conn.commit()

conn.close()