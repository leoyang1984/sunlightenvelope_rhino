"""
The failure mode that actually matters for an agent-driven pipeline.

A crash is fine. A drawing that parses into a plausible but wrong scene is
not: the agent will confidently report sun hours for a building that is not
the one the architect drew. Every case here must raise, not warn.
"""

import math
import pathlib
import sys
import tempfile
import unittest

import ezdxf

sys.path.insert(0, str(pathlib.Path(__file__).parents[1] / "src" / "headless"))

from cadsolar import dxfio  # noqa: E402
from cadsolar.naming import NameError_, parse_block_name  # noqa: E402

MM = 1000.0


def rect(x0, y0, x1, y1):
    return [(x0 * MM, y0 * MM), (x1 * MM, y0 * MM),
            (x1 * MM, y1 * MM), (x0 * MM, y1 * MM)]


def write(tmpdir, build):
    doc = ezdxf.new("R2010", setup=True)
    doc.header["$INSUNITS"] = 4
    build(doc, doc.modelspace())
    path = pathlib.Path(tmpdir) / "case.dxf"
    doc.saveas(str(path))
    return path


class NameParsingTests(unittest.TestCase):

    def test_valid_forms(self):
        cases = [
            ("方案a-100m", "design", 100.0),
            ("建筑a-10m", "context", 10.0),
            ("周边建筑a-50m", "context", 50.0),
            ("保护点1-0.5米", "point", 0.5),
            ("方案b-36000mm", "design", 36.0),
            ("scheme-48m", "design", 48.0),
            ("context_tower-25m", "context", 25.0),
        ]

        for raw, role, meters in cases:
            parsed = parse_block_name(raw)
            self.assertEqual(parsed.role, role, raw)
            self.assertAlmostEqual(parsed.meters, meters, places=6, msg=raw)

    def test_full_width_digits_and_dash(self):
        parsed = parse_block_name("方案ａ－３６ｍ")
        self.assertEqual(parsed.role, "design")
        self.assertAlmostEqual(parsed.meters, 36.0)

    def test_missing_height_is_rejected(self):
        with self.assertRaises(NameError_) as caught:
            parse_block_name("方案a")
        self.assertIn("缺少高度段", str(caught.exception))

    def test_unknown_role_is_rejected(self):
        with self.assertRaises(NameError_) as caught:
            parse_block_name("楼栋a-30m")
        self.assertIn("没有可识别的角色前缀", str(caught.exception))

    def test_zero_height_is_rejected(self):
        with self.assertRaises(NameError_):
            parse_block_name("方案a-0m")

    def test_longest_prefix_wins(self):
        self.assertEqual(parse_block_name("周边建筑x-9m").role, "context")


class DrawingTests(unittest.TestCase):

    def _design_and_point(self, doc, msp):
        doc.blocks.new("方案a-36m").add_lwpolyline(
            rect(0, 0, 30, 20), close=True)
        msp.add_blockref("方案a-36m", (0, 0))
        doc.blocks.new("保护点a-1.5m").add_point((0, 0, 0))
        msp.add_blockref("保护点a-1.5m", (10 * MM, 50 * MM))

    def test_valid_minimum_scene_parses(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, self._design_and_point)
            scene = dxfio.read_scene(path)
            self.assertEqual(len(scene.design), 1)
            self.assertEqual(len(scene.protected_points), 1)
            self.assertAlmostEqual(scene.protected_points[0][2], 1.5)

    def test_typo_in_block_name_raises_not_warns(self):
        def build(doc, msp):
            self._design_and_point(doc, msp)
            doc.blocks.new("周边建筑a50m").add_lwpolyline(  # missing dash
                rect(40, 0, 60, 20), close=True)
            msp.add_blockref("周边建筑a50m", (0, 0))

        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, build)

            with self.assertRaises(dxfio.SceneError) as caught:
                dxfio.read_scene(path)

            self.assertIn("周边建筑a50m", str(caught.exception))

    def test_unclosed_footprint_raises(self):
        def build(doc, msp):
            self._design_and_point(doc, msp)
            block = doc.blocks.new("周边建筑b-20m")
            block.add_lwpolyline(rect(40, 0, 60, 20), close=False)
            msp.add_blockref("周边建筑b-20m", (0, 0))

        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, build)

            with self.assertRaises(dxfio.SceneError) as caught:
                dxfio.read_scene(path)

            self.assertIn("未闭合", str(caught.exception))

    def test_missing_design_raises(self):
        def build(doc, msp):
            doc.blocks.new("保护点a-1.5m").add_point((0, 0, 0))
            msp.add_blockref("保护点a-1.5m", (0, 0))

        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, build)

            with self.assertRaises(dxfio.SceneError) as caught:
                dxfio.read_scene(path)

            self.assertIn("没有方案体量", str(caught.exception))

    def test_missing_protected_points_raises(self):
        def build(doc, msp):
            doc.blocks.new("方案a-36m").add_lwpolyline(
                rect(0, 0, 30, 20), close=True)
            msp.add_blockref("方案a-36m", (0, 0))

        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, build)

            with self.assertRaises(dxfio.SceneError):
                dxfio.read_scene(path)

    def test_point_block_without_a_point_entity_raises(self):
        def build(doc, msp):
            doc.blocks.new("方案a-36m").add_lwpolyline(
                rect(0, 0, 30, 20), close=True)
            msp.add_blockref("方案a-36m", (0, 0))
            doc.blocks.new("保护点a-1.5m").add_line((0, 0), (1, 1))
            msp.add_blockref("保护点a-1.5m", (0, 0))

        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, build)

            with self.assertRaises(dxfio.SceneError) as caught:
                dxfio.read_scene(path)

            self.assertIn("没有 POINT 实体", str(caught.exception))

    def test_unitless_drawing_raises_rather_than_guessing(self):
        def build(doc, msp):
            doc.header["$INSUNITS"] = 0
            self._design_and_point(doc, msp)

        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, build)

            with self.assertRaises(dxfio.SceneError) as caught:
                dxfio.read_scene(path)

            self.assertIn("没有声明单位", str(caught.exception))

    def test_metre_drawing_scales_correctly(self):
        def build(doc, msp):
            doc.header["$INSUNITS"] = 6
            doc.blocks.new("方案a-36m").add_lwpolyline(
                [(0, 0), (30, 0), (30, 20), (0, 20)], close=True)
            msp.add_blockref("方案a-36m", (0, 0))
            doc.blocks.new("保护点a-1.5m").add_point((0, 0, 0))
            msp.add_blockref("保护点a-1.5m", (10, 50))

        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, build)
            scene = dxfio.read_scene(path)
            self.assertAlmostEqual(scene.design[0].volume, 30 * 20 * 36, places=3)

    def test_insert_offset_is_applied(self):
        """A block inserted away from the origin must move with the insert."""
        def build(doc, msp):
            doc.blocks.new("方案a-36m").add_lwpolyline(
                rect(0, 0, 30, 20), close=True)
            msp.add_blockref("方案a-36m", (100 * MM, 200 * MM))
            doc.blocks.new("保护点a-1.5m").add_point((0, 0, 0))
            msp.add_blockref("保护点a-1.5m", (10 * MM, 50 * MM))

        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, build)
            scene = dxfio.read_scene(path)
            x_min = scene.design[0].bbox[0]
            self.assertAlmostEqual(x_min, 100.0, places=6)


