"""
Project source: src/rhino7/SunlightEnvelope_Rhino7_GhPython.py

Rhino 7 Grasshopper GhPython Script Component
IronPython 2.7

GhPython input parameter access settings
----------------------------------------
Boundary    : Item Access
Context     : List Access
North       : Item Access
Latitude    : Item Access
Longitude   : Item Access
TimeZone    : Item Access
Month       : Item Access
Day         : Item Access
StartHour   : Item Access
EndHour     : Item Access
TimeStep    : Item Access
GridSize    : Item Access
HeightStep  : Item Access
MaxHeight   : Item Access
Run         : Item Access

GhPython output parameter names
-------------------------------
P
H
I

Purpose
-------
Generate three-dimensional sample points inside a site boundary and calculate
the accumulated direct-sun duration at every sample point.

Python responsibilities
-----------------------
1. Validate inputs.
2. Generate sample points by horizontal layer.
3. Calculate sun vectors for the specified date and time range.
4. Test direct-sun obstruction against context geometry.
5. Output sample points and sun hours as matching Grasshopper Data Trees.

Python does NOT
---------------
1. Decide whether a point is compliant.
2. Apply a sunlight threshold.
3. Dispatch pass/fail points.
4. Generate voxels or final design geometry.

Inputs
------
Boundary    : Curve
Context     : List[Geometry]
North       : Vector3d
Latitude    : float, degrees
Longitude   : float, degrees; east positive, west negative
TimeZone    : float, UTC offset hours
Month       : int
Day         : int
StartHour   : float, local clock hour
EndHour     : float, local clock hour
TimeStep    : float, minutes
GridSize    : float, model units
HeightStep  : float, model units
MaxHeight   : float, model units
Run         : bool

Outputs
-------
P : DataTree[Point3d]
    One branch per height layer.

H : DataTree[float]
    Accumulated direct-sun hours matching P exactly.

I : List[str]
    Status, statistics, assumptions, and validation messages.
"""

import math
import time
from datetime import datetime, timedelta

import Rhino
import Rhino.Geometry as rg
import scriptcontext as sc

from Grasshopper import DataTree
from Grasshopper.Kernel.Data import GH_Path


# =============================================================================
# CONSTANTS
# =============================================================================

EPSILON = 1.0e-9
RAY_ORIGIN_OFFSET = 1.0e-6
DEFAULT_YEAR = 2024
MAX_SAMPLE_POINTS = 2000000
PROGRESS_CHECK_INTERVAL = 2000


# =============================================================================
# OUTPUT INITIALIZATION
# =============================================================================

P = DataTree[object]()
H = DataTree[object]()
I = []


# =============================================================================
# BASIC HELPERS
# =============================================================================

def is_finite_number(value):
    """Return True when value can be converted to a finite float."""
    try:
        number = float(value)
        return not math.isnan(number) and not math.isinf(number)
    except Exception:
        return False


def clamp(value, minimum, maximum):
    """Clamp a numeric value to an inclusive range."""
    return max(minimum, min(maximum, value))


def format_number(value, digits=3):
    """Format a number for Grasshopper Panel output."""
    try:
        return ("{0:." + str(digits) + "f}").format(float(value))
    except Exception:
        return str(value)


def geometry_type_name(geometry):
    """Return a readable geometry type name."""
    if geometry is None:
        return "None"

    try:
        return geometry.GetType().Name
    except Exception:
        return type(geometry).__name__


def check_escape_key():
    """
    Return True when Rhino reports that the Escape key was pressed.

    This allows very large calculations to be interrupted without requiring
    the Grasshopper document to be closed.
    """
    try:
        return bool(sc.escape_test(False))
    except Exception:
        return False


def timedelta_to_seconds(delta):
    """
    Return total seconds without relying on timedelta division.

    This form is compatible with IronPython 2.7 and also preserves
    microseconds.
    """
    return (
        delta.days * 86400.0 +
        delta.seconds +
        delta.microseconds / 1000000.0
    )


# =============================================================================
# INPUT VALIDATION
# =============================================================================

def validate_date(month, day):
    """
    Validate month and day using a leap year so February 29 is accepted.

    Returns
    -------
    datetime
        Midnight on the validated date.
    """
    return datetime(DEFAULT_YEAR, int(month), int(day), 0, 0, 0)


def validate_boundary(boundary):
    """
    Validate the site boundary and retrieve its working plane.

    The current implementation expects a closed planar boundary whose plane is
    approximately horizontal. This keeps vertical sampling aligned with Rhino Z.
    """
    errors = []
    boundary_plane = None

    if boundary is None:
        errors.append("Boundary is missing.")
        return errors, boundary_plane

    if not isinstance(boundary, rg.Curve):
        errors.append(
            "Boundary must be a Rhino curve. Received: {0}.".format(
                geometry_type_name(boundary)
            )
        )
        return errors, boundary_plane

    if not boundary.IsValid:
        errors.append("Boundary curve is invalid.")

    if not boundary.IsClosed:
        errors.append("Boundary curve must be closed.")

    try:
        success, plane = boundary.TryGetPlane()
    except Exception:
        success = False
        plane = None

    if not success or plane is None:
        errors.append("Boundary curve must be planar.")
        return errors, boundary_plane

    normal = rg.Vector3d(plane.Normal)

    if not normal.Unitize():
        errors.append("Boundary plane has an invalid normal vector.")
        return errors, boundary_plane

    vertical_alignment = abs(normal * rg.Vector3d.ZAxis)

    if vertical_alignment < 0.999:
        errors.append(
            "Boundary plane must be approximately horizontal and aligned "
            "with Rhino World XY."
        )
        return errors, boundary_plane

    if normal.Z < 0.0:
        plane.Flip()

    boundary_plane = plane
    return errors, boundary_plane


