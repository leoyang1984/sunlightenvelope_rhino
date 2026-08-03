"""
Write the reference DXF scene, using the block-naming convention only.

Layout, in millimetres, north = +Y, Shanghai:

    y=+55m   保护点1/2/3   three protected windows on an existing north block
    y=0..30  方案a-36m     the proposed volume, 30 m wide, 36 m tall
    y=-25..0 周边建筑a-30m an existing block southeast, shading the morning

The design sits directly south of the protected points, so on the winter
solstice it is exactly what blocks their sun. That is the case worth testing;
a design north of the points would never violate anything.
"""

import ezdxf

MM = 1000.0


def rect(x0, y0, x1, y1):
    return [(x0 * MM, y0 * MM), (x1 * MM, y0 * MM),
            (x1 * MM, y1 * MM), (x0 * MM, y1 * MM)]


def add_footprint_block(doc, name, polygon):
    block = doc.blocks.new(name=name)
    block.add_lwpolyline(polygon, close=True)
    return block


def add_point_block(doc, name):
    block = doc.blocks.new(name=name)
    block.add_point((0, 0, 0))
    return block


def build(path):
    doc = ezdxf.new("R2010", setup=True)
    doc.header["$INSUNITS"] = 4  # millimetres
    modelspace = doc.modelspace()

    # Non-rectangular on purpose: the sloped east edge forces boundary cells
    # through the polygon-clip path that replaces Brep Boolean intersection.
    design = [
        (12 * MM, 0 * MM),
        (56 * MM, 0 * MM),
        (44 * MM, 33 * MM),
        (12 * MM, 33 * MM),
    ]
    add_footprint_block(doc, "方案a-48m", design)
    modelspace.add_blockref("方案a-48m", (0, 0))

    # Southeast, tall: eats the morning sun for the eastern points, so the
    # baseline is not a flat 6 h and the solvable/unsolvable split is real.
    add_footprint_block(doc, "周边建筑a-45m", rect(62, -34, 96, -2))
    modelspace.add_blockref("周边建筑a-45m", (0, 0))

    # Southwest, lower: trims the late afternoon on the western side.
    add_footprint_block(doc, "周边建筑b-28m", rect(-34, -20, -6, 6))
    modelspace.add_blockref("周边建筑b-28m", (0, 0))

    add_footprint_block(doc, "地块-0m", rect(-40, -40, 110, 70))
    modelspace.add_blockref("地块-0m", (0, 0))

    add_point_block(doc, "保护点a-1.5m")

    for x in (2.0, 22.0, 42.0, 62.0):
        modelspace.add_blockref("保护点a-1.5m", (x * MM, 52 * MM))

    doc.saveas(str(path))
    return str(path)


if __name__ == "__main__":
    import pathlib
    target = pathlib.Path(__file__).parent / "scene" / "reference.dxf"
    target.parent.mkdir(parents=True, exist_ok=True)
    print(build(target))
