#! python 3
"""
Solar Design Voxelizer MVP
Rhino 8 Grasshopper Python 3 Script Component - SDK Mode

Purpose
-------
Convert a designer-controlled closed DesignVolume into conservative,
world-axis-aligned column voxels. The same DesignVolume input can be shared
with SolarConstraintSolver_Rhino8_SDK.py.

The voxel contract is intentionally explicit:

    Voxels[i]
    VoxelIDs[i]
    ColumnIDs[i]
    LayerIDs[i]
    VoxelCenters[i]
    VoxelVolumes[i]

all refer to the same voxel. VoxelTree branch {c} contains the voxels belonging
to ColumnID c, ordered from bottom to top.

MVP geometry rules
------------------
- DesignVolume must contain one or more valid closed solids.
- World Z is the vertical direction.
- The lowest world-Z level of the combined input is the common base.
- Only cells fully contained in the input solids are kept.
- Each output column must be continuously supported from the common base.
- Overhangs, floating pieces, and cells above a vertical gap are discarded.
- The grid is aligned to World X/Y and begins at the combined bounding-box
  minimum.

Recommended input access
------------------------
DesignVolume : List Access, GeometryBase
VoxelSizeXY  : Item Access, float, model units
VoxelSizeZ   : Item Access, float, model units
Run          : Item Access, bool

Create or rename eight outputs:
Voxels, VoxelIDs, ColumnIDs, LayerIDs, VoxelCenters, VoxelVolumes,
VoxelTree, Report.
"""

import math
import time

import Rhino
import Rhino.Geometry as rg
import scriptcontext as sc

import Grasshopper
from Grasshopper import DataTree
from Grasshopper.Kernel.Data import GH_Path


EPSILON = 1.0e-9
MAX_CANDIDATE_CELLS = 250000
ESCAPE_CHECK_INTERVAL = 1000


def unwrap_gh_value(value):
    """Unwrap common Grasshopper goo values passed through SDK parameters."""
    if value is None:
        return None

    try:
        unwrapped = value.Value

        if unwrapped is not None:
            return unwrapped
    except Exception:
        pass

    try:
        script_variable = value.ScriptVariable()

        if script_variable is not None:
            return script_variable
    except Exception:
        pass

    return value


def normalize_sequence(value):
    """Return a Python list for a GH List input or single fallback value."""
    if value is None:
        return []

    if isinstance(value, (str, bytes)):
        return [value]

    if isinstance(value, (list, tuple)):
        return list(value)

    try:
        return list(value)
    except Exception:
        return [value]


def is_finite_number(value):
    """Return True when value converts to a finite float."""
    try:
        number = float(unwrap_gh_value(value))
        return not math.isnan(number) and not math.isinf(number)
    except Exception:
        return False


def format_number(value, digits=3):
    """Format a number for a Grasshopper Panel."""
    try:
        return ("{0:." + str(digits) + "f}").format(float(value))
    except Exception:
        return str(value)


def geometry_type_name(geometry):
    """Return a readable Rhino or Python type name."""
    if geometry is None:
        return "None"

    try:
        return geometry.GetType().Name
    except Exception:
        return type(geometry).__name__


def active_document_tolerance():
    """Return a safe Rhino model tolerance."""
    document = Rhino.RhinoDoc.ActiveDoc

    if document is None:
        return 0.001

    try:
        return max(float(document.ModelAbsoluteTolerance), EPSILON)
    except Exception:
        return 0.001


def active_document_units():
    """Return the active Rhino model unit-system name."""
    document = Rhino.RhinoDoc.ActiveDoc

    if document is None:
        return "Unknown"

    try:
        return str(document.ModelUnitSystem)
    except Exception:
        return "Unknown"


def check_escape_key():
    """Return True when Rhino reports Escape."""
    try:
        return bool(sc.escape_test(False))
    except Exception:
        return False


def mesh_from_brep(brep):
    """Return one joined analysis mesh for a valid solid Brep."""
    if brep is None or not brep.IsValid or not brep.IsSolid:
        return None

    try:
        parts = rg.Mesh.CreateFromBrep(
            brep,
            rg.MeshingParameters.FastRenderMesh
        )
    except Exception:
        return None

    if not parts:
        return None

    joined = rg.Mesh()

    for part in parts:
        if part is not None and part.IsValid:
            joined.Append(part)

    try:
        joined.Vertices.CombineIdentical(True, True)
        joined.Faces.CullDegenerateFaces()
        joined.Compact()
    except Exception:
        pass

    if (
        not joined.IsValid or
        joined.Faces.Count == 0 or
        not joined.IsSolid
    ):
        return None

    return joined


