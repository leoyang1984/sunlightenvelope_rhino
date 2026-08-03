"""
Run the shipping Rhino components on the spike's reference scene.

Driven through rhinocode, so no Grasshopper canvas is involved. Both R8
components expose a module-level execute() taking plain arguments;
Script_Instance.RunScript is only a thin wrapper over it.

The scene is built here with RhinoCommon to be geometrically identical to
spike/scene/reference.dxf, in millimetres (matching the Rhino document unit).

Results land in rhino_result.json for the pure-Python side to compare against.
"""

import importlib.util
import json
import pathlib
import time
import traceback

import Rhino
import Rhino.Geometry as rg
import scriptcontext as sc

HERE = pathlib.Path(__file__).parent
REPO = HERE.parent
RESULT = REPO / "src" / "headless" / "rhino_result.json"
STARTED = time.time()

MM = 1000.0

# Same numbers as spike/make_scene.py, in metres.
DESIGN_POLYGON = [(12, 0), (56, 0), (44, 33), (12, 33)]
DESIGN_HEIGHT = 48.0

CONTEXT = [
    ([(62, -34), (96, -34), (96, -2), (62, -2)], 45.0),
    ([(-34, -20), (-6, -20), (-6, 6), (-34, 6)], 28.0),
]

PROTECTED_POINTS = [(2, 52, 1.5), (22, 52, 1.5), (42, 52, 1.5), (62, 52, 1.5)]

SETTINGS = {
    "Latitude": 31.233333,
    "Longitude": 121.466667,
    "TimeZone": 8.0,
    "Year": 2024,
    "Month": 12,
    "Day": 21,
    "StartHour": 9.0,
    "EndHour": 15.0,
    "TimeStep": 10.0,
    "MinimumContinuousMinutes": 60.0,
    "RequiredSunHours": 2.0,
    "MaxIterations": 200,
    "VoxelSizeXY": 6.0 * MM,
    "VoxelSizeZ": 6.0 * MM,
    "ImpactTolerance": 0.1,
}


