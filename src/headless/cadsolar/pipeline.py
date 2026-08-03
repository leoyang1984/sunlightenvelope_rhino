"""
The three components, headless.

组件1 voxelize()            2.5D grid + polygon clip, replaces Brep Boolean
组件2 optimize()            the repo's own optimize_voxels, unmodified
组件0 verify()              the repo's own solve_protected_points, unmodified

Only 组件1 is new code. 组件0 and 组件2 are loaded out of src/rhino8/ by
kernel.py and run as written.
"""

import math
import time

from . import kernel
from .geom import (
    EPS,
    Prism,
    PrismSet,
    clip_polygon_to_rect,
    polygon_area,
)


# ------------------------------------------------------------- 组件1

class VoxelGrid(object):
    """Result of voxelizing the design volume."""

    __slots__ = (
        "records", "column_members", "columns", "layers",
        "full_count", "clipped_count", "candidate_cells",
        "total_volume", "warnings", "origin", "size_xy", "size_z"
    )

    def __init__(self):
        self.records = []
        self.column_members = {}
        self.columns = 0
        self.layers = 0
        self.full_count = 0
        self.clipped_count = 0
        self.candidate_cells = 0
        self.total_volume = 0.0
        self.warnings = []
        self.origin = (0.0, 0.0, 0.0)
        self.size_xy = 0.0
        self.size_z = 0.0


def voxelize(design_prisms, size_xy, size_z, max_voxels=250000):
    """
    Split the design volume into a column/layer indexed voxel set.

    Mirrors the 组件1 contract: grid anchored at the union bounding-box
    minimum, full cells kept as regular boxes, boundary cells clipped to the
    design outline instead of being dropped, every layer judged independently,
    ColumnID by XY grid position and LayerID global.
    """
    if size_xy <= 0.0 or size_z <= 0.0:
        raise ValueError("VoxelSizeXY 和 VoxelSizeZ 必须大于 0。")

    if not design_prisms:
        raise ValueError("没有方案体量可以体素化。")

    boxes = [prism.bbox for prism in design_prisms]
    x_min = min(box[0] for box in boxes)
    y_min = min(box[1] for box in boxes)
    z_min = min(box[2] for box in boxes)
    x_max = max(box[3] for box in boxes)
    y_max = max(box[4] for box in boxes)
    z_max = max(box[5] for box in boxes)

    nx = max(1, int(math.ceil((x_max - x_min) / size_xy - EPS)))
    ny = max(1, int(math.ceil((y_max - y_min) / size_xy - EPS)))
    nz = max(1, int(math.ceil((z_max - z_min) / size_z - EPS)))

    if nx * ny * nz > max_voxels:
        raise ValueError(
            "候选体素 {0} 个，超过安全上限 {1}。"
            "多半是体素尺寸单位写错了。".format(nx * ny * nz, max_voxels)
        )

    grid = VoxelGrid()
    grid.origin = (x_min, y_min, z_min)
    grid.size_xy = float(size_xy)
    grid.size_z = float(size_z)
    grid.layers = nz

    column_id = 0
    voxel_id = 0

    for j in range(ny):
        for i in range(nx):
            cell_x0 = x_min + i * size_xy
            cell_y0 = y_min + j * size_xy
            # Clamp the last row/column to the bounding box, the way 组件1
            # does. Geometry and volume are the same either way, but the
            # full-vs-clipped counter is measured against the clamped cell.
            cell_x1 = min(cell_x0 + size_xy, x_max)
            cell_y1 = min(cell_y0 + size_xy, y_max)
            full_cell_area = (cell_x1 - cell_x0) * (cell_y1 - cell_y0)

            pieces = []

            for prism in design_prisms:
                clipped = clip_polygon_to_rect(
                    prism.polygon, cell_x0, cell_y0, cell_x1, cell_y1
                )

                if len(clipped) < 3:
                    continue

                area = polygon_area(clipped)

                if area <= EPS:
                    continue

                pieces.append((area, clipped, prism))

            if not pieces:
                continue

            if len(pieces) > 1:
                grid.warnings.append(
                    "列 ({0},{1}) 有 {2} 个方案体量重叠，本 spike 只取"
                    "面积最大的一个，未做实体并集。".format(i, j, len(pieces))
                )

            pieces.sort(key=lambda item: item[0], reverse=True)
            area, footprint, prism = pieces[0]

            column_has_voxel = False

            for k in range(nz):
                layer_z0 = z_min + k * size_z
                layer_z1 = min(layer_z0 + size_z, z_max)
                low = max(layer_z0, prism.z_low)
                high = min(layer_z1, prism.z_high)
                grid.candidate_cells += 1

                if high - low <= EPS:
                    continue

                clipped_geometry = (
                    area < full_cell_area - EPS or
                    (high - low) < size_z - EPS
                )

                voxel = Prism(footprint, low, high)
                volume = area * (high - low)

                record = {
                    "index": len(grid.records),
                    "id": voxel_id,
                    "column_id": column_id,
                    "layer_id": k,
                    "geometry": voxel,
                    "mesh": voxel,
                    "bbox": voxel.bbox,
                    "volume": volume,
                    "center": voxel.center,
                    "clipped": clipped_geometry,
                }
                grid.records.append(record)
                grid.column_members.setdefault(column_id, []).append(
                    record["index"]
                )
                grid.total_volume += volume
                voxel_id += 1
                column_has_voxel = True

                if clipped_geometry:
                    grid.clipped_count += 1
                else:
                    grid.full_count += 1

            if column_has_voxel:
                column_id += 1

    grid.columns = column_id

    for members in grid.column_members.values():
        members.sort(key=lambda index: grid.records[index]["layer_id"])

    return grid