def geometry_to_closed_mesh(geometry):
    """Convert a supported closed geometry object to one solid mesh."""
    geometry = unwrap_gh_value(geometry)

    if geometry is None:
        return None

    if isinstance(geometry, rg.Mesh):
        if not geometry.IsValid or not geometry.IsSolid:
            return None

        duplicate = geometry.DuplicateMesh()

        if duplicate is None or not duplicate.IsValid:
            return None

        return duplicate

    if isinstance(geometry, rg.Brep):
        return mesh_from_brep(geometry)

    if isinstance(geometry, rg.Extrusion):
        try:
            return mesh_from_brep(geometry.ToBrep())
        except Exception:
            return None

    if isinstance(geometry, rg.Surface):
        try:
            return mesh_from_brep(geometry.ToBrep())
        except Exception:
            return None

    if isinstance(geometry, rg.SubD):
        try:
            return mesh_from_brep(geometry.ToBrep())
        except Exception:
            return None

    return None


def collect_closed_source_meshes(design_volume):
    """Validate DesignVolume and return one closed mesh per source item."""
    errors = []
    warnings = []
    source_meshes = []
    values = normalize_sequence(design_volume)

    if not values:
        errors.append("DesignVolume is empty.")
        return source_meshes, errors, warnings

    for index, value in enumerate(values):
        geometry = unwrap_gh_value(value)

        if geometry is None:
            warnings.append(
                "DesignVolume item {0} is null and was ignored.".format(
                    index
                )
            )
            continue

        mesh = geometry_to_closed_mesh(geometry)

        if mesh is None:
            errors.append(
                "DesignVolume item {0} must be a valid closed solid. "
                "Received: {1}.".format(
                    index,
                    geometry_type_name(geometry)
                )
            )
            continue

        if not mesh.IsSolid:
            errors.append(
                "DesignVolume item {0} did not produce a closed, oriented, "
                "manifold solid mesh."
                .format(index)
            )
            continue

        source_meshes.append(mesh)

    if not source_meshes and not errors:
        errors.append("DesignVolume contains no usable closed solids.")

    return source_meshes, errors, warnings


def union_bounding_box(meshes):
    """Return the world-aligned bounding box of all source meshes."""
    combined = rg.BoundingBox.Empty

    for mesh in meshes:
        box = mesh.GetBoundingBox(True)

        if box.IsValid:
            combined.Union(box)

    return combined


def point_inside_union(point, source_meshes, tolerance):
    """Return True when a point is inside or on any source solid."""
    for mesh in source_meshes:
        try:
            if mesh.IsPointInside(point, tolerance, False):
                return True
        except Exception:
            continue

    return False


def bounding_box_corners(minimum, maximum):
    """Return the eight corners of an axis-aligned cell."""
    return [
        rg.Point3d(minimum.X, minimum.Y, minimum.Z),
        rg.Point3d(maximum.X, minimum.Y, minimum.Z),
        rg.Point3d(maximum.X, maximum.Y, minimum.Z),
        rg.Point3d(minimum.X, maximum.Y, minimum.Z),
        rg.Point3d(minimum.X, minimum.Y, maximum.Z),
        rg.Point3d(maximum.X, minimum.Y, maximum.Z),
        rg.Point3d(maximum.X, maximum.Y, maximum.Z),
        rg.Point3d(minimum.X, maximum.Y, maximum.Z)
    ]


def cell_sample_points(minimum, maximum):
    """Return corners, center, and face centers for conservative occupancy."""
    points = bounding_box_corners(minimum, maximum)
    center = rg.Point3d(
        (minimum.X + maximum.X) * 0.5,
        (minimum.Y + maximum.Y) * 0.5,
        (minimum.Z + maximum.Z) * 0.5
    )
    points.append(center)
    points.extend(
        [
            rg.Point3d(center.X, center.Y, minimum.Z),
            rg.Point3d(center.X, center.Y, maximum.Z),
            rg.Point3d(minimum.X, center.Y, center.Z),
            rg.Point3d(maximum.X, center.Y, center.Z),
            rg.Point3d(center.X, minimum.Y, center.Z),
            rg.Point3d(center.X, maximum.Y, center.Z)
        ]
    )
    return points


