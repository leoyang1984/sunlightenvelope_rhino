"""
Rebuild a .3dm from its geometry alone, dropping everything else.

A Rhino file carries more than the model. The render environment, texture
cache and material slots record absolute paths into the author's home
directory, so a file saved on a Mac ships a line like

    /Users/<name>/Library/Application Support/McNeel/Rhinoceros/8.0/...

into any public repository. Nothing in there is needed to open the example.

This copies layers, objects, their attributes, units and tolerance into a
fresh document and writes that out. Render content, plug-in data, notes,
document user data and the undo history do not come along.

    python3 tools/sanitize_3dm.py <input.3dm> [-o output.3dm] [--check]

--check reports what would be dropped without writing anything.

Needs rhino3dm (pip install rhino3dm). Rhino itself is not required.
"""

import argparse
import pathlib
import re
import sys

try:
    import rhino3dm
except ImportError:
    sys.exit("需要 rhino3dm：pip install rhino3dm")


LEAK_PATTERNS = [
    re.compile(rb"/Users/[^\"<\x00]{1,80}"),
    re.compile(rb"/home/[^\"<\x00]{1,80}"),
    re.compile(rb"C:\\\\Users\\\\[^\"<\x00]{1,80}"),
    re.compile(rb"/Volumes/[^\"<\x00]{1,80}"),
]


def find_leaks(path):
    """Return the set of home-directory-ish paths embedded in a file."""
    data = pathlib.Path(path).read_bytes()
    found = set()

    for pattern in LEAK_PATTERNS:
        for match in pattern.findall(data):
            try:
                found.add(match.decode("utf-8", "replace"))
            except Exception:
                pass

    return found


def sanitize(source, target):
    original = rhino3dm.File3dm.Read(str(source))

    if original is None:
        raise SystemExit("无法读取 {0}".format(source))

    clean = rhino3dm.File3dm()
    clean.Settings.ModelUnitSystem = original.Settings.ModelUnitSystem
    clean.Settings.ModelAbsoluteTolerance = (
        original.Settings.ModelAbsoluteTolerance
    )
    clean.Settings.ModelAngleToleranceRadians = (
        original.Settings.ModelAngleToleranceRadians
    )

    index_map = {}

    for layer in original.Layers:
        fresh = rhino3dm.Layer()
        fresh.Name = layer.Name
        fresh.Color = layer.Color
        fresh.Visible = layer.Visible
        fresh.Locked = layer.Locked
        index_map[layer.Index] = len(clean.Layers)
        clean.Layers.Add(fresh)

    copied = 0
    skipped = 0

    for item in original.Objects:
        geometry = item.Geometry

        if geometry is None:
            skipped += 1
            continue

        attributes = rhino3dm.ObjectAttributes()
        attributes.Name = item.Attributes.Name
        attributes.LayerIndex = index_map.get(item.Attributes.LayerIndex, 0)
        attributes.Visible = item.Attributes.Visible

        try:
            clean.Objects.Add(geometry, attributes)
            copied += 1
        except Exception:
            skipped += 1

    clean.Write(str(target), 0)
    return copied, skipped, len(clean.Layers)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("source")
    parser.add_argument("-o", "--output")
    parser.add_argument("--check", action="store_true",
                        help="只报告嵌入的本机路径，不写文件")
    args = parser.parse_args()

    source = pathlib.Path(args.source)
    leaks = find_leaks(source)

    print("输入 {0}（{1:,} 字节）".format(source, source.stat().st_size))

    if leaks:
        print("嵌入的本机路径 {0} 处：".format(len(leaks)))

        for leak in sorted(leaks)[:8]:
            print("  {0}".format(leak))
    else:
        print("没有发现嵌入的本机路径。")

    if args.check:
        return 1 if leaks else 0

    target = pathlib.Path(args.output or source)
    temporary = target.with_suffix(".sanitized.3dm")
    copied, skipped, layers = sanitize(source, temporary)

    remaining = find_leaks(temporary)

    if remaining:
        print("清洗后仍有残留，未替换原文件：")

        for leak in sorted(remaining)[:8]:
            print("  {0}".format(leak))

        return 2

    temporary.replace(target)
    print("输出 {0}（{1:,} 字节）".format(target, target.stat().st_size))
    print("对象 {0} 个（跳过 {1}），图层 {2} 个，无本机路径。".format(
        copied, skipped, layers))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