def validate_numeric_inputs(
    latitude,
    longitude,
    timezone,
    month,
    day,
    start_hour,
    end_hour,
    time_step,
    grid_size,
    height_step,
    max_height
):
    """Validate all non-geometric inputs."""
    errors = []
    warnings = []

    numeric_values = {
        "Latitude": latitude,
        "Longitude": longitude,
        "TimeZone": timezone,
        "Month": month,
        "Day": day,
        "StartHour": start_hour,
        "EndHour": end_hour,
        "TimeStep": time_step,
        "GridSize": grid_size,
        "HeightStep": height_step,
        "MaxHeight": max_height
    }

    for name, value in numeric_values.items():
        if not is_finite_number(value):
            errors.append("{0} must be a finite number.".format(name))

    if errors:
        return errors, warnings

    latitude = float(latitude)
    longitude = float(longitude)
    timezone = float(timezone)
    start_hour = float(start_hour)
    end_hour = float(end_hour)
    time_step = float(time_step)
    grid_size = float(grid_size)
    height_step = float(height_step)
    max_height = float(max_height)

    try:
        month_integer = int(month)
        day_integer = int(day)

        if abs(float(month) - month_integer) > EPSILON:
            errors.append("Month must be an integer.")

        if abs(float(day) - day_integer) > EPSILON:
            errors.append("Day must be an integer.")

        if not errors:
            validate_date(month_integer, day_integer)

    except Exception:
        errors.append("Month and Day do not form a valid calendar date.")

    if latitude < -90.0 or latitude > 90.0:
        errors.append("Latitude must be between -90 and 90 degrees.")

    if longitude < -180.0 or longitude > 180.0:
        errors.append("Longitude must be between -180 and 180 degrees.")

    if timezone < -14.0 or timezone > 14.0:
        errors.append("TimeZone must be between UTC-14 and UTC+14.")

    if start_hour < 0.0 or start_hour > 24.0:
        errors.append("StartHour must be between 0 and 24.")

    if end_hour < 0.0 or end_hour > 24.0:
        errors.append("EndHour must be between 0 and 24.")

    if end_hour <= start_hour:
        errors.append("EndHour must be greater than StartHour.")

    if time_step <= 0.0:
        errors.append("TimeStep must be greater than zero minutes.")

    if grid_size <= 0.0:
        errors.append("GridSize must be greater than zero.")

    if height_step <= 0.0:
        errors.append("HeightStep must be greater than zero.")

    if max_height <= 0.0:
        errors.append("MaxHeight must be greater than zero.")

    if time_step > 240.0:
        warnings.append(
            "TimeStep is larger than 240 minutes; solar results may be coarse."
        )

    document = Rhino.RhinoDoc.ActiveDoc

    if document is not None:
        document_tolerance = max(
            document.ModelAbsoluteTolerance,
            EPSILON
        )
    else:
        document_tolerance = 0.001

    if grid_size < document_tolerance:
        warnings.append(
            "GridSize is smaller than the Rhino document absolute tolerance."
        )

    if height_step < document_tolerance:
        warnings.append(
            "HeightStep is smaller than the Rhino document absolute tolerance."
        )

    return errors, warnings


def validate_and_normalize_north(north):
    """
    Validate North and return normalized horizontal north and east vectors.

    Azimuth convention
    ------------------
    0 degrees   = north
    90 degrees  = east
    180 degrees = south
    270 degrees = west
    """
    errors = []

    if north is None:
        errors.append("North vector is missing.")
        return errors, None, None

    try:
        north_vector = rg.Vector3d(north)
    except Exception:
        errors.append("North must be convertible to Rhino Vector3d.")
        return errors, None, None

    north_vector.Z = 0.0

    if north_vector.IsTiny(EPSILON):
        errors.append(
            "North vector must have a non-zero horizontal XY component."
        )
        return errors, None, None

    if not north_vector.Unitize():
        errors.append("North vector could not be normalized.")
        return errors, None, None

    east_vector = rg.Vector3d.CrossProduct(
        north_vector,
        rg.Vector3d.ZAxis
    )

    if east_vector.IsTiny(EPSILON) or not east_vector.Unitize():
        errors.append("East vector could not be derived from North.")
        return errors, None, None

    return errors, north_vector, east_vector


# =============================================================================
# CONTEXT GEOMETRY CONVERSION
# =============================================================================

def mesh_from_brep(brep):
    """Create analysis meshes from a Brep."""
    meshes = []

    if brep is None or not brep.IsValid:
        return meshes

    try:
        created = rg.Mesh.CreateFromBrep(
            brep,
            rg.MeshingParameters.FastRenderMesh
        )

        if created:
            for mesh in created:
                if mesh is not None and mesh.IsValid:
                    meshes.append(mesh)

    except Exception:
        pass

    return meshes