def cell_is_conservatively_inside(
    minimum,
    maximum,
    source_meshes,
    tolerance
):
    """Require all cell sample points to lie inside the source-solid union."""
    for point in cell_sample_points(minimum, maximum):
        if not point_inside_union(point, source_meshes, tolerance):
            return False

    return True


def validate_sizes(voxel_size_xy, voxel_size_z):
    """Validate voxel dimensions and return normalized floats."""
    errors = []

    if not is_finite_number(voxel_size_xy):
        errors.append("VoxelSizeXY must be a finite number.")

    if not is_finite_number(voxel_size_z):
        errors.append("VoxelSizeZ must be a finite number.")

    if errors:
        return errors, None, None

    size_xy = float(unwrap_gh_value(voxel_size_xy))
    size_z = float(unwrap_gh_value(voxel_size_z))

    if size_xy <= 0.0:
        errors.append("VoxelSizeXY must be greater than zero.")

    if size_z <= 0.0:
        errors.append("VoxelSizeZ must be greater than zero.")

    return errors, size_xy, size_z


def axis_cell_count(length, cell_size):
    """Return the number of grid cells required to cover one axis."""
    if length <= EPSILON:
        return 0

    return int(math.ceil(length / cell_size - EPSILON))


def create_voxel_grid(
    source_meshes,
    bounding_box,
    voxel_size_xy,
    voxel_size_z,
    tolerance
):
    """
    Create conservative, base-supported, world-aligned column voxels.

    Returns flat synchronized arrays plus diagnostic counts.
    """
    extent_x = bounding_box.Max.X - bounding_box.Min.X
    extent_y = bounding_box.Max.Y - bounding_box.Min.Y
    extent_z = bounding_box.Max.Z - bounding_box.Min.Z
    count_x = axis_cell_count(extent_x, voxel_size_xy)
    count_y = axis_cell_count(extent_y, voxel_size_xy)
    count_z = axis_cell_count(extent_z, voxel_size_z)
    candidate_count = count_x * count_y * count_z

    if count_x <= 0 or count_y <= 0 or count_z <= 0:
        return {
            "error": "DesignVolume bounding box has a zero-sized axis.",
            "candidate_count": candidate_count
        }

    if candidate_count > MAX_CANDIDATE_CELLS:
        return {
            "error": (
                "Candidate voxel count {0} exceeds the safety limit {1}. "
                "Increase VoxelSizeXY or VoxelSizeZ.".format(
                    candidate_count,
                    MAX_CANDIDATE_CELLS
                )
            ),
            "candidate_count": candidate_count
        }

    voxels = []
    voxel_ids = []
    column_ids = []
    layer_ids = []
    centers = []
    volumes = []
    column_count = 0
    unsupported_cell_count = 0
    rejected_cell_count = 0
    processed_candidates = 0
    cancelled = False

    for x_index in range(count_x):
        if cancelled:
            break

        minimum_x = bounding_box.Min.X + x_index * voxel_size_xy
        maximum_x = min(
            minimum_x + voxel_size_xy,
            bounding_box.Max.X
        )

        for y_index in range(count_y):
            minimum_y = bounding_box.Min.Y + y_index * voxel_size_xy
            maximum_y = min(
                minimum_y + voxel_size_xy,
                bounding_box.Max.Y
            )
            cell_flags = []
            cell_bounds = []

            for z_index in range(count_z):
                minimum_z = bounding_box.Min.Z + z_index * voxel_size_z
                maximum_z = min(
                    minimum_z + voxel_size_z,
                    bounding_box.Max.Z
                )
                minimum = rg.Point3d(
                    minimum_x,
                    minimum_y,
                    minimum_z
                )
                maximum = rg.Point3d(
                    maximum_x,
                    maximum_y,
                    maximum_z
                )
                is_inside = cell_is_conservatively_inside(
                    minimum,
                    maximum,
                    source_meshes,
                    tolerance
                )
                cell_flags.append(is_inside)
                cell_bounds.append((minimum, maximum, z_index))
                processed_candidates += 1

                if (
                    processed_candidates % ESCAPE_CHECK_INTERVAL == 0 and
                    check_escape_key()
                ):
                    cancelled = True
                    break

            if cancelled:
                break

            supported_bounds = []
            support_broken = False

            for flag, bounds in zip(cell_flags, cell_bounds):
                if not support_broken and flag:
                    supported_bounds.append(bounds)
                    continue

                if not flag:
                    support_broken = True
                    rejected_cell_count += 1
                    continue

                unsupported_cell_count += 1

            if not supported_bounds:
                continue

            column_id = column_count
            column_count += 1

            for minimum, maximum, z_index in supported_bounds:
                box = rg.BoundingBox(minimum, maximum)
                brep = rg.Brep.CreateFromBox(box)

                if brep is None or not brep.IsValid:
                    continue

                voxel_id = len(voxels)
                center = box.Center
                volume = (
                    (maximum.X - minimum.X) *
                    (maximum.Y - minimum.Y) *
                    (maximum.Z - minimum.Z)
                )
                voxels.append(brep)
                voxel_ids.append(voxel_id)
                column_ids.append(column_id)
                layer_ids.append(z_index)
                centers.append(center)
                volumes.append(volume)

    return {
        "error": None,
        "voxels": voxels,
        "voxel_ids": voxel_ids,
        "column_ids": column_ids,
        "layer_ids": layer_ids,
        "centers": centers,
        "volumes": volumes,
        "count_x": count_x,
        "count_y": count_y,
        "count_z": count_z,
        "candidate_count": candidate_count,
        "column_count": column_count,
        "rejected_cell_count": rejected_cell_count,
        "unsupported_cell_count": unsupported_cell_count,
        "cancelled": cancelled
    }


