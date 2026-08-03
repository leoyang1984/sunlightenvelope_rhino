"""
DXF in, DXF out.

Reads a drawing whose blocks follow the naming convention and returns the
analysis scene. Writes the carved massing back as polyface solids so the
result lands in the architect's own CAD file rather than a viewer format.

Everything is validated loudly. The failure mode that matters for an agent
driven pipeline is not a crash, it is a drawing that parses into a plausible
but wrong scene - an unclosed footprint read as a line, a block left unparsed
and silently dropped. Those are errors here, not warnings.
"""

import ezdxf
from ezdxf import bbox as ezdxf_bbox

from .geom import Prism, polygon_area
from .naming import (
    NameError_,
    ROLE_CONTEXT,
    ROLE_DESIGN,
    ROLE_POINT,
    ROLE_SITE,
    parse_block_name,
)

INSUNITS_TO_METERS = {
    0: None,     # unitless, must be declared by the caller
    1: 0.0254,   # inches
    2: 0.3048,   # feet
    4: 0.001,    # millimeters
    5: 0.01,     # centimeters
    6: 1.0,      # meters
}

MIN_FOOTPRINT_AREA_M2 = 1.0e-6


class SceneError(ValueError):
    """Raised when a drawing cannot be turned into a valid analysis scene."""


class Scene(object):
    """Everything the pipeline needs, in meters, Z up."""

    __slots__ = (
        "design", "context", "protected_points", "site",
        "unit_scale", "warnings", "source"
    )

    def __init__(self):
        self.design = []
        self.context = []
        self.protected_points = []
        self.site = None
        self.unit_scale = 1.0
        self.warnings = []
        self.source = None


def _drawing_scale(doc, unit_override):
    if unit_override is not None:
        return float(unit_override)

    code = int(doc.header.get("$INSUNITS", 0))
    scale = INSUNITS_TO_METERS.get(code)

    if scale is None:
        raise SceneError(
            "图纸没有声明单位（$INSUNITS = {0}）。"
            "请在 CAD 里设定单位，或调用时显式传入 unit_scale。".format(code)
        )

    return scale


def _polyline_points(entity):
    """Return the 2D vertices of a closed polyline entity, or None."""
    kind = entity.dxftype()

    if kind == "LWPOLYLINE":
        points = [(p[0], p[1]) for p in entity.get_points("xy")]
        closed = bool(entity.closed)
    elif kind == "POLYLINE":
        points = [(v.dxf.location.x, v.dxf.location.y) for v in entity.vertices]
        closed = bool(entity.is_closed)
    else:
        return None, False

    return points, closed


def _collect_from_container(entities):
    """Split a block's virtual entities into footprints and point locations."""
    footprints = []
    locations = []
    open_polylines = 0

    for entity in entities:
        kind = entity.dxftype()

        if kind in ("LWPOLYLINE", "POLYLINE"):
            points, closed = _polyline_points(entity)

            if points is None or len(points) < 3:
                continue

            if not closed:
                first, last = points[0], points[-1]

                if (
                    abs(first[0] - last[0]) > 1.0e-6 or
                    abs(first[1] - last[1]) > 1.0e-6
                ):
                    open_polylines += 1
                    continue

            footprints.append(points)
        elif kind == "POINT":
            location = entity.dxf.location
            locations.append((location.x, location.y))
        elif kind == "CIRCLE":
            center = entity.dxf.center
            locations.append((center.x, center.y))

    return footprints, locations, open_polylines