# ------------------------------------------------------------ orchestration

def north_east_vectors(north_angle_degrees=0.0):
    """Project north/east unit vectors for the given north rotation."""
    angle = math.radians(north_angle_degrees)
    north = (-math.sin(angle), math.cos(angle), 0.0)
    east = (north[1], -north[0], 0.0)
    return north, east


def model_scale(points, prisms, context):
    """Bounding-box diagonal used for the ray-origin offset."""
    xs, ys, zs = [], [], []

    for x, y, z in points:
        xs.append(x)
        ys.append(y)
        zs.append(z)

    boxes = [prism.bbox for prism in prisms]

    if context is not None:
        box = context.bounding_box()

        if box is not None:
            boxes.append(box)

    for box in boxes:
        xs.extend([box[0], box[3]])
        ys.extend([box[1], box[4]])
        zs.extend([box[2], box[5]])

    if not xs:
        return 1.0

    diagonal = math.sqrt(
        (max(xs) - min(xs)) ** 2 +
        (max(ys) - min(ys)) ** 2 +
        (max(zs) - min(zs)) ** 2
    )
    return max(diagonal, 1.0)


class Settings(object):
    """Analysis parameters, matching the component input names."""

    def __init__(self, **kwargs):
        self.latitude = kwargs.get("latitude", 31.233333)
        self.longitude = kwargs.get("longitude", 121.466667)
        self.timezone = kwargs.get("timezone", 8.0)
        self.year = kwargs.get("year", 2024)
        self.month = kwargs.get("month", 12)
        self.day = kwargs.get("day", 21)
        self.start_hour = kwargs.get("start_hour", 9.0)
        self.end_hour = kwargs.get("end_hour", 15.0)
        self.time_step = kwargs.get("time_step", 10.0)
        self.minimum_continuous_minutes = kwargs.get(
            "minimum_continuous_minutes", 60.0
        )
        self.required_sun_hours = kwargs.get("required_sun_hours", 2.0)
        self.impact_tolerance = kwargs.get("impact_tolerance", 0.1)
        self.max_iterations = kwargs.get("max_iterations", 200)
        self.north_angle = kwargs.get("north_angle", 0.0)
        self.voxel_size_xy = kwargs.get("voxel_size_xy", 6.0)
        self.voxel_size_z = kwargs.get("voxel_size_z", 6.0)


def run(scene, settings):
    """Run 组件1 -> 组件2 -> 组件0 After and return one result dict."""
    optimizer = kernel.load_optimizer()
    solver = kernel.load_solver()

    started = time.perf_counter()

    grid = voxelize(
        scene.design, settings.voxel_size_xy, settings.voxel_size_z
    )
    voxelize_seconds = time.perf_counter() - started

    context = PrismSet(scene.context) if scene.context else None
    points = list(scene.protected_points)
    north, east = north_east_vectors(settings.north_angle)

    intervals = optimizer["generate_time_intervals"](
        settings.year,
        settings.month,
        settings.day,
        settings.start_hour,
        settings.end_hour,
        settings.time_step,
    )
    samples, below_horizon = optimizer["calculate_sun_samples"](
        intervals,
        settings.latitude,
        settings.longitude,
        settings.timezone,
        north,
        east,
    )

    if not samples:
        raise ValueError("分析时段内太阳都在地平线以下。")

    scale = model_scale(
        points,
        [record["geometry"] for record in grid.records],
        context,
    )
    origin_offset = scale * optimizer["RAY_ORIGIN_OFFSET_FACTOR"]

    mapping_started = time.perf_counter()
    mapping = optimizer["build_event_voxel_paths"](
        points,
        samples,
        context,
        grid.records,
        origin_offset,
    )
    mapping_seconds = time.perf_counter() - mapping_started

    optimize_started = time.perf_counter()
    outcome = optimizer["optimize_voxels"](
        grid.records,
        grid.column_members,
        mapping["baseline_flags"],
        mapping["paths"],
        samples,
        settings.minimum_continuous_minutes,
        settings.required_sun_hours,
        settings.max_iterations,
    )
    optimize_seconds = time.perf_counter() - optimize_started

    keep_mask = outcome["keep_mask"]
    kept = [
        record["geometry"]
        for record, keep in zip(grid.records, keep_mask) if keep
    ]
    removed = [
        record["geometry"]
        for record, keep in zip(grid.records, keep_mask) if not keep
    ]
    kept_volume = sum(
        record["volume"]
        for record, keep in zip(grid.records, keep_mask) if keep
    )

    # 组件0 After: independent re-check with the solver, not the optimizer.
    verify_started = time.perf_counter()
    verification = solver["solve_protected_points"](
        points,
        samples,
        context,
        PrismSet(kept) if kept else None,
        origin_offset,
        settings.minimum_continuous_minutes,
        settings.required_sun_hours,
        settings.impact_tolerance,
    )
    verify_seconds = time.perf_counter() - verify_started

    return {
        "grid": grid,
        "samples": samples,
        "below_horizon": below_horizon,
        "mapping": mapping,
        "outcome": outcome,
        "kept": kept,
        "removed": removed,
        "kept_volume": kept_volume,
        "retained_ratio": (
            kept_volume / grid.total_volume if grid.total_volume > 0 else 0.0
        ),
        "verification": verification,
        "timing": {
            "voxelize": voxelize_seconds,
            "mapping": mapping_seconds,
            "optimize": optimize_seconds,
            "verify": verify_seconds,
            "total": time.perf_counter() - started,
        },
    }
