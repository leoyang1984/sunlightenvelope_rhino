"""
Validate the replacement geometry against closed-form answers.

The pipeline agreeing with itself proves nothing. These tests check the four
primitives that replaced the Rhino kernel against results computed by hand.
"""

import math
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).parents[1] / "src" / "headless"))

from cadsolar import kernel, pipeline  # noqa: E402
from cadsolar.geom import (  # noqa: E402
    Prism,
    PrismSet,
    clip_polygon_to_rect,
    point_in_polygon,
    polygon_area,
)

OPTIMIZER = kernel.load_optimizer()


def box(x0, y0, x1, y1, z0, z1):
    return Prism([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], z0, z1)


class RayTests(unittest.TestCase):
    """Prism.ray_distance versus hand-computed intersections."""

    def test_axis_ray_hits_near_face(self):
        solid = box(10, -5, 20, 5, 0, 10)
        distance = solid.ray_distance((0, 0, 5), (1, 0, 0))
        self.assertAlmostEqual(distance, 10.0, places=9)

    def test_ray_from_inside_returns_exit_distance(self):
        """MeshRay semantics: an origin inside the solid returns the far face."""
        solid = box(0, 0, 10, 10, 0, 10)
        distance = solid.ray_distance((5, 5, 5), (1, 0, 0))
        self.assertAlmostEqual(distance, 5.0, places=9)

    def test_ray_pointing_away_misses(self):
        solid = box(10, -5, 20, 5, 0, 10)
        self.assertEqual(solid.ray_distance((0, 0, 5), (-1, 0, 0)), -1.0)

    def test_ray_passing_over_the_top_misses(self):
        solid = box(10, -5, 20, 5, 0, 10)
        self.assertEqual(solid.ray_distance((0, 0, 20), (1, 0, 0)), -1.0)

    def test_diagonal_ray_matches_closed_form(self):
        solid = box(10, 10, 20, 20, 0, 100)
        direction = (1 / math.sqrt(2), 1 / math.sqrt(2), 0.0)
        distance = solid.ray_distance((0, 0, 5), direction)
        self.assertAlmostEqual(distance, 10.0 * math.sqrt(2), places=9)

    def test_sloped_ray_enters_through_the_top_face(self):
        """Ray clears the near wall and lands on the roof plane."""
        solid = box(10, -5, 20, 5, 0, 10)
        direction = (math.cos(math.radians(45)), 0.0, math.sin(math.radians(45)))
        distance = solid.ray_distance((0, 0, 0), direction)
        # Top face at z=10 is reached at horizontal x=10, i.e. exactly the
        # near wall corner: distance = 10*sqrt(2).
        self.assertAlmostEqual(distance, 10.0 * math.sqrt(2), places=6)

    def test_prism_set_returns_nearest_member(self):
        near = box(10, -5, 20, 5, 0, 10)
        far = box(40, -5, 50, 5, 0, 10)
        group = PrismSet([far, near])
        self.assertAlmostEqual(
            group.ray_distance((0, 0, 5), (1, 0, 0)), 10.0, places=9
        )


class ShadowTests(unittest.TestCase):
    """A shadow length the pipeline computes must match trigonometry."""

    def test_shadow_boundary_matches_tangent_rule(self):
        """
        A wall of height H due south of a point shades it exactly while
        D < H / tan(altitude). Test both sides of that boundary.
        """
        height = 30.0
        altitude = math.radians(35.0)
        critical = height / math.tan(altitude)

        wall = box(-100, -1, 100, 0, 0, height)
        # Direction from the point toward a due-south sun, matching the
        # component convention (azimuth 180 -> north * cos(180) = -north).
        sun = (0.0, -math.cos(altitude), math.sin(altitude))

        inside = wall.ray_distance((0, critical - 1.0, 0.0), sun)
        outside = wall.ray_distance((0, critical + 1.0, 0.0), sun)

        self.assertGreaterEqual(inside, 0.0, "应当被遮挡")
        self.assertEqual(outside, -1.0, "应当见到太阳")