def convert_geometry_to_meshes(geometry):
    """
    Convert a supported Rhino geometry object into one or more meshes.

    Supported inputs include Mesh, Brep, Extrusion, and Surface.
    SubD is deliberately ignored for stable Rhino 7 compatibility.
    Unsupported objects are reported but ignored.
    """
    meshes = []

    if geometry is None:
        return meshes

    if isinstance(geometry, rg.Mesh):
        if geometry.IsValid:
            duplicate = geometry.DuplicateMesh()
            if duplicate is not None and duplicate.IsValid:
                meshes.append(duplicate)
        return meshes

    if isinstance(geometry, rg.Brep):
        return mesh_from_brep(geometry)

    if isinstance(geometry, rg.Extrusion):
        try:
            brep = geometry.ToBrep()
            return mesh_from_brep(brep)
        except Exception:
            return meshes

    if isinstance(geometry, rg.Surface):
        try:
            brep = geometry.ToBrep()
            return mesh_from_brep(brep)
        except Exception:
            return meshes

    return meshes


def build_context_mesh(context_geometry):
    """
    Convert all context geometry into one joined analysis mesh.

    Returns
    -------
    Mesh or None
        Joined context mesh.

    list[str]
        Warnings for unsupported or invalid geometry.

    int
        Number of source meshes appended.
    """
    warnings = []
    source_mesh_count = 0
    joined_mesh = rg.Mesh()

    if context_geometry is None:
        return None, warnings, source_mesh_count

    if isinstance(context_geometry, (list, tuple)):
        geometries = list(context_geometry)
    else:
        try:
            geometries = list(context_geometry)
        except Exception:
            geometries = [context_geometry]

    for index, geometry in enumerate(geometries):
        if geometry is None:
            continue

        if geometry_type_name(geometry) == "SubD":
            warnings.append(
                "Context item {0} is a SubD and was safely ignored. "
                "Convert it to a Mesh or Brep before input for stable "
                "Rhino 7 GhPython support.".format(index)
            )
            continue

        converted = convert_geometry_to_meshes(geometry)

        if not converted:
            warnings.append(
                "Context item {0} was ignored because it could not be "
                "converted to a valid mesh. Type: {1}.".format(
                    index,
                    geometry_type_name(geometry)
                )
            )
            continue

        for mesh in converted:
            try:
                joined_mesh.Append(mesh)
                source_mesh_count += 1
            except Exception:
                warnings.append(
                    "Context mesh generated from item {0} could not be "
                    "appended.".format(index)
                )

    if source_mesh_count == 0:
        return None, warnings, source_mesh_count

    try:
        joined_mesh.Vertices.CombineIdentical(True, True)
    except Exception:
        pass

    try:
        joined_mesh.Faces.CullDegenerateFaces()
    except Exception:
        pass

    try:
        joined_mesh.Compact()
    except Exception:
        pass

    if not joined_mesh.IsValid or joined_mesh.Faces.Count == 0:
        warnings.append(
            "The joined context mesh is invalid or contains no faces. "
            "Obstruction testing will be skipped."
        )
        return None, warnings, 0

    return joined_mesh, warnings, source_mesh_count


# =============================================================================
# SAMPLE POINT GENERATION
# =============================================================================

def estimate_sample_count(boundary, grid_size, height_step, max_height):
    """
    Estimate the upper bound of sample points using the boundary bounding box.

    This is intentionally conservative because only points inside the boundary
    will actually be retained.
    """
    bounding_box = boundary.GetBoundingBox(True)

    width = max(0.0, bounding_box.Max.X - bounding_box.Min.X)
    depth = max(0.0, bounding_box.Max.Y - bounding_box.Min.Y)

    x_count = max(1, int(math.ceil(width / grid_size)))
    y_count = max(1, int(math.ceil(depth / grid_size)))
    layer_count = max(1, int(math.ceil(max_height / height_step)))

    estimated_count = x_count * y_count * layer_count

    return estimated_count, x_count, y_count, layer_count


def point_inside_boundary(boundary, boundary_plane, point, tolerance):
    """
    Return True when a point is inside or on the site boundary.

    The point is projected onto the boundary plane before containment testing.
    """
    projected = boundary_plane.ClosestPoint(point)

    containment = boundary.Contains(
        projected,
        boundary_plane,
        tolerance
    )

    return (
        containment == rg.PointContainment.Inside or
        containment == rg.PointContainment.Coincident
    )


def generate_plan_sample_points(
    boundary,
    boundary_plane,
    grid_size,
    tolerance
):
    """
    Generate one horizontal grid of sample positions inside the boundary.

    The grid uses cell centers rather than cell corners. This allows each point
    to represent the center of a future GridSize x GridSize voxel.
    """
    points = []
    bounding_box = boundary.GetBoundingBox(True)

    minimum_x = bounding_box.Min.X
    minimum_y = bounding_box.Min.Y
    maximum_x = bounding_box.Max.X
    maximum_y = bounding_box.Max.Y

    x_count = max(
        1,
        int(math.ceil((maximum_x - minimum_x) / grid_size))
    )

    y_count = max(
        1,
        int(math.ceil((maximum_y - minimum_y) / grid_size))
    )

    base_z = boundary_plane.Origin.Z

    for x_index in range(x_count):
        x = minimum_x + ((x_index + 0.5) * grid_size)

        if x > maximum_x + tolerance:
            continue

        for y_index in range(y_count):
            y = minimum_y + ((y_index + 0.5) * grid_size)

            if y > maximum_y + tolerance:
                continue

            candidate = rg.Point3d(x, y, base_z)

            if point_inside_boundary(
                boundary,
                boundary_plane,
                candidate,
                tolerance
            ):
                points.append(candidate)

    return points