def load(name, filename):
    path = REPO / "src" / "rhino8" / filename
    spec = importlib.util.spec_from_file_location(name, str(path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def extrusion_brep(polygon_metres, height_metres):
    """
    Closed solid from a polygon footprint, in millimetres, standing on z=0.

    Extrusion.Create extrudes along the curve plane normal, so the sign has to
    follow the winding. Getting this wrong builds the volume underground,
    where it blocks nothing and the whole comparison is meaningless.
    """
    points = [
        rg.Point3d(x * MM, y * MM, 0.0) for x, y in polygon_metres
    ]
    points.append(points[0])
    curve = rg.PolylineCurve(points)

    if not curve.IsClosed:
        raise ValueError("footprint curve did not close")

    for height in (height_metres * MM, -height_metres * MM):
        extrusion = rg.Extrusion.Create(curve, height, True)

        if extrusion is None:
            continue

        brep = extrusion.ToBrep()

        if brep is None or not brep.IsSolid:
            continue

        box = brep.GetBoundingBox(True)

        if box.Min.Z >= -1.0 and box.Max.Z > 1.0:
            return brep

    raise ValueError("could not build an upward closed solid")


def main():
    out = {}

    def checkpoint(stage, **fields):
        """Flush progress after every stage so it can be watched live."""
        out["stage"] = stage
        out["elapsed_seconds"] = round(time.time() - STARTED, 3)
        out.update(fields)
        RESULT.write_text(
            json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    checkpoint("loading components")
    voxelizer = load("voxelizer", "SolarDesignVoxelizer_Rhino8_SDK.py")
    optimizer = load("optimizer", "SolarVoxelOptimizer_Rhino8_SDK.py")
    solver = load("solver", "SolarConstraintSolver_Rhino8_SDK.py")
    checkpoint("components loaded")

    design = extrusion_brep(DESIGN_POLYGON, DESIGN_HEIGHT)
    context = [
        extrusion_brep(polygon, height) for polygon, height in CONTEXT
    ]
    points = [
        rg.Point3d(x * MM, y * MM, z * MM) for x, y, z in PROTECTED_POINTS
    ]
    north = rg.Vector3d(0.0, 1.0, 0.0)

    checkpoint("scene built")
    out["scene"] = {
        "design_volume_mm3": design.GetVolume(),
        "context_count": len(context),
        "point_count": len(points),
        # Under rhinocode there is no document at all: both RhinoDoc.ActiveDoc
        # and scriptcontext.doc are None. The components already fall back to
        # tolerance 0.001 and units "Unknown", so record what they will see
        # rather than asserting a document exists.
        "document_units": voxelizer.active_document_units(),
        "document_tolerance": voxelizer.active_document_tolerance(),
        "active_doc_present": Rhino.RhinoDoc.ActiveDoc is not None,
        "scriptcontext_doc_present": sc.doc is not None,
    }

    checkpoint("running component1")
    # ---------------------------------------------------------- 组件1
    (
        voxels,
        voxel_ids,
        column_ids,
        layer_ids,
        voxel_centers,
        voxel_volumes,
        voxel_tree,
        voxel_report,
    ) = voxelizer.execute(
        [design], SETTINGS["VoxelSizeXY"], SETTINGS["VoxelSizeZ"], True
    )

    out["component1"] = {
        "report": list(voxel_report),
        "voxel_count": len(list(voxels)),
        "total_volume_mm3": sum(float(v) for v in voxel_volumes),
    }

    checkpoint("component1 done", component1=out.get("component1"))
    # ---------------------------------------------------------- 组件2
    (
        kept_voxels,
        removed_voxels,
        optimized_columns,
        keep_mask,
        initial_hours,
        final_hours,
        impact_hours,
        event_tree,
        iteration_data,
        optimizer_report,
    ) = optimizer.execute(
        points,
        list(voxels),
        list(voxel_ids),
        list(column_ids),
        list(layer_ids),
        context,
        north,
        SETTINGS["Latitude"],
        SETTINGS["Longitude"],
        SETTINGS["TimeZone"],
        SETTINGS["Year"],
        SETTINGS["Month"],
        SETTINGS["Day"],
        SETTINGS["StartHour"],
        SETTINGS["EndHour"],
        SETTINGS["TimeStep"],
        SETTINGS["MinimumContinuousMinutes"],
        SETTINGS["RequiredSunHours"],
        SETTINGS["MaxIterations"],
        True,
    )

    kept = list(kept_voxels)
    removed = list(removed_voxels)
    mask = [bool(v) for v in keep_mask]
    kept_volume = sum(
        float(volume)
        for volume, keep in zip(voxel_volumes, mask)
        if keep
    )
    total_volume = sum(float(v) for v in voxel_volumes)

    out["component2"] = {
        "report": list(optimizer_report),
        "kept": len(kept),
        "removed": len(removed),
        "initial_hours": [float(v) for v in initial_hours],
        "final_hours": [float(v) for v in final_hours],
        "iterations": len(list(iteration_data)),
        "retained_ratio": (
            kept_volume / total_volume if total_volume else 0.0
        ),
    }

    checkpoint("component2 done", component2=out.get("component2"))
    # ------------------------------------------------- 组件0 After
    sun_hours, violation_data, constraint_tree, solver_report = solver.execute(
        points,
        kept,
        context,
        north,
        SETTINGS["Latitude"],
        SETTINGS["Longitude"],
        SETTINGS["TimeZone"],
        SETTINGS["Year"],
        SETTINGS["Month"],
        SETTINGS["Day"],
        SETTINGS["StartHour"],
        SETTINGS["EndHour"],
        SETTINGS["TimeStep"],
        SETTINGS["MinimumContinuousMinutes"],
        SETTINGS["RequiredSunHours"],
        SETTINGS["ImpactTolerance"],
        True,
    )

    out["component0_after"] = {
        "report": list(solver_report),
        "sun_hours": [float(v) for v in sun_hours],
    }

    checkpoint("all done")
    return out


if __name__ == "__main__":
    try:
        payload = main()
    except Exception:
        payload = {"error": traceback.format_exc()}

    RESULT.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )
