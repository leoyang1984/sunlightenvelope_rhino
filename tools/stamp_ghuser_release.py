"""
Stamp and verify the prebuilt .ghuser files committed under dist/ghuser.

The built components are committed so people can download them straight from
the repository without a GitHub account and without compiling anything. That
creates one hazard: someone edits a script or a port and forgets to rebuild,
and the repository ships components that no longer match their source.

The componentizer assigns a fresh GUID to every input and output parameter on
each run, so the .ghuser files are not byte-reproducible and cannot be checked
by rebuilding and comparing. What is reproducible is the *source* of a build:
everything under src/ghuser. This tool records a digest of those sources
alongside the binaries, so a stale drop is detectable even though the binaries
themselves are not.

Usage
-----
    python3 tools/stamp_ghuser_release.py --run-url URL   # write the manifest
    python3 tools/stamp_ghuser_release.py --check         # verify it

--check fails when src/ghuser has changed since the committed binaries were
built. Rebuild in CI, download the artifacts, replace dist/ghuser and stamp
again.
"""

from __future__ import print_function

import argparse
import hashlib
import io
import os
import sys

sys.dont_write_bytecode = True

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOURCE_ROOT = os.path.join(REPO_ROOT, "src", "ghuser")
DIST_ROOT = os.path.join(REPO_ROOT, "dist", "ghuser")
MANIFEST = os.path.join(DIST_ROOT, "MANIFEST.txt")

SOURCE_DIGEST_PREFIX = "source-digest: "


def iter_source_files():
    """Every file under src/ghuser, in a stable order."""
    collected = []

    for current, directories, files in os.walk(SOURCE_ROOT):
        directories.sort()

        for name in sorted(files):
            if name == ".DS_Store":
                continue

            collected.append(os.path.join(current, name))

    return sorted(collected)


def source_digest():
    """Digest of the bundle sources the committed binaries were built from."""
    digest = hashlib.sha256()

    for path in iter_source_files():
        relative = os.path.relpath(path, REPO_ROOT).replace(os.sep, "/")
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")

        with open(path, "rb") as handle:
            digest.update(handle.read())

        digest.update(b"\0")

    return digest.hexdigest()


def iter_built_files():
    collected = []

    for current, directories, files in os.walk(DIST_ROOT):
        directories.sort()

        for name in sorted(files):
            if name.endswith(".ghuser"):
                collected.append(os.path.join(current, name))

    return sorted(collected)


def read_manifest_digest():
    if not os.path.exists(MANIFEST):
        return None

    with io.open(MANIFEST, encoding="utf-8") as handle:
        for line in handle:
            if line.startswith(SOURCE_DIGEST_PREFIX):
                return line[len(SOURCE_DIGEST_PREFIX):].strip()

    return None


def write_manifest(run_url):
    built = iter_built_files()

    if not built:
        raise SystemExit(
            "No .ghuser files under {0}. Download them from the CI run "
            "first.".format(os.path.relpath(DIST_ROOT, REPO_ROOT))
        )

    lines = [
        "Prebuilt Grasshopper User Objects",
        "",
        "These files are built by .github/workflows/build-ghuser.yml and",
        "committed so they can be downloaded without a GitHub account.",
        "Do not edit them by hand.",
        "",
        SOURCE_DIGEST_PREFIX + source_digest(),
        "built-from-run: " + (run_url or "unrecorded"),
        "",
        "files:",
    ]

    for path in built:
        with open(path, "rb") as handle:
            data = handle.read()

        lines.append(
            "  {0}  {1} bytes  sha256:{2}".format(
                os.path.relpath(path, DIST_ROOT).replace(os.sep, "/"),
                len(data),
                hashlib.sha256(data).hexdigest(),
            )
        )

    lines.append("")

    with io.open(MANIFEST, "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines))

    print("Stamped {0} file(s) into {1}".format(
        len(built), os.path.relpath(MANIFEST, REPO_ROOT)
    ))
    return 0


def check():
    recorded = read_manifest_digest()

    if recorded is None:
        print(
            "No source digest recorded in {0}.".format(
                os.path.relpath(MANIFEST, REPO_ROOT)
            )
        )
        return 1

    current = source_digest()

    if current == recorded:
        print("Prebuilt components match the current bundle sources.")
        return 0

    print("The prebuilt components under dist/ghuser are STALE.")
    print("  recorded source digest: {0}".format(recorded))
    print("  current source digest:  {0}".format(current))
    print("")
    print("src/ghuser changed after these binaries were built. Rerun the")
    print("Build User Objects workflow, download both artifacts, replace")
    print("dist/ghuser, then run:")
    print("")
    print("    python3 tools/stamp_ghuser_release.py --run-url <run URL>")
    return 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="verify the committed binaries against the bundle sources",
    )
    parser.add_argument(
        "--run-url",
        help="URL of the CI run the committed binaries came from",
    )
    arguments = parser.parse_args()

    if arguments.check:
        return check()

    return write_manifest(arguments.run_url)


if __name__ == "__main__":
    sys.exit(main())