def generate_sample_layers(
    boundary,
    boundary_plane,
    grid_size,
    height_step,
    max_height,
    tolerance
):
    """
    Generate all sample points organized by vertical layer.

    Each point represents the center of a voxel:
    X size = GridSize
    Y size = GridSize
    Z size = HeightStep

    The first layer is centered at HeightStep / 2 above the boundary plane.
    """
    plan_points = generate_plan_sample_points(
        boundary,
        boundary_plane,
        grid_size,
        tolerance
    )

    layer_count = max(
        1,
        int(math.ceil(max_height / height_step))
    )

    layers = []
    base_z = boundary_plane.Origin.Z

    for layer_index in range(layer_count):
        layer_center_height = (layer_index + 0.5) * height_step

        if layer_center_height > max_height + tolerance:
            break

        layer_z = base_z + layer_center_height
        layer_points = []

        for plan_point in plan_points:
            layer_points.append(
                rg.Point3d(
                    plan_point.X,
                    plan_point.Y,
                    layer_z
                )
            )

        layers.append(layer_points)

    return layers, plan_points


# =============================================================================
# TIME SAMPLING
# =============================================================================

def decimal_hour_to_datetime(base_date, decimal_hour):
    """Convert a local decimal clock hour into a datetime."""
    total_seconds = int(round(float(decimal_hour) * 3600.0))
    return base_date + timedelta(seconds=total_seconds)


def generate_time_intervals(
    month,
    day,
    start_hour,
    end_hour,
    time_step_minutes
):
    """
    Generate midpoint time samples with integration weights.

    Example
    -------
    StartHour = 8
    EndHour   = 10
    TimeStep  = 60 minutes

    Samples are evaluated at:
    08:30 with weight 1.0 hour
    09:30 with weight 1.0 hour

    This avoids double-counting endpoints and supports a shorter final interval.
    """
    base_date = validate_date(month, day)

    start_datetime = decimal_hour_to_datetime(base_date, start_hour)
    end_datetime = decimal_hour_to_datetime(base_date, end_hour)

    intervals = []
    current_start = start_datetime
    requested_step = timedelta(minutes=float(time_step_minutes))

    while current_start < end_datetime:
        current_end = min(
            current_start + requested_step,
            end_datetime
        )

        interval_delta = current_end - current_start
        interval_seconds = timedelta_to_seconds(interval_delta)
        duration_hours = interval_seconds / 3600.0

        midpoint = current_start + timedelta(
            seconds=interval_seconds * 0.5
        )

        intervals.append(
            {
                "datetime": midpoint,
                "duration_hours": duration_hours,
                "start": current_start,
                "end": current_end
            }
        )

        current_start = current_end

    return intervals


# =============================================================================
# SOLAR POSITION
# =============================================================================

def fractional_year_radians(local_datetime):
    """
    Calculate the NOAA fractional-year angle in radians.

    The hour term is included because equation of time and declination vary
    slightly during the day.
    """
    day_of_year = local_datetime.timetuple().tm_yday
    hour = (
        local_datetime.hour +
        local_datetime.minute / 60.0 +
        local_datetime.second / 3600.0
    )

    return (
        2.0 *
        math.pi /
        365.0 *
        (
            day_of_year -
            1 +
            (hour - 12.0) / 24.0
        )
    )


def equation_of_time_minutes(gamma):
    """NOAA approximation of equation of time in minutes."""
    return 229.18 * (
        0.000075 +
        0.001868 * math.cos(gamma) -
        0.032077 * math.sin(gamma) -
        0.014615 * math.cos(2.0 * gamma) -
        0.040849 * math.sin(2.0 * gamma)
    )


def solar_declination_radians(gamma):
    """NOAA approximation of solar declination in radians."""
    return (
        0.006918 -
        0.399912 * math.cos(gamma) +
        0.070257 * math.sin(gamma) -
        0.006758 * math.cos(2.0 * gamma) +
        0.000907 * math.sin(2.0 * gamma) -
        0.002697 * math.cos(3.0 * gamma) +
        0.001480 * math.sin(3.0 * gamma)
    )


