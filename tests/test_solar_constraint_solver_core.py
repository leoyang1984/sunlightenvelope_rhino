"""Core tests that run without Rhino or Grasshopper installed."""

import ast
import math
import unittest
from datetime import datetime, timedelta
from pathlib import Path


SCRIPT_PATH = (
    Path(__file__).parents[1]
    / "src"
    / "rhino8"
    / "SolarConstraintSolver_Rhino8_SDK.py"
)


def load_core_functions():
    """Load pure-Python solver helpers without importing RhinoCommon."""
    tree = ast.parse(SCRIPT_PATH.read_text(encoding="utf-8"))
    function_names = {
        "unwrap_gh_value",
        "is_finite_number",
        "calculate_qualified_accumulated_hours",
        "make_violation_record",
    }
    body = [
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name in function_names
    ]
    namespace = {"EPSILON": 1.0e-9, "math": math}
    module = ast.Module(body=body, type_ignores=[])
    exec(compile(module, str(SCRIPT_PATH), "exec"), namespace)
    return namespace


CORE = load_core_functions()


def minute_samples(count, gap_after=None):
    """Create one-minute analysis samples, optionally with a time gap."""
    start = datetime(2026, 12, 21, 9, 0)
    samples = []
    offset = 0

    for index in range(count):
        if gap_after is not None and index == gap_after:
            offset += 1

        interval_start = start + timedelta(minutes=index + offset)
        samples.append(
            {
                "start": interval_start,
                "end": interval_start + timedelta(minutes=1),
                "duration_hours": 1.0 / 60.0,
            }
        )

    return samples


class SolarConstraintSolverCoreTests(unittest.TestCase):
    def test_run_script_has_expected_seventeen_inputs(self):
        tree = ast.parse(SCRIPT_PATH.read_text(encoding="utf-8"))
        script_class = next(
            node
            for node in tree.body
            if isinstance(node, ast.ClassDef)
            and node.name == "Script_Instance"
        )
        run_script = next(
            node
            for node in script_class.body
            if isinstance(node, ast.FunctionDef)
            and node.name == "RunScript"
        )
        input_names = [
            argument.arg
            for argument in run_script.args.args
            if argument.arg != "self"
        ]

        self.assertEqual(17, len(input_names))
        self.assertEqual(
            "MinimumContinuousMinutes",
            input_names[13],
        )

    def test_grasshopper_value_wrapper_is_unwrapped(self):
        wrapper = type("FakeGHPoint", (), {"Value": "Point3d"})()
        self.assertEqual(
            "Point3d",
            CORE["unwrap_gh_value"](wrapper),
        )

    def test_only_complete_runs_reaching_threshold_are_counted(self):
        flags = [
            True,
            True,
            False,
            True,
            True,
            True,
            True,
            False,
            True,
        ]
        qualified, raw, runs = CORE[
            "calculate_qualified_accumulated_hours"
        ](flags, minute_samples(len(flags)), 3)

        self.assertAlmostEqual(4.0 / 60.0, qualified)
        self.assertAlmostEqual(7.0 / 60.0, raw)
        self.assertEqual(
            [round(2.0 / 60.0, 10), round(4.0 / 60.0, 10), round(1.0 / 60.0, 10)],
            runs,
        )

    def test_exact_threshold_is_included(self):
        qualified, raw, _ = CORE[
            "calculate_qualified_accumulated_hours"
        ]([True, True, True], minute_samples(3), 3)

        self.assertAlmostEqual(3.0 / 60.0, qualified)
        self.assertAlmostEqual(raw, qualified)

    def test_zero_threshold_preserves_raw_accumulation(self):
        flags = [True, False, True]
        qualified, raw, _ = CORE[
            "calculate_qualified_accumulated_hours"
        ](flags, minute_samples(3), 0)

        self.assertAlmostEqual(raw, qualified)

    def test_time_gap_breaks_a_continuous_run(self):
        qualified, raw, runs = CORE[
            "calculate_qualified_accumulated_hours"
        ]([True, True, True, True], minute_samples(4, gap_after=2), 3)

        self.assertAlmostEqual(0.0, qualified)
        self.assertAlmostEqual(4.0 / 60.0, raw)
        self.assertEqual(2, len(runs))

    def test_mismatched_flags_and_samples_are_rejected(self):
        with self.assertRaises(ValueError):
            CORE["calculate_qualified_accumulated_hours"](
                [True],
                minute_samples(2),
                3,
            )

    def test_result_record_keeps_raw_and_qualified_metrics(self):
        record = CORE["make_violation_record"](
            0,
            "Point",
            4.0,
            3.0,
            4.1,
            3.2,
            3.0,
            [4.0],
            [3.0],
            2.0,
            0.01,
        )

        self.assertEqual(3.0, record["SunHours"])
        self.assertEqual(3.2, record["RawSunHours"])
        self.assertEqual(3.0, record["MinimumContinuousMinutes"])


if __name__ == "__main__":
    unittest.main()
