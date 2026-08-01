"""
Validate .ghuser source bundles before running the componentizer.

The componentizer needs IronPython and GH_IO.dll, so it usually runs only on a
Rhino machine. This script runs anywhere and catches the mistakes that would
otherwise surface as a failed or, worse, a silently wrong build: an unknown
type hint, a bad access value, a missing bundle file, or a RunScript signature
that disagrees with the declared ports.

The valid value tables below mirror componentize_ipy.py from
compas-dev/compas-actions.ghpython_components.

Usage
-----
    python3 tools/check_ghuser_bundle.py
"""

from __future__ import print_function

import io
import json
import os
import re
import struct
import sys


REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COMPONENTS_ROOT = os.path.join(REPO_ROOT, "src", "ghuser", "components")

VALID_TYPE_HINTS = set(
    """none ghdoc float bool int complex str datetime guid color point vector
    plane interval uvinterval box transform line circle arc polyline rectangle
    curve mesh surface subd brep geometrybase""".split()
)

VALID_ACCESS = set(["item", "list", "tree", 0, 1, 2])
VALID_EXPOSURE = set([-1, 2, 4, 8, 16, 32, 64, 128])

REQUIRED_TOP_LEVEL = ["name", "nickname", "category", "subcategory", "ghpython"]

ICON_SIZE = (24, 24)

GUID_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


def png_size(path):
    """Return (width, height) of a PNG without needing an image library."""
    with open(path, "rb") as handle:
        header = handle.read(24)

    if len(header) < 24 or header[:8] != b"\x89PNG\r\n\x1a\n":
        return None

    return struct.unpack(">II", header[16:24])


def runscript_params(code_path):
    """Return the RunScript parameter names declared in code.py."""
    with io.open(code_path, encoding="utf-8") as handle:
        source = handle.read()

    match = re.search(r"def RunScript\(self,(.*?)\):", source, re.DOTALL)

    if not match:
        return None

    raw = match.group(1)
    return [name.strip() for name in raw.split(",") if name.strip()]


def check_bundle(directory, problems):
    name = os.path.basename(directory)

    def fail(message):
        problems.append("{0}: {1}".format(name, message))

    icon = os.path.join(directory, "icon.png")
    code = os.path.join(directory, "code.py")
    meta = os.path.join(directory, "metadata.json")

    for path, label in ((icon, "icon.png"), (code, "code.py"), (meta, "metadata.json")):
        if not os.path.exists(path):
            fail("missing {0}".format(label))
            return

    size = png_size(icon)

    if size is None:
        fail("icon.png is not a valid PNG")
    elif size != ICON_SIZE:
        fail("icon.png is {0}x{1}, expected 24x24".format(size[0], size[1]))

    try:
        with io.open(meta, encoding="utf-8") as handle:
            data = json.load(handle)
    except ValueError as error:
        fail("metadata.json is not valid JSON: {0}".format(error))
        return

    for key in REQUIRED_TOP_LEVEL:
        if key not in data:
            fail("metadata.json is missing required key '{0}'".format(key))

    nickname = data.get("nickname", "")

    if not 1 <= len(nickname) <= 5:
        fail(
            "nickname '{0}' should be 1-5 characters".format(nickname)
        )

    if "exposure" in data and data["exposure"] not in VALID_EXPOSURE:
        fail(
            "exposure {0} is invalid, expected one of {1}".format(
                data["exposure"], sorted(VALID_EXPOSURE)
            )
        )

    instance_guid = data.get("instanceGuid")

    if instance_guid is None:
        fail(
            "no instanceGuid: every rebuild would produce a component "
            "Grasshopper treats as unrelated to the previous one"
        )
    elif not GUID_PATTERN.match(instance_guid):
        fail("instanceGuid '{0}' is not a GUID".format(instance_guid))

    ghpython = data.get("ghpython", {})
    inputs = ghpython.get("inputParameters", [])
    outputs = ghpython.get("outputParameters", [])

    if not inputs:
        fail("no inputParameters declared")

    if not outputs:
        fail("no outputParameters declared")

    seen = set()

    for parameter in inputs:
        parameter_name = parameter.get("name")

        if not parameter_name:
            fail("an input parameter has no name")
            continue

        if parameter_name in seen:
            fail("duplicate input name '{0}'".format(parameter_name))

        seen.add(parameter_name)

        hint = parameter.get("typeHintID")

        if hint is not None and hint not in VALID_TYPE_HINTS:
            fail(
                "input '{0}' has unknown typeHintID '{1}'".format(
                    parameter_name, hint
                )
            )

        access = parameter.get("scriptParamAccess")

        if access is not None and access not in VALID_ACCESS:
            fail(
                "input '{0}' has invalid scriptParamAccess '{1}'".format(
                    parameter_name, access
                )
            )

    seen_out = set()

    for parameter in outputs:
        parameter_name = parameter.get("name")

        if not parameter_name:
            fail("an output parameter has no name")
            continue

        if parameter_name in seen_out:
            fail("duplicate output name '{0}'".format(parameter_name))

        seen_out.add(parameter_name)

    # The port names are the component's contract. If code.py and metadata.json
    # disagree, the build succeeds and the component fails at run time.
    if ghpython.get("isAdvancedMode"):
        declared = runscript_params(code)

        if declared is None:
            fail("isAdvancedMode is true but code.py has no RunScript(self, ...)")
        else:
            expected = [parameter.get("name") for parameter in inputs]

            if declared != expected:
                fail(
                    "RunScript signature {0} does not match "
                    "inputParameters {1}".format(declared, expected)
                )


def main():
    if not os.path.isdir(COMPONENTS_ROOT):
        print("No component bundles found at {0}".format(COMPONENTS_ROOT))
        return 1

    directories = sorted(
        os.path.join(COMPONENTS_ROOT, entry)
        for entry in os.listdir(COMPONENTS_ROOT)
        if os.path.isdir(os.path.join(COMPONENTS_ROOT, entry))
    )

    if not directories:
        print("No component bundles found at {0}".format(COMPONENTS_ROOT))
        return 1

    problems = []

    for directory in directories:
        check_bundle(directory, problems)

    for directory in directories:
        name = os.path.basename(directory)
        related = [p for p in problems if p.startswith(name + ":")]

        if related:
            print("FAIL  {0}".format(name))
            for problem in related:
                print("      {0}".format(problem.split(": ", 1)[1]))
        else:
            print("OK    {0}".format(name))

    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