def calculate_solar_position(
    local_datetime,
    latitude_degrees,
    longitude_degrees,
    timezone_hours
):
    """
    Calculate solar altitude and azimuth.

    Coordinate conventions
    ----------------------
    Longitude:
        East positive, west negative.

    TimeZone:
        UTC offset in hours.

    Azimuth:
        Clockwise from true north.
        0 degrees   = north
        90 degrees  = east
        180 degrees = south
        270 degrees = west.

    Returns
    -------
    altitude_radians : float
    azimuth_radians  : float
    """
    latitude = math.radians(float(latitude_degrees))
    longitude = float(longitude_degrees)
    timezone = float(timezone_hours)

    gamma = fractional_year_radians(local_datetime)
    equation_of_time = equation_of_time_minutes(gamma)
    declination = solar_declination_radians(gamma)

    local_minutes = (
        local_datetime.hour * 60.0 +
        local_datetime.minute +
        local_datetime.second / 60.0
    )

    time_offset = (
        equation_of_time +
        4.0 * longitude -
        60.0 * timezone
    )

    true_solar_time = (local_minutes + time_offset) % 1440.0

    hour_angle_degrees = true_solar_time / 4.0 - 180.0

    if hour_angle_degrees < -180.0:
        hour_angle_degrees += 360.0

    hour_angle = math.radians(hour_angle_degrees)

    cosine_zenith = (
        math.sin(latitude) * math.sin(declination) +
        math.cos(latitude) *
        math.cos(declination) *
        math.cos(hour_angle)
    )

    cosine_zenith = clamp(cosine_zenith, -1.0, 1.0)
    zenith = math.acos(cosine_zenith)
    altitude = (math.pi / 2.0) - zenith

    azimuth_from_south = math.atan2(
        math.sin(hour_angle),
        (
            math.cos(hour_angle) * math.sin(latitude) -
            math.tan(declination) * math.cos(latitude)
        )
    )

    azimuth_from_north = (
        azimuth_from_south + math.pi
    ) % (2.0 * math.pi)

    return altitude, azimuth_from_north


def solar_position_to_vector(
    altitude,
    azimuth,
    north_vector,
    east_vector
):
    """
    Convert solar altitude and azimuth into a Rhino world-space vector.

    The returned vector points from the sample point toward the sun.
    """
    horizontal_factor = math.cos(altitude)

    north_component = (
        horizontal_factor *
        math.cos(azimuth)
    )

    east_component = (
        horizontal_factor *
        math.sin(azimuth)
    )

    vertical_component = math.sin(altitude)

    vector = (
        north_vector * north_component +
        east_vector * east_component +
        rg.Vector3d.ZAxis * vertical_component
    )

    if not vector.Unitize():
        return None

    return vector


def calculate_sun_samples(
    time_intervals,
    latitude,
    longitude,
    timezone,
    north_vector,
    east_vector
):
    """
    Calculate sun vectors and integration weights for all time intervals.

    Intervals whose midpoint sun is at or below the horizon are excluded from
    ray casting but remain represented in the reporting statistics.
    """
    active_samples = []
    below_horizon_count = 0

    for interval in time_intervals:
        altitude, azimuth = calculate_solar_position(
            interval["datetime"],
            latitude,
            longitude,
            timezone
        )

        if altitude <= 0.0:
            below_horizon_count += 1
            continue

        vector = solar_position_to_vector(
            altitude,
            azimuth,
            north_vector,
            east_vector
        )

        if vector is None:
            continue

        active_samples.append(
            {
                "datetime": interval["datetime"],
                "duration_hours": interval["duration_hours"],
                "altitude": altitude,
                "azimuth": azimuth,
                "vector": vector
            }
        )

    return active_samples, below_horizon_count


# =============================================================================
# RAY CASTING
# =============================================================================

def point_has_direct_sun(
    point,
    sun_vector,
    context_mesh,
    origin_offset,
    ray_error_counter=None
):
    """
    Return True when no context mesh intersects the ray toward the sun.

    A tiny origin offset is applied in the sun direction to reduce accidental
    intersections caused by numerical coincidence with a context surface.
    """
    if context_mesh is None:
        return True

    ray_origin = point + sun_vector * origin_offset
    ray = rg.Ray3d(ray_origin, sun_vector)

    try:
        distance = rg.Intersect.Intersection.MeshRay(
            context_mesh,
            ray
        )
    except Exception:
        if ray_error_counter is not None:
            ray_error_counter[0] += 1
        return False

    return distance < 0.0


def calculate_layer_sun_hours(
    layer_points,
    sun_samples,
    context_mesh,
    origin_offset,
    global_counter_start=0,
    ray_error_counter=None
):
    """
    Calculate accumulated direct-sun hours for one layer.

    Returns
    -------
    list[float]
        One value for each point in layer_points.

    bool
        True when calculation was cancelled with Escape.

    int
        Updated global point counter.
    """
    sun_hours = []
    global_counter = global_counter_start

    for point in layer_points:
        accumulated_hours = 0.0

        for sample in sun_samples:
            if point_has_direct_sun(
                point,
                sample["vector"],
                context_mesh,
                origin_offset,
                ray_error_counter
            ):
                accumulated_hours += sample["duration_hours"]

        sun_hours.append(accumulated_hours)
        global_counter += 1

        if global_counter % PROGRESS_CHECK_INTERVAL == 0:
            if check_escape_key():
                return sun_hours, True, global_counter

    return sun_hours, False, global_counter