if __name__ == "__main__":
    unittest.main(verbosity=2)


class NorthDirectionTests(unittest.TestCase):
    """The sign convention that silently ruins a run if it is wrong."""

    def _bearing_of(self, bearing):
        from cadsolar.pipeline import bearing_to_north_angle, north_east_vectors
        north, _ = north_east_vectors(bearing_to_north_angle(bearing))
        return (math.degrees(math.atan2(north[0], north[1])) + 360.0) % 360.0

    def test_due_north(self):
        self.assertAlmostEqual(self._bearing_of(0), 0.0, places=9)

    def test_north_by_east_swings_east(self):
        """北偏东 15 度 -> 方位角 15，不是 345。"""
        self.assertAlmostEqual(self._bearing_of(15), 15.0, places=6)

    def test_north_by_west_swings_west(self):
        self.assertAlmostEqual(self._bearing_of(-15), 345.0, places=6)

    def test_quarter_turn(self):
        self.assertAlmostEqual(self._bearing_of(90), 90.0, places=6)

    def test_east_vector_stays_perpendicular(self):
        from cadsolar.pipeline import bearing_to_north_angle, north_east_vectors

        for bearing in (0, 15, -40, 90, 180):
            north, east = north_east_vectors(bearing_to_north_angle(bearing))
            dot = sum(a * b for a, b in zip(north, east))
            self.assertAlmostEqual(dot, 0.0, places=9, msg=str(bearing))
            self.assertAlmostEqual(
                math.hypot(north[0], north[1]), 1.0, places=9)


class CityTableTests(unittest.TestCase):

    def test_chinese_and_pinyin_agree(self):
        from cadsolar.cities import lookup_city
        for chinese, pinyin in [("上海", "shanghai"), ("宁波", "ningbo"),
                                ("乌鲁木齐", "urumqi")]:
            self.assertEqual(lookup_city(chinese), lookup_city(pinyin), chinese)

    def test_shanghai_matches_the_official_profile(self):
        from cadsolar.cities import lookup_city
        latitude, longitude, timezone = lookup_city("上海")
        self.assertAlmostEqual(latitude, 31.233333, places=6)
        self.assertAlmostEqual(longitude, 121.466667, places=6)
        self.assertEqual(timezone, 8.0)

    def test_unknown_city_returns_none(self):
        from cadsolar.cities import lookup_city
        self.assertIsNone(lookup_city("瓦坎达"))
        self.assertIsNone(lookup_city(""))

    def test_coordinates_are_plausible(self):
        from cadsolar.cities import CITIES
        for name, (latitude, longitude, timezone) in CITIES.items():
            self.assertTrue(3.0 < latitude < 54.0, name)
            self.assertTrue(73.0 < longitude < 136.0, name)
            self.assertEqual(timezone, 8.0, name)

    def test_day_presets(self):
        from cadsolar.cities import lookup_day
        month, day, start, end, _ = lookup_day("大寒")
        self.assertEqual((month, day), (1, 20))
        self.assertLess(start, end)
        self.assertEqual(lookup_day("大寒"), lookup_day("dahan"))
        self.assertIsNone(lookup_day("小雪"))
