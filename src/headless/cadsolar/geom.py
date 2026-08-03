"""
2.5D prism geometry.

This module is the entire replacement for the RhinoCommon geometry kernel.
Everything the pipeline needs from Rhino reduces to four operations once the
input is restricted to vertical extrusions of closed 2D polygons:

    Rhino                                   here
    -------------------------------------   --------------------------------
    Intersect.Intersection.MeshRay          Prism.ray_distance
    Mesh.IsPointInside                      Prism.contains_xy + z range
    Brep.CreateBooleanIntersection          clip_polygon_to_rect
    VolumeMassProperties.Compute            polygon_area * height

All four are analytic here. The Rhino path meshes a Brep first and then casts
against the tessellation, so this is not an approximation of the Rhino result
but a more exact one.
"""

import math

EPS = 1.0e-9
INF = float("inf")


# ---------------------------------------------------------------- polygons

def polygon_area(polygon):
    """Return the absolute shoelace area of a closed 2D polygon."""
    count = len(polygon)

    if count < 3:
        return 0.0

    total = 0.0

    for index in range(count):
        x1, y1 = polygon[index]
        x2, y2 = polygon[(index + 1) % count]
        total += x1 * y2 - x2 * y1

    return abs(total) * 0.5


def point_in_polygon(polygon, x, y):
    """Even-odd point-in-polygon test."""
    inside = False
    count = len(polygon)

    for index in range(count):
        x1, y1 = polygon[index]
        x2, y2 = polygon[(index + 1) % count]

        if (y1 > y) != (y2 > y):
            crossing_x = x1 + (y - y1) * (x2 - x1) / (y2 - y1)

            if x < crossing_x:
                inside = not inside

    return inside


def clip_polygon_to_rect(polygon, x_min, y_min, x_max, y_max):
    """
    Sutherland-Hodgman clip of a polygon against an axis-aligned rectangle.

    The clip window is convex, so the result is exact for convex subjects and
    area-correct for concave ones. This replaces Brep Boolean intersection for
    boundary voxel cells.
    """
    def clip_half_plane(points, axis, bound, keep_greater):
        """Clip against one axis-aligned line; crossings are solved exactly."""
        if not points:
            return []

        def inside(point):
            if keep_greater:
                return point[axis] >= bound - EPS
            return point[axis] <= bound + EPS

        def crossing(a, b):
            span = b[axis] - a[axis]

            if abs(span) < EPS:
                return a

            parameter = (bound - a[axis]) / span
            return (
                a[0] + (b[0] - a[0]) * parameter,
                a[1] + (b[1] - a[1]) * parameter
            )

        result = []

        for index in range(len(points)):
            current = points[index]
            previous = points[index - 1]
            current_in = inside(current)
            previous_in = inside(previous)

            if current_in:
                if not previous_in:
                    result.append(crossing(previous, current))
                result.append(current)
            elif previous_in:
                result.append(crossing(previous, current))

        return result

    points = list(polygon)
    points = clip_half_plane(points, 0, x_min, True)
    points = clip_half_plane(points, 0, x_max, False)
    points = clip_half_plane(points, 1, y_min, True)
    points = clip_half_plane(points, 1, y_max, False)
    return points


# ------------------------------------------------------------------ prisms