def build_voxel_tree(voxels, column_ids):
    """Build branch {ColumnID}, ordered bottom-to-top by flat input order."""
    tree = DataTree[object]()

    for voxel, column_id in zip(voxels, column_ids):
        tree.Add(voxel, GH_Path(int(column_id)))

    return tree


def build_report(
    status,
    elapsed_seconds,
    source_count,
    bounding_box,
    voxel_size_xy,
    voxel_size_z,
    result,
    warnings
):
    """Build a complete Panel-friendly report."""
    total_volume = sum(result.get("volumes", []))
    report = [
        "Status: {0}".format(status),
        "Component: Solar Design Voxelizer MVP",
        "Runtime: Rhino 8 Python 3 SDK-Mode",
        "Calculation Time: {0} seconds".format(
            format_number(elapsed_seconds, 3)
        ),
        "--- Input ---",
        "Design Source Solids: {0}".format(source_count),
        "Model Units: {0}".format(active_document_units()),
        "Voxel Size XY: {0}".format(
            format_number(voxel_size_xy, 3)
        ),
        "Voxel Size Z: {0}".format(
            format_number(voxel_size_z, 3)
        ),
        "Grid Alignment: World XY / World Z",
        "Containment Mode: Conservative Full Cell",
        "Support Rule: Continuous from combined minimum Z",
        "--- Bounding Box ---",
        "Minimum: {0}".format(bounding_box.Min),
        "Maximum: {0}".format(bounding_box.Max),
        "--- Grid ---",
        "X Cells: {0}".format(result.get("count_x", 0)),
        "Y Cells: {0}".format(result.get("count_y", 0)),
        "Z Layers: {0}".format(result.get("count_z", 0)),
        "Candidate Cells: {0}".format(
            result.get("candidate_count", 0)
        ),
        "Output Columns: {0}".format(
            result.get("column_count", 0)
        ),
        "Output Voxels: {0}".format(
            len(result.get("voxels", []))
        ),
        "Conservative Rejected Cells: {0}".format(
            result.get("rejected_cell_count", 0)
        ),
        "Unsupported Cells Discarded: {0}".format(
            result.get("unsupported_cell_count", 0)
        ),
        "Voxelized Volume: {0} cubic model units".format(
            format_number(total_volume, 3)
        ),
        "--- Output Contract ---",
        (
            "All flat output lists use the same voxel index and item order."
        ),
        (
            "VoxelTree branch {c} contains ColumnID c from bottom to top."
        ),
        (
            "The voxelized result is a conservative subset of "
            "DesignVolume."
        ),
        (
            "This component generates candidates only; it does not perform "
            "solar optimization."
        )
    ]

    if warnings:
        report.append("--- Warnings ---")

        for warning in warnings:
            report.append("Warning: {0}".format(warning))

    return report


