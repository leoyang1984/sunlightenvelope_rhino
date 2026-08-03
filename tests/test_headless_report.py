"""
The report has to survive being emailed: one file, no network, nothing to
install. These tests pin that property, plus the payload/geometry agreement
that the viewer depends on.
"""

import json
import pathlib
import re
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).parents[1] / "src" / "headless"))

from cadsolar import dxfio, pipeline, report  # noqa: E402

SCENE = (pathlib.Path(__file__).parents[1] / "src" / "headless" /
         "scene" / "reference.dxf")


class ReportTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        if not SCENE.exists():
            raise unittest.SkipTest("先运行 make_reference_scene.py")

        cls.scene = dxfio.read_scene(SCENE)
        cls.settings = pipeline.Settings()
        cls.result = pipeline.run(cls.scene, cls.settings)
        cls.html = report.render(cls.scene, cls.settings, cls.result)

    def payload(self):
        match = re.search(r"const DATA = (\{.*?\});</script>", self.html, re.S)
        self.assertIsNotNone(match, "找不到嵌入的数据")
        return json.loads(match.group(1).replace("<\\/", "</"))

    def test_no_external_resources(self):
        """A CDN reference would break the file offline or behind a firewall."""
        for pattern in (r'src=["\']https?://', r'href=["\']https?://',
                        r"fetch\(", r"XMLHttpRequest", r"import\s+.*from\s+['\"]http"):
            self.assertEqual(
                re.findall(pattern, self.html), [], "不应引用外部资源: " + pattern
            )

    def test_is_one_self_contained_document(self):
        self.assertTrue(self.html.startswith("<!doctype html>"))
        self.assertIn("<canvas id=\"view\">", self.html)
        self.assertNotIn("</script></script>", self.html)

    def test_payload_matches_the_result(self):
        data = self.payload()
        model, summary = data["model"], data["summary"]
        self.assertEqual(len(model["kept"]), len(self.result["kept"]))
        self.assertEqual(len(model["removed"]), len(self.result["removed"]))
        self.assertEqual(len(model["context"]), len(self.scene.context))
        self.assertEqual(len(model["points"]), len(self.scene.protected_points))
        self.assertEqual(len(summary["points"]), len(self.scene.protected_points))

    def test_every_prism_is_a_closed_ring_with_height(self):
        model = self.payload()["model"]

        for group in ("kept", "removed", "context"):
            for prism in model[group]:
                self.assertGreaterEqual(len(prism["r"]), 3, group)
                self.assertGreater(prism["z1"], prism["z0"], group)

    def test_focus_box_covers_the_massing_not_the_whole_scene(self):
        """The view frames the massing; context may run off-frame."""
        model = self.payload()["model"]
        focus, bbox = model["focus"], model["bbox"]

        for i in range(3):
            self.assertGreaterEqual(focus[i], bbox[i] - 1e-6)
            self.assertLessEqual(focus[i + 3], bbox[i + 3] + 1e-6)

        self.assertGreater(focus[3] - focus[0], 0.0)

    def test_sun_hours_reach_the_summary(self):
        summary = self.payload()["summary"]
        final = [p["final_hours"] for p in summary["points"]]
        expected = [round(v, 4) for v in self.result["outcome"]["final_hours"]]
        self.assertEqual(final, expected)

    def test_disclaimer_is_present(self):
        self.assertIn("不能作为日照报审结论", self.html)
        self.assertIn("贪心启发式", self.html)

    def test_title_is_escaped_into_place(self):
        html = report.render(
            self.scene, self.settings, self.result, title="某项目 · 校核"
        )
        self.assertIn("<title>某项目 · 校核</title>", html)


if __name__ == "__main__":
    unittest.main(verbosity=2)
