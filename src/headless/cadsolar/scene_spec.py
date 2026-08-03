"""
Build a Scene from a JSON spec, for projects with no CAD file.

An architect describing a massing in conversation ("a 60 by 30 block, 48 m
tall, with the existing housing 25 m to the north") should not have to open
CAD first. This turns a plain dict into the same Scene that dxfio.read_scene
produces, so the rest of the pipeline cannot tell the difference.

Spec shape:

{
  "units": "m",                         optional, "m" (default) or "mm"
  "design": [
    {"name": "方案a", "height": 48,
     "box": [12, 0, 56, 33]}            or "footprint": [[x, y], ...]
  ],
  "context": [
    {"name": "周边a", "height": 45, "box": [62, -34, 96, -2]}
  ],
  "protected_points": [
    {"name": "p1", "x": 2, "y": 52, "z": 1.5}
  ],
  "site": {"box": [-40, -40, 110, 70]}  optional
}

Every geometric error is raised with the offending entry named. A spec that
half-parses is worse than one that fails.
"""

import json

from .dxfio import Scene, SceneError
from .geom import Prism, polygon_area

UNIT_SCALE = {"m": 1.0, "mm": 0.001, "米": 1.0, "毫米": 0.001}


def _footprint(entry, index, role, scale):
    """Return a polygon in metres from either 'box' or 'footprint'."""
    label = entry.get("name") or "{0}[{1}]".format(role, index)

    if "box" in entry:
        box = entry["box"]

        if len(box) != 4:
            raise SceneError(
                "{0} 的 box 需要 4 个数 [x0, y0, x1, y1]，收到 {1} 个。"
                .format(label, len(box))
            )

        x0, y0, x1, y1 = [float(v) * scale for v in box]

        if abs(x1 - x0) < 1e-9 or abs(y1 - y0) < 1e-9:
            raise SceneError("{0} 的 box 退化成了线或点。".format(label))

        x0, x1 = min(x0, x1), max(x0, x1)
        y0, y1 = min(y0, y1), max(y0, y1)
        return label, [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]

    if "footprint" in entry:
        points = [
            (float(x) * scale, float(y) * scale) for x, y in entry["footprint"]
        ]

        if len(points) < 3:
            raise SceneError(
                "{0} 的 footprint 只有 {1} 个点，至少要 3 个。"
                .format(label, len(points))
            )

        if polygon_area(points) < 1e-9:
            raise SceneError(
                "{0} 的 footprint 面积接近 0，可能有重复点或自相交。"
                .format(label)
            )

        return label, points

    raise SceneError("{0} 既没有 box 也没有 footprint。".format(label))


def _height(entry, label, scale):
    if "height" not in entry:
        raise SceneError("{0} 缺少 height。".format(label))

    height = float(entry["height"]) * scale

    if height <= 0.0:
        raise SceneError(
            "{0} 的 height 必须大于 0，收到 {1}。".format(label, height)
        )

    return height


def scene_from_spec(spec):
    """Turn a spec dict into a Scene, in metres."""
    if not isinstance(spec, dict):
        raise SceneError("场景描述必须是一个 JSON 对象。")

    unit = str(spec.get("units", "m")).strip().lower()
    scale = UNIT_SCALE.get(unit)

    if scale is None:
        raise SceneError(
            "units 只支持 m / mm，收到 {0!r}。".format(spec.get("units"))
        )

    scene = Scene()
    scene.unit_scale = scale
    scene.source = "spec"

    for index, entry in enumerate(spec.get("design") or []):
        label, polygon = _footprint(entry, index, "design", scale)
        scene.design.append(Prism(polygon, 0.0, _height(entry, label, scale)))

    for index, entry in enumerate(spec.get("context") or []):
        label, polygon = _footprint(entry, index, "context", scale)
        scene.context.append(Prism(polygon, 0.0, _height(entry, label, scale)))

    for index, entry in enumerate(spec.get("protected_points") or []):
        label = entry.get("name") or "protected_points[{0}]".format(index)

        for key in ("x", "y", "z"):
            if key not in entry:
                raise SceneError("{0} 缺少坐标 {1}。".format(label, key))

        scene.protected_points.append(
            (
                float(entry["x"]) * scale,
                float(entry["y"]) * scale,
                float(entry["z"]) * scale,
            )
        )

    site = spec.get("site")

    if site:
        _, polygon = _footprint(site, 0, "site", scale)
        scene.site = polygon

    if not scene.design:
        raise SceneError("场景描述里没有 design（方案体量）。")

    if not scene.protected_points:
        raise SceneError("场景描述里没有 protected_points（保护点）。")

    return scene


def load_spec(path):
    with open(str(path), "r", encoding="utf-8") as handle:
        return scene_from_spec(json.load(handle))


TEMPLATE = {
    "units": "m",
    "design": [
        {"name": "方案a", "box": [12, 0, 56, 33], "height": 48}
    ],
    "context": [
        {"name": "周边建筑a", "box": [62, -34, 96, -2], "height": 45},
        {"name": "周边建筑b", "box": [-34, -20, -6, 6], "height": 28},
    ],
    "protected_points": [
        {"name": "北侧住宅窗1", "x": 2, "y": 52, "z": 1.5},
        {"name": "北侧住宅窗2", "x": 22, "y": 52, "z": 1.5},
        {"name": "北侧住宅窗3", "x": 42, "y": 52, "z": 1.5},
    ],
}