def error_report(errors, warnings=None):
    """Return errors and warnings as Panel-friendly strings."""
    report = ["Status: Input Error"]

    for error in errors:
        report.append("Error: {0}".format(error))

    if warnings:
        for warning in warnings:
            report.append("Warning: {0}".format(warning))

    return report


def execute(DesignVolume, VoxelSizeXY, VoxelSizeZ, Run):
    """Execute the complete voxelization workflow."""
    empty_tree = DataTree[object]()

    if not bool(unwrap_gh_value(Run)):
        return (
            [],
            [],
            [],
            [],
            [],
            [],
            empty_tree,
            [
                "Status: Waiting",
                "Set Run to True to generate column voxels."
            ]
        )

    start_time = time.perf_counter()
    size_errors, size_xy, size_z = validate_sizes(
        VoxelSizeXY,
        VoxelSizeZ
    )
    source_meshes, geometry_errors, warnings = (
        collect_closed_source_meshes(DesignVolume)
    )
    errors = size_errors + geometry_errors

    if errors:
        return (
            [],
            [],
            [],
            [],
            [],
            [],
            empty_tree,
            error_report(errors, warnings)
        )

    bounding_box = union_bounding_box(source_meshes)

    if not bounding_box.IsValid:
        return (
            [],
            [],
            [],
            [],
            [],
            [],
            empty_tree,
            error_report(
                ["DesignVolume bounding box is invalid."],
                warnings
            )
        )

    tolerance = active_document_tolerance()
    result = create_voxel_grid(
        source_meshes,
        bounding_box,
        size_xy,
        size_z,
        tolerance
    )

    if result.get("error"):
        return (
            [],
            [],
            [],
            [],
            [],
            [],
            empty_tree,
            error_report([result["error"]], warnings)
        )

    if not result["voxels"]:
        return (
            [],
            [],
            [],
            [],
            [],
            [],
            empty_tree,
            error_report(
                [
                    "No fully contained, base-supported voxels were "
                    "generated. Reduce voxel sizes or check DesignVolume."
                ],
                warnings
            )
        )

    if result["cancelled"]:
        status = "Cancelled"
        warnings.append(
            "Voxelization was cancelled with Escape. Partial output was "
            "discarded; run again to receive a complete synchronized set."
        )
        return (
            [],
            [],
            [],
            [],
            [],
            [],
            empty_tree,
            build_report(
                status,
                time.perf_counter() - start_time,
                len(source_meshes),
                bounding_box,
                size_xy,
                size_z,
                {
                    "candidate_count": result["candidate_count"],
                    "count_x": result["count_x"],
                    "count_y": result["count_y"],
                    "count_z": result["count_z"]
                },
                warnings
            )
        )

    voxel_tree = build_voxel_tree(
        result["voxels"],
        result["column_ids"]
    )
    report = build_report(
        "Completed",
        time.perf_counter() - start_time,
        len(source_meshes),
        bounding_box,
        size_xy,
        size_z,
        result,
        warnings
    )

    return (
        result["voxels"],
        result["voxel_ids"],
        result["column_ids"],
        result["layer_ids"],
        result["centers"],
        result["volumes"],
        voxel_tree,
        report
    )


class Script_Instance(Grasshopper.Kernel.GH_ScriptInstance):
    """Rhino 8 SDK-Mode entry point."""

    def RunScript(
        self,
        DesignVolume: list[rg.GeometryBase],
        VoxelSizeXY: float,
        VoxelSizeZ: float,
        Run: bool
    ):
        """Generate synchronized flat voxel lists and one branch per column."""
        try:
            (
                Voxels,
                VoxelIDs,
                ColumnIDs,
                LayerIDs,
                VoxelCenters,
                VoxelVolumes,
                VoxelTree,
                Report
            ) = execute(
                DesignVolume,
                VoxelSizeXY,
                VoxelSizeZ,
                Run
            )
        except Exception as exception:
            Voxels = []
            VoxelIDs = []
            ColumnIDs = []
            LayerIDs = []
            VoxelCenters = []
            VoxelVolumes = []
            VoxelTree = DataTree[object]()
            Report = [
                "Status: Runtime Error",
                "Error Type: {0}".format(type(exception).__name__),
                "Error Message: {0}".format(str(exception))
            ]

        return (
            Voxels,
            VoxelIDs,
            ColumnIDs,
            LayerIDs,
            VoxelCenters,
            VoxelVolumes,
            VoxelTree,
            Report
        )
