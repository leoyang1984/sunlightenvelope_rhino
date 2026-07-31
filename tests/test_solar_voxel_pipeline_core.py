"""Pure-Python tests for the Rhino 8 solar voxel pipeline."""

import ast
import math
import unittest
from datetime import datetime, timedelta
from pathlib import Path


ROOT = Path(__file__).parents[1]
VOXELIZER_PATH = (
    ROOT / "src" / "rhino8" / "SolarDesignVoxelizer_Rhino8_SDK.py"
)
OPTIMIZER_PATH = (
    ROOT / "src" / "rhino8" / "SolarVoxelOptimizer_Rhino8_SDK.py"
)
SOLVER_PATH = (
    ROOT / "src" / "rhino8" / "SolarConstraintSolver_Rhino8_SDK.py"
)


def extract_functions(path, names, namespace=None):
    """Compile selected top-level functions without importing RhinoCommon."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    body = [
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name in names
    ]
    values = {"EPSILON": 1.0e-9, "math": math}

    if namespace:
        values.update(namespace)

    exec(
        compile(
            ast.Module(body=body, type_ignores=[]),
            str(path),
            "exec",
        ),
        values,
    )
    return values


OPTIMIZER_FUNCTIONS = {
    "calculate_qualified_accumulated_hours",
    "evaluate_kept_state",
    "calculate_baseline_hours",
    "column_top_closure",
    "minimum_qualifying_windows",
    "build_candidate_actions",
    "total_solvable_deficit",
    "choose_best_action",
    "optimize_voxels",
}

OPTIMIZER = extract_functions(
    OPTIMIZER_PATH,
    OPTIMIZER_FUNCTIONS,
    {"check_escape_key": lambda: False},
)


def minute_samples(count, minutes=1):
    """Create consecutive synthetic analysis samples."""
    start = datetime(2026, 12, 22, 9, 0)
    samples = []

    for index in range(count):
        interval_start = start + timedelta(minutes=index * minutes)
        interval_end = interval_start + timedelta(minutes=minutes)
        samples.append(
            {
                "start": interval_start,
                "end": interval_end,
                "duration_hours": minutes / 60.0,
            }
        )

    return samples


class SolarVoxelPipelineCoreTests(unittest.TestCase):
    def test_voxelizer_axis_cell_count(self):
        functions = extract_functions(
            VOXELIZER_PATH,
            {"axis_cell_count"},
        )
        self.assertEqual(6, functions["axis_cell_count"](12000, 2000))
        self.assertEqual(7, functions["axis_cell_count"](12001, 2000))

    def test_voxelizer_sdk_signature(self):
        tree = ast.parse(VOXELIZER_PATH.read_text(encoding="utf-8"))
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
        names = [
            argument.arg
            for argument in run_script.args.args
            if argument.arg != "self"
        ]
        self.assertEqual(
            ["DesignVolume", "VoxelSizeXY", "VoxelSizeZ", "Run"],
            names,
        )

    def test_optimizer_sdk_signature(self):
        tree = ast.parse(OPTIMIZER_PATH.read_text(encoding="utf-8"))
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
        names = [
            argument.arg
            for argument in run_script.args.args
            if argument.arg != "self"
        ]
        self.assertEqual(20, len(names))
        self.assertEqual(
            [
                "ProtectedPoints",
                "Voxels",
                "VoxelIDs",
                "ColumnIDs",
                "LayerIDs",
                "ContextBuildings",
            ],
            names[:6],
        )

    def test_top_down_closure_removes_intersection_and_everything_above(self):
        records = [
            {"index": 0, "column_id": 0, "layer_id": 0},
            {"index": 1, "column_id": 0, "layer_id": 1},
            {"index": 2, "column_id": 0, "layer_id": 2},
            {"index": 3, "column_id": 1, "layer_id": 0},
            {"index": 4, "column_id": 1, "layer_id": 1},
        ]
        columns = {0: [0, 1, 2], 1: [3, 4]}
        closure = OPTIMIZER["column_top_closure"](
            [1, 4],
            [True] * 5,
            records,
            columns,
        )
        self.assertEqual({1, 2, 4}, closure)

    def test_minimum_window_uses_consecutive_context_clear_samples(self):
        samples = minute_samples(5)
        windows = OPTIMIZER["minimum_qualifying_windows"](
            [True, True, True, False, True],
            samples,
            3,
        )
        self.assertIn((0, 1, 2), windows)
        self.assertNotIn((2, 3, 4), windows)

    def test_optimizer_recovers_a_three_minute_qualified_run(self):
        samples = minute_samples(6)
        records = [
            {
                "index": 0,
                "id": 10,
                "column_id": 0,
                "layer_id": 0,
                "volume": 8.0,
            },
            {
                "index": 1,
                "id": 11,
                "column_id": 0,
                "layer_id": 1,
                "volume": 8.0,
            },
        ]
        columns = {0: [0, 1]}
        baseline = [[True] * 6]
        paths = [[[1], [1], [1], [], [], []]]
        result = OPTIMIZER["optimize_voxels"](
            records,
            columns,
            baseline,
            paths,
            samples,
            3,
            0.1,
            10,
        )

        self.assertEqual([True, False], result["keep_mask"])
        self.assertAlmostEqual(0.05, result["initial_hours"][0])
        self.assertAlmostEqual(0.1, result["final_hours"][0])
        self.assertEqual(
            "All baseline-solvable points meet the requirement.",
            result["stop_reason"],
        )

    def test_full_ray_path_requires_removing_lower_and_upper_voxels(self):
        samples = minute_samples(3)
        records = [
            {
                "index": 0,
                "id": 20,
                "column_id": 0,
                "layer_id": 0,
                "volume": 8.0,
            },
            {
                "index": 1,
                "id": 21,
                "column_id": 0,
                "layer_id": 1,
                "volume": 8.0,
            },
        ]
        result = OPTIMIZER["optimize_voxels"](
            records,
            {0: [0, 1]},
            [[True] * 3],
            [[[0, 1], [0, 1], [0, 1]]],
            samples,
            3,
            0.05,
            5,
        )
        self.assertEqual([False, False], result["keep_mask"])
        self.assertAlmostEqual(0.05, result["final_hours"][0])

    def test_baseline_unsolvable_point_does_not_trigger_design_removal(self):
        samples = minute_samples(3)
        records = [
            {
                "index": 0,
                "id": 30,
                "column_id": 0,
                "layer_id": 0,
                "volume": 8.0,
            }
        ]
        result = OPTIMIZER["optimize_voxels"](
            records,
            {0: [0]},
            [[False, False, False]],
            [[[0], [0], [0]]],
            samples,
            3,
            0.05,
            5,
        )
        self.assertEqual([True], result["keep_mask"])
        self.assertEqual([False], result["solvable_mask"])

    def test_optimizer_and_reference_solver_share_solar_math(self):
        function_names = {
            "clamp",
            "fractional_year_radians",
            "equation_of_time_minutes",
            "solar_declination_radians",
            "calculate_solar_position",
        }
        optimizer_solar = extract_functions(
            OPTIMIZER_PATH,
            function_names,
        )
        solver_solar = extract_functions(
            SOLVER_PATH,
            function_names,
        )
        sample_times = [
            datetime(2026, 12, 22, 9, 0),
            datetime(2026, 12, 22, 12, 0),
            datetime(2026, 12, 22, 15, 0),
        ]

        for sample_time in sample_times:
            optimizer_value = optimizer_solar[
                "calculate_solar_position"
            ](sample_time, 31.233333, 121.466667, 8)
            solver_value = solver_solar[
                "calculate_solar_position"
            ](sample_time, 31.233333, 121.466667, 8)
            self.assertAlmostEqual(
                optimizer_value[0],
                solver_value[0],
            )
            self.assertAlmostEqual(
                optimizer_value[1],
                solver_value[1],
            )

    def test_optimizer_and_reference_solver_share_time_integration(self):
        function_names = {
            "decimal_hour_to_datetime",
            "generate_time_intervals",
            "calculate_qualified_accumulated_hours",
        }
        optimizer_time = extract_functions(
            OPTIMIZER_PATH,
            function_names,
            {"datetime": datetime, "timedelta": timedelta},
        )
        solver_time = extract_functions(
            SOLVER_PATH,
            function_names,
            {"datetime": datetime, "timedelta": timedelta},
        )
        optimizer_intervals = optimizer_time["generate_time_intervals"](
            2026,
            12,
            22,
            9,
            9.1,
            4,
        )
        solver_intervals = solver_time["generate_time_intervals"](
            2026,
            12,
            22,
            9,
            9.1,
            4,
        )
        self.assertEqual(optimizer_intervals, solver_intervals)

        flags = [True, True]
        optimizer_hours = optimizer_time[
            "calculate_qualified_accumulated_hours"
        ](flags, optimizer_intervals, 3)
        solver_hours = solver_time[
            "calculate_qualified_accumulated_hours"
        ](flags, solver_intervals, 3)
        self.assertEqual(optimizer_hours, solver_hours)


if __name__ == "__main__":
    unittest.main()
