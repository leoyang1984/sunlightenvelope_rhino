"""
Single definition of every Grasshopper User Object port.

Six bundles are generated from this file: the three pipeline components, each
in a Rhino 7 IronPython flavour and a Rhino 8 Python 3 flavour. The two
flavours of one component share the same ports, so they are declared once here
and emitted twice. Hand-writing six metadata.json files would guarantee the
pair drifts apart.

Port names and order must match the RunScript signature of the corresponding
script. tools/check_ghuser_bundle.py enforces that.
"""


# Shared port fragments -------------------------------------------------------

SOLAR_INPUTS = [
    ("North", "N", "vector", "item",
     "Project north direction. The horizontal XY component must not be zero."),
    ("Latitude", "Lat", "float", "item",
     "Site latitude in degrees, -90 to 90."),
    ("Longitude", "Lon", "float", "item",
     "Site longitude in degrees. East is positive, west is negative."),
    ("TimeZone", "TZ", "float", "item",
     "UTC offset in hours. China is 8."),
    ("Year", "Y", "int", "item", "Analysis year."),
    ("Month", "M", "int", "item", "Analysis month."),
    ("Day", "D", "int", "item", "Analysis day."),
    ("StartHour", "S", "float", "item",
     "Local clock hour to start the analysis window, 0 to 24."),
    ("EndHour", "E", "float", "item",
     "Local clock hour to end the analysis window. Must be greater than "
     "StartHour."),
    ("TimeStep", "TS", "float", "item",
     "Sampling interval in minutes. Smaller values resolve continuous "
     "segments more precisely and cost more time."),
    ("MinimumContinuousMinutes", "Min", "float", "item",
     "Shortest continuous direct-sun run that counts toward the qualified "
     "total, in minutes. Zero keeps the raw accumulated hours."),
]

CONTEXT_INPUT = (
    "ContextBuildings", "C", "geometrybase", "list",
    "Existing surrounding buildings used as the baseline obstruction. An "
    "empty list is a valid unobstructed baseline. Accepts Grasshopper "
    "geometry, a Rhino Guid, an ObjRef or a RhinoObject.",
)

PROTECTED_POINTS_INPUT = (
    "ProtectedPoints", "P", "point", "list",
    "Points whose sunlight must be evaluated. Accepts Grasshopper points, a "
    "Rhino Guid, an ObjRef, a RhinoObject or a Rhino Point.",
)

RUN_INPUT = (
    "Run", "R", "bool", "item",
    "Set to True to calculate. Leave False while wiring the inputs.",
)

REPORT_OUTPUT = (
    "Report", "Rp",
    "Status, inputs, statistics, warnings and errors. Connect a Panel and "
    "read this first after every run.",
)


def _inputs(*entries):
    return [
        {
            "name": name,
            "nickname": nickname,
            "description": description,
            "optional": True,
            "scriptParamAccess": access,
            "typeHintID": hint,
        }
        for name, nickname, hint, access, description in entries
    ]


def _outputs(*entries):
    return [
        {
            "name": name,
            "nickname": nickname,
            "description": description,
            "optional": False,
        }
        for name, nickname, description in entries
    ]


# Components ------------------------------------------------------------------

