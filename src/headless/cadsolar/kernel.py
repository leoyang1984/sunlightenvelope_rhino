"""
Load the shipping algorithm out of the Rhino components, without Rhino.

This does not reimplement anything. It parses the actual component files in
src/rhino8/, keeps every top-level function that does not touch RhinoCommon,
and executes them in a namespace where the handful of Rhino-bound helpers are
replaced by 2.5D equivalents.

The point of doing it this way rather than porting by hand: if the extracted
functions produce a different answer than Rhino, the difference can only come
from the injected primitives, because the algorithm itself is the same bytes.

Injected per component:

    mesh_ray_distance / ray_mesh_hit   -> geom.ray_distance
    solar_position_to_vector           -> tuple math
    check_escape_key                   -> always False
    active_document_units              -> fixed string
    make_constraint_event              -> plain dict, no Rhino Line
    cell_sample_points                 -> unused here

Everything else - solar position, interval integration, the continuous-window
rule, the greedy top-down search, the reporting - runs as written.
"""

import ast
import math
import pathlib
from datetime import datetime, timedelta

from . import geom

REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
RHINO8_DIR = REPO_ROOT / "src" / "rhino8"

OPTIMIZER_PATH = RHINO8_DIR / "SolarVoxelOptimizer_Rhino8_SDK.py"
SOLVER_PATH = RHINO8_DIR / "SolarConstraintSolver_Rhino8_SDK.py"

RHINO_NAMES = {"rg", "Rhino", "sc", "System", "DataTree", "GH_Path"}


def _touches_rhino(node):
    return any(
        isinstance(child, ast.Name) and child.id in RHINO_NAMES
        for child in ast.walk(node)
    )


def _solar_position_to_vector(altitude, azimuth, north_vector, east_vector):
    """Altitude/azimuth to a unit world vector, as plain tuples."""
    horizontal = math.cos(altitude)
    nx, ny, nz = north_vector
    ex, ey, ez = east_vector
    north_weight = horizontal * math.cos(azimuth)
    east_weight = horizontal * math.sin(azimuth)
    up_weight = math.sin(altitude)

    x = nx * north_weight + ex * east_weight
    y = ny * north_weight + ey * east_weight
    z = nz * north_weight + ez * east_weight + up_weight
    length = math.sqrt(x * x + y * y + z * z)

    if length < 1.0e-12:
        return None

    return (x / length, y / length, z / length)


def _mesh_ray_distance(point, vector, solid, origin_offset):
    """The single geometry primitive the whole pipeline needs."""
    origin = (
        point[0] + vector[0] * origin_offset,
        point[1] + vector[1] * origin_offset,
        point[2] + vector[2] * origin_offset,
    )
    return geom.ray_distance(origin, vector, solid)


def _ray_mesh_hit(point, sun_vector, solid, origin_offset, error_counter):
    """Solver-side variant that also returns the hit point."""
    if solid is None:
        return False, None, None

    origin = (
        point[0] + sun_vector[0] * origin_offset,
        point[1] + sun_vector[1] * origin_offset,
        point[2] + sun_vector[2] * origin_offset,
    )
    distance = geom.ray_distance(origin, sun_vector, solid)

    if distance < 0.0:
        return False, None, None

    hit_point = (
        origin[0] + sun_vector[0] * distance,
        origin[1] + sun_vector[1] * distance,
        origin[2] + sun_vector[2] * distance,
    )
    return True, float(distance), hit_point


def _make_constraint_event(point_index, point, sample, hit_distance, hit_point):
    """Same record as the component, minus the Rhino Line."""
    return {
        "Schema": "SolarConstraintEvent.v1",
        "ProtectedPointIndex": int(point_index),
        "ProtectedPoint": point,
        "SampleIndex": int(sample["sample_index"]),
        "IntervalStart": sample["start"].isoformat(),
        "IntervalEnd": sample["end"].isoformat(),
        "SampleTime": sample["datetime"].isoformat(),
        "DurationHours": float(sample["duration_hours"]),
        "SolarAltitudeDegrees": math.degrees(sample["altitude"]),
        "SolarAzimuthDegrees": math.degrees(sample["azimuth"]),
        "SunVector": sample["vector"],
        "ConstraintLine": None,
        "DesignHitPoint": hit_point,
        "DesignHitDistance": hit_distance,
    }


def load_component(path):
    """
    Return {name: object} for every Rhino-free top-level definition in a
    component file, with the Rhino-bound helpers injected.
    """
    source = pathlib.Path(path).read_text(encoding="utf-8")
    tree = ast.parse(source)

    namespace = {
        "math": math,
        "datetime": datetime,
        "timedelta": timedelta,
        "solar_position_to_vector": _solar_position_to_vector,
        "mesh_ray_distance": _mesh_ray_distance,
        "ray_mesh_hit": _ray_mesh_hit,
        "make_constraint_event": _make_constraint_event,
        "check_escape_key": lambda: False,
        "active_document_units": lambda: "meters",
        "active_document_tolerance": lambda: 1.0e-6,
    }

    kept_nodes = []

    for node in tree.body:
        if isinstance(node, ast.Assign):
            target = node.targets[0]

            if isinstance(target, ast.Name) and target.id.isupper():
                if not _touches_rhino(node):
                    kept_nodes.append(node)
            continue

        if isinstance(node, ast.FunctionDef) and not _touches_rhino(node):
            kept_nodes.append(node)

    module = ast.Module(body=kept_nodes, type_ignores=[])
    exec(compile(module, str(path), "exec"), namespace)

    namespace["__extracted__"] = [
        node.name
        for node in kept_nodes
        if isinstance(node, ast.FunctionDef)
    ]
    namespace["__source_path__"] = str(path)
    return namespace


def load_optimizer():
    return load_component(OPTIMIZER_PATH)


def load_solver():
    return load_component(SOLVER_PATH)