class ClipTests(unittest.TestCase):
    """clip_polygon_to_rect replaces Brep Boolean intersection."""

    def test_full_containment_is_identity_in_area(self):
        polygon = [(1, 1), (4, 1), (4, 4), (1, 4)]
        clipped = clip_polygon_to_rect(polygon, 0, 0, 10, 10)
        self.assertAlmostEqual(polygon_area(clipped), 9.0, places=9)

    def test_half_overlap(self):
        polygon = [(0, 0), (10, 0), (10, 10), (0, 10)]
        clipped = clip_polygon_to_rect(polygon, 5, 0, 20, 10)
        self.assertAlmostEqual(polygon_area(clipped), 50.0, places=9)

    def test_no_overlap_yields_nothing(self):
        polygon = [(0, 0), (1, 0), (1, 1), (0, 1)]
        clipped = clip_polygon_to_rect(polygon, 5, 5, 6, 6)
        self.assertLess(polygon_area(clipped), 1e-12)

    def test_triangle_corner_clip_matches_hand_area(self):
        triangle = [(0, 0), (10, 0), (0, 10)]

        # The hypotenuse is x + y = 10, so the 5x5 cell sits entirely inside
        # (its far corner lands exactly on the line).
        contained = clip_polygon_to_rect(triangle, 0, 0, 5, 5)
        self.assertAlmostEqual(polygon_area(contained), 25.0, places=9)

        # An 8x8 cell is cut: 64 minus the corner triangle with legs of 6.
        cut = clip_polygon_to_rect(triangle, 0, 0, 8, 8)
        self.assertAlmostEqual(polygon_area(cut), 64.0 - 18.0, places=9)

    def test_grid_of_clips_conserves_total_area(self):
        """The property that matters: voxelizing must not lose volume."""
        polygon = [(12, 0), (56, 0), (44, 33), (12, 33)]
        expected = polygon_area(polygon)
        cell = 6.0
        total = 0.0

        for i in range(-1, 12):
            for j in range(-1, 8):
                piece = clip_polygon_to_rect(
                    polygon, i * cell, j * cell, (i + 1) * cell, (j + 1) * cell
                )
                total += polygon_area(piece)

        self.assertAlmostEqual(total, expected, places=6)


class PointInPolygonTests(unittest.TestCase):

    def test_inside_and_outside(self):
        polygon = [(0, 0), (10, 0), (10, 10), (0, 10)]
        self.assertTrue(point_in_polygon(polygon, 5, 5))
        self.assertFalse(point_in_polygon(polygon, 15, 5))

    def test_concave_notch(self):
        polygon = [(0, 0), (10, 0), (10, 10), (5, 10), (5, 5), (0, 5)]
        self.assertTrue(point_in_polygon(polygon, 2, 2))
        self.assertFalse(point_in_polygon(polygon, 2, 7))


class VolumeTests(unittest.TestCase):

    def test_voxelization_conserves_volume_exactly(self):
        design = Prism([(12, 0), (56, 0), (44, 33), (12, 33)], 0.0, 48.0)
        grid = pipeline.voxelize([design], 6.0, 6.0)
        self.assertAlmostEqual(grid.total_volume, design.volume, places=6)

    def test_voxelization_is_grid_offset_invariant(self):
        """Shifting the design must not change its voxelized volume."""
        base = Prism([(12, 0), (56, 0), (44, 33), (12, 33)], 0.0, 48.0)
        shifted = Prism(
            [(x + 2.37, y + 1.11) for x, y in base.polygon], 0.0, 48.0
        )
        a = pipeline.voxelize([base], 6.0, 6.0)
        b = pipeline.voxelize([shifted], 6.0, 6.0)
        self.assertAlmostEqual(a.total_volume, b.total_volume, places=6)

    def test_column_and_layer_contract(self):
        design = Prism([(12, 0), (56, 0), (44, 33), (12, 33)], 0.0, 48.0)
        grid = pipeline.voxelize([design], 6.0, 6.0)

        for column_id, members in grid.column_members.items():
            layers = [grid.records[i]["layer_id"] for i in members]
            self.assertEqual(layers, sorted(layers), "柱内层号必须递增")
            self.assertEqual(len(layers), len(set(layers)), "层号不能重复")

        ids = [record["id"] for record in grid.records]
        self.assertEqual(len(ids), len(set(ids)), "VoxelID 必须唯一")