COMPONENTS = [
    {
        "name": "SolarConstraintSolver",
        "nickname": "Solve",
        "label": "Component 0",
        "description": (
            "Component 0. Evaluate direct sun at protected points with "
            "Context only and with Context plus Design, and report affected "
            "points and violations. Place two instances: one for the original "
            "DesignVolume, one to independently verify the optimized result."
        ),
        "docline": (
            "Evaluate protected-point sunlight before and after the design."
        ),
        "sources": {
            "rhino7": "src/rhino7/SolarConstraintSolver_Rhino7_GhPython.py",
            "rhino8": "src/rhino8/SolarConstraintSolver_Rhino8_SDK.py",
        },
        "instance_guids": {
            "rhino7": "28472408-7da8-4d3f-87bc-c05649308285",
            "rhino8": "518585f4-c1ba-4237-ac1b-5dad28c81836",
        },
        "icon": "solver",
        "inputs": _inputs(
            PROTECTED_POINTS_INPUT,
            ("DesignVolume", "V", "geometrybase", "list",
             "The proposed design volume evaluated as a separate obstruction "
             "role from ContextBuildings. Connect KeptVoxels here for the "
             "post-optimization verification instance."),
            CONTEXT_INPUT,
            *SOLAR_INPUTS,
            ("RequiredSunHours", "Req", "float", "item",
             "Qualified sun hours a point must reach. No regulation value is "
             "hard-coded."),
            ("ImpactTolerance", "Tol", "float", "item",
             "Lost hours above this value mark a point as affected by the "
             "design."),
            RUN_INPUT,
        ),
        "outputs": _outputs(
            ("SunHours", "H",
             "Final qualified direct-sun hours, one per ProtectedPoints item "
             "in the same order."),
            ("ViolationData", "V",
             "One record per affected or violating point, distinguishing "
             "existing-context violations from design-caused impact."),
            ("ConstraintData", "C",
             "Branch {i} holds the design-blocking events of "
             "ProtectedPoints[i]. Events are emitted only where Context is "
             "clear and the design blocks the sun."),
            REPORT_OUTPUT,
        ),
        "tree_outputs": ["ConstraintData"],
    },
    {
        "name": "SolarDesignVoxelizer",
        "nickname": "Voxel",
        "label": "Component 1",
        "description": (
            "Component 1. Split a closed DesignVolume into numbered, "
            "traceable, boundary-clipped column voxels. Outputs feed "
            "SolarVoxelOptimizer unchanged."
        ),
        "docline": (
            "Split a DesignVolume into numbered, traceable column voxels."
        ),
        "sources": {
            "rhino7": "src/rhino7/SolarDesignVoxelizer_Rhino7_GhPython.py",
            "rhino8": "src/rhino8/SolarDesignVoxelizer_Rhino8_SDK.py",
        },
        "instance_guids": {
            "rhino7": "9d690892-fe5b-4c95-9cf2-ddb6fff912e9",
            "rhino8": "b877ea64-7e9f-40d8-bf57-2559b680e316",
        },
        "icon": "voxelizer",
        "inputs": _inputs(
            ("DesignVolume", "V", "geometrybase", "list",
             "One or more valid closed solids to voxelize. Accepts "
             "Grasshopper geometry, a Rhino Guid, an ObjRef or a "
             "RhinoObject."),
            ("VoxelSizeXY", "XY", "float", "item",
             "Voxel edge length on the world X and Y axes, in model units. "
             "In a millimetre file 3000 means 3 metres."),
            ("VoxelSizeZ", "Z", "float", "item",
             "Voxel layer height on the world Z axis, in model units."),
            RUN_INPUT,
        ),
        "outputs": _outputs(
            ("Voxels", "V",
             "Flat list of voxel geometry. Fully contained cells are boxes; "
             "boundary cells are clipped to DesignVolume."),
            ("VoxelIDs", "ID",
             "Flat list of voxel IDs, aligned item by item with Voxels."),
            ("ColumnIDs", "C",
             "Flat list of column IDs grouping voxels by world XY grid "
             "location."),
            ("LayerIDs", "L",
             "Flat list of global world-Z layer indices. May contain gaps "
             "when the input does."),
            ("VoxelCenters", "Ctr",
             "Flat list of voxel centres. Clipped cells report their true "
             "centroid."),
            ("VoxelVolumes", "Vol",
             "Flat list of true solid volumes in cubic model units."),
            ("VoxelTree", "T",
             "Branch {c} holds the voxels of ColumnID c, ordered bottom to "
             "top."),
            REPORT_OUTPUT,
        ),
        "tree_outputs": ["VoxelTree"],
    },
    {
        "name": "SolarVoxelOptimizer",
        "nickname": "Optim",
        "label": "Component 2",
        "description": (
            "Component 2. Map every protected point and time sample to the "
            "voxels it passes through, then remove voxels top-down with a "
            "deterministic greedy heuristic until the sunlight requirement is "
            "met."
        ),
        "docline": "Remove voxels top-down until the sunlight requirement is met.",
        "sources": {
            "rhino7": "src/rhino7/SolarVoxelOptimizer_Rhino7_GhPython.py",
            "rhino8": "src/rhino8/SolarVoxelOptimizer_Rhino8_SDK.py",
        },
        "instance_guids": {
            "rhino7": "36848a58-bf71-4f14-a2e7-c0dd9aaa9729",
            "rhino8": "cc4d5fc5-19c7-4b79-bd03-380fb5e15441",
        },
        "icon": "optimizer",
        "inputs": _inputs(
            PROTECTED_POINTS_INPUT,
            ("Voxels", "V", "geometrybase", "list",
             "Voxel geometry from SolarDesignVoxelizer. Connect the output "
             "directly; do not sort, cull or dispatch it."),
            ("VoxelIDs", "ID", "int", "list",
             "Voxel IDs from SolarDesignVoxelizer, in the original order."),
            ("ColumnIDs", "C", "int", "list",
             "Column IDs from SolarDesignVoxelizer, in the original order."),
            ("LayerIDs", "L", "int", "list",
             "Layer IDs from SolarDesignVoxelizer, in the original order."),
            CONTEXT_INPUT,
            *SOLAR_INPUTS,
            ("RequiredSunHours", "Req", "float", "item",
             "Qualified sun hours each baseline-solvable point must reach."),
            ("MaxIterations", "It", "int", "item",
             "Upper bound on greedy removal rounds. Each round removes one "
             "action."),
            RUN_INPUT,
        ),
        "outputs": _outputs(
            ("KeptVoxels", "K",
             "Voxels surviving optimization. Feed these to a second "
             "SolarConstraintSolver instance to verify the result "
             "independently."),
            ("RemovedVoxels", "Rm",
             "Voxels removed to satisfy the sunlight requirement."),
            ("OptimizedColumns", "Col",
             "Kept voxels grouped by column."),
            ("KeepMask", "Msk",
             "Boolean per input voxel, aligned with the Voxels input order."),
            ("InitialSunHours", "I0",
             "Qualified sun hours per protected point before any removal."),
            ("FinalSunHours", "H",
             "Qualified sun hours per protected point after optimization."),
            ("VoxelImpactHours", "Imp",
             "Hours attributable to each voxel, aligned with the Voxels "
             "input order."),
            ("EventVoxelPaths", "Ev",
             "Branch {i} holds the voxel paths blocking ProtectedPoints[i]."),
            ("IterationData", "It",
             "One record per greedy round: the action taken, its cost and "
             "its gain."),
            REPORT_OUTPUT,
        ),
        "tree_outputs": ["EventVoxelPaths"],
    },
]


FLAVOURS = {
    "rhino7": {
        "directory": "rhino7",
        "category": "Sunlight",
        "subcategory": "Voxel Pipeline (IronPython)",
        "interpreter": "ironpython",
    },
    "rhino8": {
        "directory": "rhino8",
        "category": "Sunlight",
        "subcategory": "Voxel Pipeline",
        "interpreter": "cpython",
    },
}