def calculate_all_sun_hours(
    sample_layers,
    sun_samples,
    context_mesh,
    origin_offset
):
    """
    Calculate direct-sun hours for every point in every layer.

    The returned nested list has exactly the same branch and item structure as
    sample_layers unless the user cancels the calculation. The other return
    values report cancellation state, processed point count, and MeshRay error
    count.
    """
    all_hours = []
    cancelled = False
    point_counter = 0
    ray_error_counter = [0]

    if context_mesh is None:
        unobstructed_hours = 0.0

        for sample in sun_samples:
            unobstructed_hours += sample["duration_hours"]

        for layer_points in sample_layers:
            layer_hours = []
            layer_item_count = len(layer_points)

            while len(layer_hours) < layer_item_count:
                items_until_escape_check = (
                    PROGRESS_CHECK_INTERVAL -
                    (point_counter % PROGRESS_CHECK_INTERVAL)
                )

                remaining_item_count = (
                    layer_item_count -
                    len(layer_hours)
                )

                chunk_size = min(
                    items_until_escape_check,
                    remaining_item_count
                )

                layer_hours.extend(
                    [unobstructed_hours] * chunk_size
                )

                point_counter += chunk_size

                if point_counter % PROGRESS_CHECK_INTERVAL == 0:
                    if check_escape_key():
                        all_hours.append(layer_hours)
                        cancelled = True

                        return (
                            all_hours,
                            cancelled,
                            point_counter,
                            ray_error_counter[0]
                        )

            all_hours.append(layer_hours)

        return (
            all_hours,
            cancelled,
            point_counter,
            ray_error_counter[0]
        )

    for layer_points in sample_layers:
        layer_hours, layer_cancelled, point_counter = (
            calculate_layer_sun_hours(
                layer_points,
                sun_samples,
                context_mesh,
                origin_offset,
                point_counter,
                ray_error_counter
            )
        )

        all_hours.append(layer_hours)

        if layer_cancelled:
            cancelled = True
            break

    return (
        all_hours,
        cancelled,
        point_counter,
        ray_error_counter[0]
    )


# =============================================================================
# GRASSHOPPER DATA TREE OUTPUT
# =============================================================================

def build_matching_output_trees(sample_layers, hour_layers):
    """
    Build matching Grasshopper Data Trees.

    Branch path {n} represents vertical layer n.

    For every valid item:
        point_tree.Branch(path)[i]
        corresponds exactly to
        hour_tree.Branch(path)[i]
    """
    point_tree = DataTree[object]()
    hour_tree = DataTree[object]()

    if len(sample_layers) != len(hour_layers):
        raise ValueError(
            "P/H layer counts do not match: {0} point layers, "
            "{1} hour layers.".format(
                len(sample_layers),
                len(hour_layers)
            )
        )

    branch_count = len(sample_layers)

    output_point_count = 0

    for layer_index in range(branch_count):
        path = GH_Path(layer_index)

        points = sample_layers[layer_index]
        hours = hour_layers[layer_index]

        if len(points) != len(hours):
            raise ValueError(
                "P/H item counts do not match in layer {0}: "
                "{1} points, {2} hour values.".format(
                    layer_index,
                    len(points),
                    len(hours)
                )
            )

        item_count = len(points)

        for item_index in range(item_count):
            point_tree.Add(points[item_index], path)
            hour_tree.Add(float(hours[item_index]), path)
            output_point_count += 1

    return point_tree, hour_tree, output_point_count


# =============================================================================
# REPORTING
# =============================================================================

def calculate_context_statistics(context_mesh):
    """Return context vertex and face counts."""
    if context_mesh is None:
        return 0, 0

    try:
        vertex_count = context_mesh.Vertices.Count
    except Exception:
        vertex_count = 0

    try:
        face_count = context_mesh.Faces.Count
    except Exception:
        face_count = 0

    return vertex_count, face_count


def calculate_result_statistics(hour_layers):
    """Calculate minimum, maximum, and average sun hours."""
    value_count = 0
    value_sum = 0.0
    minimum = None
    maximum = None

    for branch in hour_layers:
        for value in branch:
            numeric_value = float(value)

            value_count += 1
            value_sum += numeric_value

            if minimum is None or numeric_value < minimum:
                minimum = numeric_value

            if maximum is None or numeric_value > maximum:
                maximum = numeric_value

    if value_count == 0:
        return 0.0, 0.0, 0.0

    average = value_sum / value_count

    return minimum, maximum, average