def read_scene(path, unit_scale=None):
    """
    Parse a DXF into a Scene.

    unit_scale overrides $INSUNITS and is expressed as meters per drawing unit.
    """
    doc = ezdxf.readfile(str(path))
    scale = _drawing_scale(doc, unit_scale)
    modelspace = doc.modelspace()

    scene = Scene()
    scene.unit_scale = scale
    scene.source = str(path)

    inserts = list(modelspace.query("INSERT"))

    if not inserts:
        raise SceneError(
            "模型空间里没有块参照（INSERT）。"
            "本约定要求把每个体量做成块，块名带角色和高度。"
        )

    name_errors = []
    seen_roles = {ROLE_DESIGN: 0, ROLE_CONTEXT: 0, ROLE_POINT: 0}

    for insert in inserts:
        block_name = insert.dxf.name

        try:
            parsed = parse_block_name(block_name)
        except NameError_ as error:
            name_errors.append(str(error))
            continue

        try:
            virtual = list(insert.virtual_entities())
        except Exception as error:
            name_errors.append(
                "块 {0!r} 无法展开：{1}".format(block_name, error)
            )
            continue

        footprints, locations, open_polylines = _collect_from_container(virtual)

        if open_polylines:
            name_errors.append(
                "块 {0!r} 里有 {1} 条未闭合的多段线。"
                "轮廓必须闭合，否则无法确定体量范围。".format(
                    block_name, open_polylines
                )
            )
            continue

        if parsed.role == ROLE_POINT:
            if not locations:
                name_errors.append(
                    "保护点块 {0!r} 里没有 POINT 实体。".format(block_name)
                )
                continue

            for x, y in locations:
                scene.protected_points.append(
                    (x * scale, y * scale, parsed.meters)
                )
            seen_roles[ROLE_POINT] += len(locations)
            continue

        if not footprints:
            name_errors.append(
                "块 {0!r} 里没有闭合轮廓多段线。".format(block_name)
            )
            continue

        for points in footprints:
            scaled = [(x * scale, y * scale) for x, y in points]

            if polygon_area(scaled) < MIN_FOOTPRINT_AREA_M2:
                name_errors.append(
                    "块 {0!r} 的一条轮廓面积接近 0，可能是重复点或退化多段线。"
                    .format(block_name)
                )
                continue

            if parsed.role == ROLE_SITE:
                scene.site = scaled
                continue

            prism = Prism(scaled, 0.0, parsed.meters)

            if parsed.role == ROLE_DESIGN:
                scene.design.append(prism)
                seen_roles[ROLE_DESIGN] += 1
            else:
                scene.context.append(prism)
                seen_roles[ROLE_CONTEXT] += 1

    if name_errors:
        raise SceneError(
            "图纸解析失败，共 {0} 处：\n  - {1}".format(
                len(name_errors), "\n  - ".join(name_errors)
            )
        )

    if not scene.design:
        raise SceneError("图纸里没有方案体量（方案* 或 scheme* 块）。")

    if not scene.protected_points:
        raise SceneError("图纸里没有保护点（保护点* 或 point* 块）。")

    return scene


# ----------------------------------------------------------------- writing

def _polyface_from_prism(polyface, prism):
    """Append one closed prism to a polyface mesh."""
    ring = prism.polygon
    count = len(ring)
    bottom = [(x, y, prism.z_low) for x, y in ring]
    top = [(x, y, prism.z_high) for x, y in ring]

    polyface.append_face(bottom[::-1])
    polyface.append_face(top)

    for index in range(count):
        next_index = (index + 1) % count
        polyface.append_face(
            [
                bottom[index],
                bottom[next_index],
                top[next_index],
                top[index],
            ]
        )


def write_result(
    path,
    kept,
    removed,
    protected_points,
    context,
    unit_scale,
    layer_kept="日照-保留体量",
    layer_removed="日照-切除体量",
    layer_points="日照-保护点",
):
    """Write the carved massing back into a DXF, in the original units."""
    inverse = 1.0 / float(unit_scale)
    doc = ezdxf.new("R2010", setup=True)
    doc.header["$INSUNITS"] = 4 if abs(unit_scale - 0.001) < 1e-12 else 6
    modelspace = doc.modelspace()

    for name, color in (
        (layer_kept, 3),
        (layer_removed, 1),
        (layer_points, 5),
    ):
        if name not in doc.layers:
            doc.layers.add(name, color=color)

    def scaled_prism(prism):
        return Prism(
            [(x * inverse, y * inverse) for x, y in prism.polygon],
            prism.z_low * inverse,
            prism.z_high * inverse,
        )

    for group, layer in ((kept, layer_kept), (removed, layer_removed)):
        for prism in group:
            polyface = modelspace.add_polyface(dxfattribs={"layer": layer})
            _polyface_from_prism(polyface, scaled_prism(prism))

    for x, y, z in protected_points:
        modelspace.add_point(
            (x * inverse, y * inverse, z * inverse),
            dxfattribs={"layer": layer_points},
        )

    doc.saveas(str(path))
    return str(path)


def write_obj(path, prisms, protected_points=()):
    """Write a plain OBJ for quick viewing without any CAD software."""
    lines = []
    offset = 1

    for prism in prisms:
        ring = prism.polygon
        count = len(ring)

        for x, y in ring:
            lines.append("v {0:.6f} {1:.6f} {2:.6f}".format(x, y, prism.z_low))

        for x, y in ring:
            lines.append("v {0:.6f} {1:.6f} {2:.6f}".format(x, y, prism.z_high))

        bottom = list(range(offset, offset + count))
        top = list(range(offset + count, offset + 2 * count))
        lines.append("f " + " ".join(str(i) for i in reversed(bottom)))
        lines.append("f " + " ".join(str(i) for i in top))

        for index in range(count):
            next_index = (index + 1) % count
            lines.append(
                "f {0} {1} {2} {3}".format(
                    bottom[index],
                    bottom[next_index],
                    top[next_index],
                    top[index],
                )
            )

        offset += 2 * count

    for x, y, z in protected_points:
        lines.append("v {0:.6f} {1:.6f} {2:.6f}".format(x, y, z))

    with open(str(path), "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")

    return str(path)