class SolarTests(unittest.TestCase):
    """The reused solar code must still produce textbook values."""

    def test_shanghai_winter_solstice_noon_altitude(self):
        altitude, azimuth = OPTIMIZER["calculate_solar_position"](
            __import__("datetime").datetime(2024, 12, 21, 12, 0, 0),
            31.233333,
            121.466667,
            8.0,
        )
        degrees = math.degrees(altitude)
        # 90 - latitude - obliquity = 90 - 31.23 - 23.44 = 35.32, and Shanghai
        # is east of the 120E meridian so local noon is a few minutes early.
        self.assertAlmostEqual(degrees, 35.3, delta=0.6)
        self.assertAlmostEqual(math.degrees(azimuth), 180.0, delta=3.0)

    def test_summer_solstice_is_far_higher(self):
        altitude, _ = OPTIMIZER["calculate_solar_position"](
            __import__("datetime").datetime(2024, 6, 21, 12, 0, 0),
            31.233333,
            121.466667,
            8.0,
        )
        self.assertAlmostEqual(math.degrees(altitude), 82.2, delta=1.0)


class DeterminismTests(unittest.TestCase):

    def test_two_runs_agree_exactly(self):
        from cadsolar import dxfio

        path = (pathlib.Path(__file__).parents[1] / "src" / "headless" /
                "scene" / "reference.dxf")

        if not path.exists():
            self.skipTest("先运行 make_scene.py")

        settings = pipeline.Settings()
        first = pipeline.run(dxfio.read_scene(path), settings)
        second = pipeline.run(dxfio.read_scene(path), settings)

        self.assertEqual(
            first["outcome"]["keep_mask"], second["outcome"]["keep_mask"]
        )
        self.assertEqual(
            first["outcome"]["final_hours"], second["outcome"]["final_hours"]
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)


class OverlappingDesignVolumeTests(unittest.TestCase):
    """
    A podium with a tower on it is drawn as two overlapping blocks. Picking
    one volume per column let the low podium mask the tower, so the pipeline
    analysed an 18 m building where 54 m had been drawn - and reported
    "nothing to carve" with full confidence.
    """

    def setUp(self):
        self.podium = Prism([(8, 4), (62, 4), (62, 34), (8, 34)], 0.0, 18.0)
        self.tower = Prism([(20, 10), (48, 10), (48, 30), (20, 30)], 0.0, 54.0)

    def test_tower_survives_the_podium(self):
        grid = pipeline.voxelize([self.podium, self.tower], 6.0, 6.0)
        top = max(record["geometry"].z_high for record in grid.records)
        self.assertAlmostEqual(top, 54.0, places=6, msg="塔楼高度不能被裙房吃掉")

    def test_nested_volumes_give_the_exact_solid_volume(self):
        """Podium contains tower, so the union is exact, not an estimate."""
        grid = pipeline.voxelize([self.podium, self.tower], 6.0, 6.0)
        overlap = 28.0 * 20.0 * 18.0
        expected = self.podium.volume + self.tower.volume - overlap
        self.assertAlmostEqual(grid.total_volume, expected, places=6)
        self.assertEqual(grid.warnings, [], "完全包含的情况不该报近似")

    def test_order_of_the_two_blocks_does_not_matter(self):
        a = pipeline.voxelize([self.podium, self.tower], 6.0, 6.0)
        b = pipeline.voxelize([self.tower, self.podium], 6.0, 6.0)
        self.assertAlmostEqual(a.total_volume, b.total_volume, places=6)
        self.assertEqual(len(a.records), len(b.records))

    def test_axis_aligned_overlap_is_still_exact(self):
        """
        Two rectangles clip to the same polygon inside a shared cell, so the
        largest is the union and there is nothing to approximate.
        """
        left = Prism([(0, 0), (20, 0), (20, 20), (0, 20)], 0.0, 20.0)
        right = Prism([(10, 0), (30, 0), (30, 20), (10, 20)], 0.0, 40.0)
        grid = pipeline.voxelize([left, right], 5.0, 5.0)
        self.assertEqual(grid.warnings, [])
        expected = 20 * 20 * 20 + 20 * 20 * 40 - 10 * 20 * 20
        self.assertAlmostEqual(grid.total_volume, expected, places=6)

    def test_partial_overlap_is_reported_as_an_approximation(self):
        """
        Footprints split along a diagonal clip to complementary shapes, so
        neither contains the other and the union cannot be recovered by
        taking one of them. That has to be said out loud, not absorbed.
        """
        lower = Prism([(0, 0), (20, 0), (20, 20)], 0.0, 20.0)
        upper = Prism([(0, 0), (0, 20), (20, 20)], 0.0, 40.0)
        grid = pipeline.voxelize([lower, upper], 5.0, 5.0)
        self.assertTrue(grid.warnings, "部分重叠必须告警")
        self.assertIn("低估", grid.warnings[0])