def build_info(
    status,
    elapsed_seconds,
    sample_layers,
    plan_points,
    time_intervals,
    sun_samples,
    below_horizon_count,
    context_mesh,
    source_mesh_count,
    output_point_count,
    grid_size,
    height_step,
    max_height,
    latitude,
    longitude,
    timezone,
    month,
    day,
    start_hour,
    end_hour,
    time_step,
    north_vector,
    warnings,
    hour_layers=None
):
    """Build a readable information list for a Grasshopper Panel."""
    info = []

    context_vertex_count, context_face_count = (
        calculate_context_statistics(context_mesh)
    )

    info.append("Status: {0}".format(status))
    info.append(
        "Calculation Time: {0} seconds".format(
            format_number(elapsed_seconds, 3)
        )
    )

    info.append("--- Sampling ---")
    info.append(
        "Plan Sample Points per Full Layer: {0}".format(
            len(plan_points)
        )
    )
    info.append(
        "Output Layers: {0}".format(
            len(sample_layers)
        )
    )
    info.append(
        "Output Sample Points: {0}".format(
            output_point_count
        )
    )
    info.append(
        "Grid Size: {0}".format(
            format_number(grid_size, 4)
        )
    )
    info.append(
        "Height Step: {0}".format(
            format_number(height_step, 4)
        )
    )
    info.append(
        "Maximum Height: {0}".format(
            format_number(max_height, 4)
        )
    )

    info.append("--- Solar Inputs ---")
    info.append(
        "Date: {0:02d}-{1:02d}".format(
            int(month),
            int(day)
        )
    )
    info.append(
        "Local Time Range: {0} to {1}".format(
            format_number(start_hour, 3),
            format_number(end_hour, 3)
        )
    )
    info.append(
        "Time Step: {0} minutes".format(
            format_number(time_step, 3)
        )
    )
    info.append(
        "Time Intervals: {0}".format(
            len(time_intervals)
        )
    )
    info.append(
        "Sun-Above-Horizon Intervals: {0}".format(
            len(sun_samples)
        )
    )
    info.append(
        "Below-Horizon Intervals: {0}".format(
            below_horizon_count
        )
    )
    info.append(
        "Latitude: {0} degrees".format(
            format_number(latitude, 6)
        )
    )
    info.append(
        "Longitude: {0} degrees".format(
            format_number(longitude, 6)
        )
    )
    info.append(
        "Time Zone: UTC{0}{1}".format(
            "+" if float(timezone) >= 0.0 else "",
            format_number(timezone, 2)
        )
    )
    info.append(
        "North Vector: ({0}, {1}, {2})".format(
            format_number(north_vector.X, 6),
            format_number(north_vector.Y, 6),
            format_number(north_vector.Z, 6)
        )
    )

    info.append("--- Context Mesh ---")
    info.append(
        "Source Mesh Parts: {0}".format(
            source_mesh_count
        )
    )
    info.append(
        "Joined Mesh Vertices: {0}".format(
            context_vertex_count
        )
    )
    info.append(
        "Joined Mesh Faces: {0}".format(
            context_face_count
        )
    )
    info.append(
        "Obstruction Test: {0}".format(
            "Enabled" if context_mesh is not None else "Disabled"
        )
    )
    info.append(
        "Sun-Hour Evaluation: {0}".format(
            "MeshRay" if context_mesh is not None
            else "Unobstructed Fast Path"
        )
    )

    if hour_layers is not None:
        minimum, maximum, average = calculate_result_statistics(
            hour_layers
        )

        info.append("--- Raw Sun-Hour Results ---")
        info.append(
            "Minimum Sun Hours: {0}".format(
                format_number(minimum, 4)
            )
        )
        info.append(
            "Maximum Sun Hours: {0}".format(
                format_number(maximum, 4)
            )
        )
        info.append(
            "Average Sun Hours: {0}".format(
                format_number(average, 4)
            )
        )

    info.append("--- Output Contract ---")
    info.append("P: Data Tree of all sample points.")
    info.append("H: Matching Data Tree of raw direct-sun hours.")
    info.append(
        "P and H have identical branch paths and item order."
    )
    info.append(
        "No compliance threshold is applied inside Python."
    )

    if warnings:
        info.append("--- Warnings ---")

        for warning in warnings:
            info.append("Warning: {0}".format(warning))

    return info


def build_error_info(errors, warnings=None):
    """Build error output without raising an unhandled component exception."""
    info = ["Status: Input Error"]

    for error in errors:
        info.append("Error: {0}".format(error))

    if warnings:
        for warning in warnings:
            info.append("Warning: {0}".format(warning))

    return info


# =============================================================================
# MAIN EXECUTION
# =============================================================================