class Prism(object):
    """A closed solid: polygon extruded vertically from z_low to z_high."""

    __slots__ = ("polygon", "z_low", "z_high", "bbox")

    def __init__(self, polygon, z_low, z_high):
        points = [(float(x), float(y)) for x, y in polygon]

        if (
            len(points) > 2 and
            abs(points[0][0] - points[-1][0]) < EPS and
            abs(points[0][1] - points[-1][1]) < EPS
        ):
            points = points[:-1]

        self.polygon = points
        self.z_low = float(min(z_low, z_high))
        self.z_high = float(max(z_low, z_high))

        xs = [p[0] for p in points]
        ys = [p[1] for p in points]
        self.bbox = (
            min(xs), min(ys), self.z_low,
            max(xs), max(ys), self.z_high
        )

    @property
    def height(self):
        return self.z_high - self.z_low

    @property
    def volume(self):
        return polygon_area(self.polygon) * self.height

    @property
    def center(self):
        x_min, y_min, _, x_max, y_max, _ = self.bbox
        return (
            (x_min + x_max) * 0.5,
            (y_min + y_max) * 0.5,
            (self.z_low + self.z_high) * 0.5
        )

    def contains(self, x, y, z):
        if z < self.z_low - EPS or z > self.z_high + EPS:
            return False

        return point_in_polygon(self.polygon, x, y)

    def _xy_inside_intervals(self, ox, oy, dx, dy):
        """Return ray parameter intervals whose XY projection is inside."""
        if math.hypot(dx, dy) < EPS:
            if point_in_polygon(self.polygon, ox, oy):
                return [(-INF, INF)]
            return []

        crossings = []
        points = self.polygon
        count = len(points)

        for index in range(count):
            x1, y1 = points[index]
            x2, y2 = points[(index + 1) % count]
            ex, ey = x2 - x1, y2 - y1
            denominator = dx * ey - dy * ex

            if abs(denominator) < 1.0e-15:
                continue

            # Half-open edge parameter [0, 1) so a ray through a shared
            # vertex is counted exactly once.
            s = ((x1 - ox) * dy - (y1 - oy) * dx) / denominator

            if s < 0.0 or s >= 1.0:
                continue

            t = ((x1 - ox) * ey - (y1 - oy) * ex) / denominator
            crossings.append(t)

        if not crossings:
            if point_in_polygon(self.polygon, ox, oy):
                return [(-INF, INF)]
            return []

        crossings.sort()

        if len(crossings) % 2 == 1:
            # Degenerate tangency; fall back to a containment answer rather
            # than emitting a malformed interval list.
            if point_in_polygon(self.polygon, ox, oy):
                return [(-INF, INF)]
            return []

        return [
            (crossings[index], crossings[index + 1])
            for index in range(0, len(crossings), 2)
        ]

    def ray_distance(self, origin, direction):
        """
        Return the distance to the first surface hit at t > 0, or -1.

        Mirrors RhinoCommon MeshRay: an origin inside the solid returns the
        exit distance, an origin outside returns the entry distance.
        """
        ox, oy, oz = origin
        dx, dy, dz = direction

        if abs(dz) > EPS:
            t_a = (self.z_low - oz) / dz
            t_b = (self.z_high - oz) / dz
            z_low_t, z_high_t = min(t_a, t_b), max(t_a, t_b)
        else:
            if oz < self.z_low - EPS or oz > self.z_high + EPS:
                return -1.0
            z_low_t, z_high_t = -INF, INF

        best = INF

        for enter, exit_ in self._xy_inside_intervals(ox, oy, dx, dy):
            low = max(enter, z_low_t)
            high = min(exit_, z_high_t)

            if high < low - EPS:
                continue

            for candidate in (low, high):
                if EPS < candidate < best:
                    best = candidate

        if best == INF:
            return -1.0

        return best


class PrismSet(object):
    """A group of prisms behaving as one occluder for ray casting."""

    __slots__ = ("prisms",)

    def __init__(self, prisms):
        self.prisms = list(prisms)

    def __len__(self):
        return len(self.prisms)

    @property
    def volume(self):
        return sum(prism.volume for prism in self.prisms)

    def bounding_box(self):
        if not self.prisms:
            return None

        boxes = [prism.bbox for prism in self.prisms]
        return (
            min(b[0] for b in boxes), min(b[1] for b in boxes),
            min(b[2] for b in boxes), max(b[3] for b in boxes),
            max(b[4] for b in boxes), max(b[5] for b in boxes)
        )

    def ray_distance(self, origin, direction):
        best = -1.0

        for prism in self.prisms:
            distance = prism.ray_distance(origin, direction)

            if distance < 0.0:
                continue

            if best < 0.0 or distance < best:
                best = distance

        return best


def ray_distance(origin, direction, solid):
    """Uniform entry point used as the injected geometry primitive."""
    if solid is None:
        return -1.0

    return solid.ray_distance(origin, direction)
