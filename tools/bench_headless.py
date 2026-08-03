"""
Where does pure Python die, and does a broad phase fix it?

The reference implementation is the repo's own build_event_voxel_paths, run
verbatim: it calls the ray primitive once per (point, sample, voxel). That is
the O(n^3) inner loop and the only part of the pipeline with a scaling problem.

The accelerated version keeps the exact same output but adds a numpy slab test
over voxel bounding boxes as a broad phase, so the exact prism test only runs
on candidates. Equivalence is asserted, not assumed.
"""

import pathlib
import sys
import time

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).parents[1] / "src" / "headless"))

from cadsolar import dxfio, kernel, pipeline  # noqa: E402
from cadsolar.geom import EPS  # noqa: E402

OPTIMIZER = kernel.load_optimizer()


def build_bbox_array(records):
    return np.array([record["geometry"].bbox for record in records], dtype=float)


def broad_phase(boxes, origin, direction):
    """Vectorized slab test; returns indices whose bbox the ray may enter."""
    lows = boxes[:, 0:3]
    highs = boxes[:, 3:6]
    origin = np.asarray(origin, dtype=float)
    direction = np.asarray(direction, dtype=float)

    with np.errstate(divide="ignore", invalid="ignore"):
        inverse = 1.0 / direction
        t_low = (lows - origin) * inverse
        t_high = (highs - origin) * inverse

    t_near = np.minimum(t_low, t_high)
    t_far = np.maximum(t_low, t_high)

    parallel = np.abs(direction) < EPS
    if parallel.any():
        inside = (origin >= lows - EPS) & (origin <= highs + EPS)
        t_near[:, parallel] = -np.inf
        t_far[:, parallel] = np.where(inside[:, parallel], np.inf, -np.inf)

    enter = t_near.max(axis=1)
    exit_ = t_far.min(axis=1)
    return np.nonzero((exit_ >= enter) & (exit_ > EPS))[0]


def accelerated_paths(points, samples, context, records, origin_offset):
    """Same contract as build_event_voxel_paths, with a broad phase."""
    boxes = build_bbox_array(records)
    baseline_flags = []
    paths = []
    ray_tests = 0

    for point in points:
        point_flags = []
        point_paths = []

        for sample in samples:
            vector = sample["vector"]
            blocked = False

            if context is not None:
                origin = tuple(
                    point[i] + vector[i] * origin_offset for i in range(3)
                )
                blocked = context.ray_distance(origin, vector) >= 0.0
                ray_tests += 1

            if blocked:
                point_flags.append(False)
                point_paths.append([])
                continue

            point_flags.append(True)
            origin = tuple(
                point[i] + vector[i] * origin_offset for i in range(3)
            )
            hits = []

            for index in broad_phase(boxes, origin, vector):
                distance = records[index]["geometry"].ray_distance(
                    origin, vector
                )
                ray_tests += 1

                if distance >= 0.0:
                    hits.append((distance, records[index]["index"]))

            hits.sort(key=lambda item: item[0])
            point_paths.append([item[1] for item in hits])

        baseline_flags.append(point_flags)
        paths.append(point_paths)

    return {
        "baseline_flags": baseline_flags,
        "paths": paths,
        "ray_test_count": ray_tests,
        "context_errors": 0,
        "voxel_errors": 0,
        "cancelled": False,
    }


def run_case(scene, voxel_size, time_step, label):
    settings = pipeline.Settings(
        voxel_size_xy=voxel_size,
        voxel_size_z=voxel_size,
        time_step=time_step,
    )
    grid = pipeline.voxelize(scene.design, voxel_size, voxel_size)
    context = (
        pipeline.PrismSet(scene.context) if scene.context else None
    )
    points = list(scene.protected_points)
    north, east = pipeline.north_east_vectors(0.0)

    intervals = OPTIMIZER["generate_time_intervals"](
        settings.year, settings.month, settings.day,
        settings.start_hour, settings.end_hour, settings.time_step,
    )
    samples, _ = OPTIMIZER["calculate_sun_samples"](
        intervals, settings.latitude, settings.longitude,
        settings.timezone, north, east,
    )
    scale = pipeline.model_scale(
        points, [r["geometry"] for r in grid.records], context
    )
    offset = scale * OPTIMIZER["RAY_ORIGIN_OFFSET_FACTOR"]

    nominal = len(points) * len(samples) * len(grid.records)

    started = time.perf_counter()
    reference = OPTIMIZER["build_event_voxel_paths"](
        points, samples, context, grid.records, offset
    )
    reference_seconds = time.perf_counter() - started

    started = time.perf_counter()
    fast = accelerated_paths(points, samples, context, grid.records, offset)
    fast_seconds = time.perf_counter() - started

    identical = (
        reference["paths"] == fast["paths"] and
        reference["baseline_flags"] == fast["baseline_flags"]
    )

    print(
        "{0:<22} {1:>6} 体素 {2:>4} 样本 {3:>4} 点 {4:>12,} 次 "
        "{5:>8.2f}s {6:>8.2f}s {7:>7.1f}x  {8}".format(
            label,
            len(grid.records),
            len(samples),
            len(points),
            nominal,
            reference_seconds,
            fast_seconds,
            reference_seconds / fast_seconds if fast_seconds > 0 else 0.0,
            "一致" if identical else "不一致!",
        )
    )
    return nominal, reference_seconds, fast_seconds, identical


def main():
    root = pathlib.Path(__file__).parents[1] / "src" / "headless"
    scene = dxfio.read_scene(root / "scene" / "reference.dxf")

    print("=" * 118)
    print("射线映射阶段：仓库原版 build_event_voxel_paths  vs  加了 numpy 粗筛的版本")
    print("=" * 118)
    print("{0:<22} {1:>9} {2:>10} {3:>9} {4:>14} {5:>9} {6:>9} {7:>8}  {8}".format(
        "场景", "体素", "样本", "点", "标称射线测试", "原版", "加速版", "倍数", "输出"))
    print("-" * 118)

    cases = [
        (6.0, 10.0, "教程档 6m/10min"),
        (4.0, 10.0, "4m/10min"),
        (3.0, 5.0, "3m/5min"),
        (2.0, 5.0, "2m/5min"),
        (2.0, 2.0, "2m/2min"),
    ]

    results = []

    for voxel_size, time_step, label in cases:
        results.append(run_case(scene, voxel_size, time_step, label))

    print("-" * 118)

    nominal, reference_seconds, fast_seconds, _ = results[-1]
    reference_rate = nominal / reference_seconds
    fast_rate = nominal / fast_seconds

    print()
    print("外推到组件里写的 2000 万次射线×体素安全上限：")
    print("  原版        {0:>12,.0f} 次/秒  ->  {1:>8.1f} 分钟".format(
        reference_rate, 20e6 / reference_rate / 60))
    print("  加粗筛      {0:>12,.0f} 次/秒  ->  {1:>8.1f} 分钟".format(
        fast_rate, 20e6 / fast_rate / 60))
    print()
    print("参考：Rhino 实机验收记录 165,560 次 MeshRay 用时 6.223 秒 "
          "= {0:,.0f} 次/秒".format(165560 / 6.223))


if __name__ == "__main__":
    main()