def execute():
    """Run the complete raw solar-analysis workflow."""
    empty_points = DataTree[object]()
    empty_hours = DataTree[object]()

    if not bool(Run):
        return (
            empty_points,
            empty_hours,
            [
                "Status: Waiting",
                "Set Run to True to calculate.",
                "Python outputs raw sample points and sun-hour data only."
            ]
        )

    calculation_start = time.time()

    all_errors = []
    all_warnings = []

    boundary_errors, boundary_plane = validate_boundary(
        Boundary
    )
    all_errors.extend(boundary_errors)

    numeric_errors, numeric_warnings = validate_numeric_inputs(
        Latitude,
        Longitude,
        TimeZone,
        Month,
        Day,
        StartHour,
        EndHour,
        TimeStep,
        GridSize,
        HeightStep,
        MaxHeight
    )
    all_errors.extend(numeric_errors)
    all_warnings.extend(numeric_warnings)

    north_errors, north_vector, east_vector = (
        validate_and_normalize_north(North)
    )
    all_errors.extend(north_errors)

    if all_errors:
        return (
            empty_points,
            empty_hours,
            build_error_info(
                all_errors,
                all_warnings
            )
        )

    latitude = float(Latitude)
    longitude = float(Longitude)
    timezone = float(TimeZone)
    month = int(Month)
    day = int(Day)
    start_hour = float(StartHour)
    end_hour = float(EndHour)
    time_step = float(TimeStep)
    grid_size = float(GridSize)
    height_step = float(HeightStep)
    max_height = float(MaxHeight)

    document = Rhino.RhinoDoc.ActiveDoc

    if document is not None:
        tolerance = max(
            document.ModelAbsoluteTolerance,
            EPSILON
        )
    else:
        tolerance = 0.001

    estimated_count, x_count, y_count, estimated_layers = (
        estimate_sample_count(
            Boundary,
            grid_size,
            height_step,
            max_height
        )
    )

    if estimated_count > MAX_SAMPLE_POINTS:
        all_errors.append(
            "Estimated sample count ({0}) exceeds the safety limit "
            "({1}). Increase GridSize or HeightStep, or reduce "
            "MaxHeight.".format(
                estimated_count,
                MAX_SAMPLE_POINTS
            )
        )

        all_errors.append(
            "Bounding-box estimate: {0} x-columns, {1} y-columns, "
            "{2} layers.".format(
                x_count,
                y_count,
                estimated_layers
            )
        )

        return (
            empty_points,
            empty_hours,
            build_error_info(
                all_errors,
                all_warnings
            )
        )

    context_mesh, context_warnings, source_mesh_count = (
        build_context_mesh(Context)
    )
    all_warnings.extend(context_warnings)

    if context_mesh is None:
        all_warnings.append(
            "No valid context mesh is available. Every point will be "
            "treated as unobstructed whenever the sun is above the horizon."
        )

    sample_layers, plan_points = generate_sample_layers(
        Boundary,
        boundary_plane,
        grid_size,
        height_step,
        max_height,
        tolerance
    )

    if not plan_points:
        all_errors.append(
            "No sample points were generated inside Boundary. "
            "Check Boundary, GridSize, and model units."
        )

        return (
            empty_points,
            empty_hours,
            build_error_info(
                all_errors,
                all_warnings
            )
        )

    if not sample_layers:
        all_errors.append(
            "No vertical sample layers were generated. "
            "Check HeightStep and MaxHeight."
        )

        return (
            empty_points,
            empty_hours,
            build_error_info(
                all_errors,
                all_warnings
            )
        )

    actual_sample_count = sum(
        len(layer) for layer in sample_layers
    )

    if actual_sample_count > MAX_SAMPLE_POINTS:
        all_errors.append(
            "Actual sample count ({0}) exceeds the safety limit "
            "({1}). Increase GridSize or HeightStep, or reduce "
            "MaxHeight.".format(
                actual_sample_count,
                MAX_SAMPLE_POINTS
            )
        )

        return (
            empty_points,
            empty_hours,
            build_error_info(
                all_errors,
                all_warnings
            )
        )

    time_intervals = generate_time_intervals(
        month,
        day,
        start_hour,
        end_hour,
        time_step
    )

    if not time_intervals:
        all_errors.append(
            "No time intervals were generated. "
            "Check StartHour, EndHour, and TimeStep."
        )

        return (
            empty_points,
            empty_hours,
            build_error_info(
                all_errors,
                all_warnings
            )
        )

    sun_samples, below_horizon_count = calculate_sun_samples(
        time_intervals,
        latitude,
        longitude,
        timezone,
        north_vector,
        east_vector
    )

    if not sun_samples:
        all_warnings.append(
            "The sun is at or below the horizon for all sampled intervals. "
            "All output sun-hour values will be zero."
        )

    model_scale = max(
        abs(grid_size),
        abs(height_step),
        1.0
    )

    origin_offset = max(
        tolerance * 10.0,
        RAY_ORIGIN_OFFSET * model_scale
    )

    (
        hour_layers,
        cancelled,
        processed_point_count,
        ray_error_count
    ) = (
        calculate_all_sun_hours(
            sample_layers,
            sun_samples,
            context_mesh,
            origin_offset
        )
    )

    if ray_error_count > 0:
        all_warnings.append(
            "{0} MeshRay call(s) failed and were conservatively "
            "treated as obstructed.".format(ray_error_count)
        )

    if cancelled:
        completed_layer_count = len(hour_layers)

        partial_sample_layers = []

        for layer_index in range(completed_layer_count):
            completed_item_count = len(hour_layers[layer_index])

            partial_sample_layers.append(
                sample_layers[layer_index][:completed_item_count]
            )

        point_tree, hour_tree, output_point_count = (
            build_matching_output_trees(
                partial_sample_layers,
                hour_layers
            )
        )

        elapsed_seconds = (
            time.time() -
            calculation_start
        )

        all_warnings.append(
            "Calculation was cancelled with Escape. "
            "Outputs may contain only partial results."
        )

        info = build_info(
            "Cancelled",
            elapsed_seconds,
            partial_sample_layers,
            plan_points,
            time_intervals,
            sun_samples,
            below_horizon_count,
            context_mesh,
            source_mesh_count,
            output_point_count,
            grid_size,
            height_step,
            max_height,
            latitude,
            longitude,
            timezone,
            month,
            day,
            start_hour,
            end_hour,
            time_step,
            north_vector,
            all_warnings,
            hour_layers
        )

        info.append(
            "Processed Points Before Cancellation: {0}".format(
                processed_point_count
            )
        )

        return point_tree, hour_tree, info

    point_tree, hour_tree, output_point_count = (
        build_matching_output_trees(
            sample_layers,
            hour_layers
        )
    )

    elapsed_seconds = (
        time.time() -
        calculation_start
    )

    info = build_info(
        "Completed",
        elapsed_seconds,
        sample_layers,
        plan_points,
        time_intervals,
        sun_samples,
        below_horizon_count,
        context_mesh,
        source_mesh_count,
        output_point_count,
        grid_size,
        height_step,
        max_height,
        latitude,
        longitude,
        timezone,
        month,
        day,
        start_hour,
        end_hour,
        time_step,
        north_vector,
        all_warnings,
        hour_layers
    )

    return point_tree, hour_tree, info


try:
    P, H, I = execute()

except Exception as exception:
    P = DataTree[object]()
    H = DataTree[object]()

    I = [
        "Status: Runtime Error",
        "Error Type: {0}".format(
            type(exception).__name__
        ),
        "Error Message: {0}".format(
            str(exception)
        ),
        "Check the component inputs and Rhino geometry validity."
    ]
