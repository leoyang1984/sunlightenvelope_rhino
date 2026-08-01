"""
Generate the 24x24 component icons.

Icons are committed under tools/icons and copied into every bundle by
build_ghuser_bundles.py, so the Rhino 7 and Rhino 8 flavours of one component
always look identical.

Everything is drawn at 8x and downsampled, which is why the shapes are all
whole pixels at 24x24: at this size an anti-aliased edge reads as mud.

Usage
-----
    python3 tools/make_icons.py

Requires Pillow. This is a design-time tool; the generated PNGs are committed
so a normal build does not need it.
"""

import os

from PIL import Image, ImageDraw


REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ICON_DIR = os.path.join(REPO_ROOT, "tools", "icons")

S = 24
SS = 8

KEPT = (52, 90, 136, 255)      # voxel that survives
CLIP = (135, 175, 214, 255)    # boundary-clipped or highlighted voxel
GONE = (214, 223, 232, 255)    # removed voxel
SUN = (232, 162, 58, 255)      # sun and rays
POINT = (34, 54, 78, 255)      # protected point
MASS = (96, 116, 140, 255)     # context building


def new_canvas():
    image = Image.new("RGBA", (S * SS, S * SS), (0, 0, 0, 0))
    return image, ImageDraw.Draw(image)


def box(draw, x, y, w, h, fill):
    draw.rectangle(
        [x * SS, y * SS, (x + w) * SS - 1, (y + h) * SS - 1], fill=fill
    )


def disc(draw, cx, cy, r, fill):
    draw.ellipse(
        [(cx - r) * SS, (cy - r) * SS, (cx + r) * SS - 1, (cy + r) * SS - 1],
        fill=fill,
    )


def ray(draw, x0, y0, x1, y1, fill, width=1):
    draw.line(
        [x0 * SS, y0 * SS, x1 * SS, y1 * SS], fill=fill, width=width * SS
    )


def save(image, name):
    if not os.path.isdir(ICON_DIR):
        os.makedirs(ICON_DIR)

    image = image.resize((S, S), Image.LANCZOS)
    path = os.path.join(ICON_DIR, name + ".png")
    image.save(path)
    print("wrote tools/icons/{0}.png".format(name))


def voxelizer():
    """A design volume cut into columns of stacked voxels."""
    image, draw = new_canvas()

    xs = [1, 7, 13, 19]
    ys = [1, 7, 13, 19]
    heights = [3, 4, 4, 2]

    for index, x in enumerate(xs):
        count = heights[index]
        for layer in range(count):
            top = layer == count - 1
            box(draw, x, ys[3 - layer], 5, 5, CLIP if top else KEPT)

    save(image, "voxelizer")


def solver():
    """A sun ray reaching a protected point past a context mass."""
    image, draw = new_canvas()

    # context mass on the right, drawn first so the ray reads on top of it
    box(draw, 15, 7, 7, 14, MASS)

    disc(draw, 5, 5, 4, SUN)
    ray(draw, 5, 5, 11, 17, SUN)

    # the protected point the ray is evaluated at
    disc(draw, 11, 17, 3, POINT)

    save(image, "solver")


def optimizer():
    """Voxel columns with the top cells removed to open a sun path."""
    image, draw = new_canvas()

    xs = [1, 7, 13, 19]
    ys = [1, 7, 13, 19]          # four layers, bottom is ys[3]
    kept_heights = [4, 2, 1, 3]  # the dip is where the sun now gets through

    for index, x in enumerate(xs):
        kept = kept_heights[index]

        for layer in range(4):
            fill = KEPT if layer < kept else GONE
            box(draw, x, ys[3 - layer], 5, 5, fill)

    # the sun path the removal opened up, drawn over the removed cells
    disc(draw, 4, 3, 3, SUN)
    ray(draw, 4, 3, 16, 13, SUN)

    save(image, "optimizer")


def main():
    voxelizer()
    solver()
    optimizer()


if __name__ == "__main__":
    main()
