"""
Install the sunlight-carve skill and check that the engine actually runs.

Written to be driven by an AI assistant as well as a person, so it is
idempotent, it never guesses, and it finishes by computing a known scene and
comparing the numbers - "the files were copied" is not the same as "it works".

    python3 tools/install_skill.py            # install, then verify
    python3 tools/install_skill.py --check    # verify only, write nothing
    python3 tools/install_skill.py --link     # symlink instead of copying
    python3 tools/install_skill.py --with-deps  # also pip install ezdxf

Installing writes into the user's skills directory (~/.claude/skills by
default). Nothing else on the machine is touched unless --with-deps is given,
because installing packages into someone's Python is their decision.
"""

import argparse
import importlib.util
import os
import pathlib
import shutil
import subprocess
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
SKILL_SRC = REPO / "skills" / "sunlight-carve"
ENGINE = REPO / "src" / "headless"
REFERENCE = ENGINE / "scene" / "reference.dxf"

# Cross-checked against the Rhino 8 components on the same scene; see
# docs/HEADLESS_ENGINE.md. If a change moves these, the change is wrong
# until proven otherwise.
EXPECTED = {
    "voxels": 328,
    "columns": 41,
    "kept": 185,
    "removed": 143,
    "final_hours": [4.1667, 2.1667, 2.0, 2.0],
}

REQUIRED_PYTHON = (3, 8)


class Step(object):
    """One reported step. Nothing is printed twice, nothing is implied."""

    def __init__(self, ok, title, detail=""):
        self.ok = ok
        self.title = title
        self.detail = detail

    def show(self):
        mark = "OK  " if self.ok else "FAIL"
        print("[{0}] {1}".format(mark, self.title))

        if self.detail:
            for line in self.detail.splitlines():
                print("       " + line)


def default_dest():
    return pathlib.Path.home() / ".claude" / "skills"


def check_python():
    version = sys.version_info[:3]

    if version[:2] < REQUIRED_PYTHON:
        return Step(
            False, "Python 版本",
            "需要 {0}.{1} 以上，当前 {2}".format(
                REQUIRED_PYTHON[0], REQUIRED_PYTHON[1],
                ".".join(str(v) for v in version))
        )

    return Step(True, "Python {0}".format(".".join(str(v) for v in version)))


def check_dependency(install):
    if importlib.util.find_spec("ezdxf") is not None:
        return Step(True, "依赖 ezdxf 已就绪")

    if not install:
        return Step(
            False, "依赖 ezdxf 未安装",
            "读写 DXF 需要它。安装：\n"
            "  {0} -m pip install ezdxf\n"
            "或者重跑本脚本并加 --with-deps。\n"
            "若报 externally-managed-environment，用虚拟环境：\n"
            "  python3 -m venv .venv && .venv/bin/pip install ezdxf".format(
                sys.executable)
        )

    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "ezdxf"],
        capture_output=True, text=True,
    )
    output = result.stdout + result.stderr

    if result.returncode == 0 and importlib.util.find_spec("ezdxf"):
        return Step(True, "已安装 ezdxf")

    if "externally-managed-environment" in output:
        return Step(
            False, "无法安装 ezdxf：这个 Python 受系统管控",
            "不要用 --break-system-packages 硬来。建虚拟环境：\n"
            "  python3 -m venv .venv\n"
            "  .venv/bin/pip install ezdxf\n"
            "之后用 .venv/bin/python 跑本项目。"
        )

    return Step(False, "安装 ezdxf 失败", output.strip()[-400:])


def install_skill(dest_root, use_link, dry_run):
    if not SKILL_SRC.is_dir():
        return Step(False, "找不到 skill 源目录", str(SKILL_SRC))

    target = pathlib.Path(dest_root) / SKILL_SRC.name

    if dry_run:
        state = "已安装" if target.exists() else "未安装"
        return Step(target.exists(), "skill 位置 {0}（{1}）".format(target, state))

    target.parent.mkdir(parents=True, exist_ok=True)

    if target.is_symlink() or target.exists():
        if target.is_symlink() or target.is_file():
            target.unlink()
        else:
            shutil.rmtree(target)

    if use_link:
        try:
            target.symlink_to(SKILL_SRC, target_is_directory=True)
            return Step(True, "已软链 skill", "{0} -> {1}".format(target, SKILL_SRC))
        except OSError as error:
            shutil.copytree(SKILL_SRC, target)
            return Step(
                True, "已复制 skill（软链失败，已回退）",
                "{0}\n软链失败原因：{1}".format(target, error)
            )

    shutil.copytree(SKILL_SRC, target)
    return Step(True, "已复制 skill", str(target))


def verify_engine():
    """Compute the reference scene and compare against the cross-checked run."""
    if not REFERENCE.exists():
        return Step(False, "找不到参考场景", str(REFERENCE))

    if importlib.util.find_spec("ezdxf") is None:
        return Step(False, "跳过引擎自检", "ezdxf 未安装")

    sys.path.insert(0, str(ENGINE))

    try:
        from cadsolar import dxfio, pipeline
    except Exception as error:
        return Step(False, "引擎导入失败", repr(error))

    try:
        scene = dxfio.read_scene(REFERENCE)
        result = pipeline.run(scene, pipeline.Settings())
    except Exception as error:
        return Step(False, "引擎运行失败", repr(error))

    grid = result["grid"]
    got = {
        "voxels": len(grid.records),
        "columns": grid.columns,
        "kept": len(result["kept"]),
        "removed": len(result["removed"]),
        "final_hours": [
            round(v, 4) for v in result["outcome"]["final_hours"]
        ],
    }

    solver = [round(v, 4) for v in result["verification"]["sun_hours"]]
    mismatched = [k for k in EXPECTED if got[k] != EXPECTED[k]]

    if mismatched or solver != got["final_hours"]:
        lines = ["参考场景结果与已核对的基准不一致："]

        for key in EXPECTED:
            flag = "  <-" if key in mismatched else ""
            lines.append("  {0}: 期望 {1}，实际 {2}{3}".format(
                key, EXPECTED[key], got[key], flag))

        if solver != got["final_hours"]:
            lines.append("  独立复核不一致: {0}".format(solver))

        return Step(False, "引擎自检未通过", "\n".join(lines))

    return Step(
        True, "引擎自检通过",
        "参考场景：{0} 体素 / 保留 {1} / 切除 {2}，"
        "逐点 {3}，独立复核一致".format(
            got["voxels"], got["kept"], got["removed"], got["final_hours"])
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dest", default=None,
                        help="skills 目录，默认 ~/.claude/skills")
    parser.add_argument("--link", action="store_true",
                        help="软链而不是复制，让 skill 跟仓库同步")
    parser.add_argument("--with-deps", action="store_true",
                        help="缺 ezdxf 时执行 pip install")
    parser.add_argument("--check", action="store_true",
                        help="只检查，不写任何文件")
    args = parser.parse_args()

    dest = pathlib.Path(args.dest) if args.dest else default_dest()

    print("仓库    {0}".format(REPO))
    print("skills  {0}".format(dest))
    print("")

    steps = [
        check_python(),
        check_dependency(args.with_deps and not args.check),
        install_skill(dest, args.link, args.check),
        verify_engine(),
    ]

    for step in steps:
        step.show()

    print("")
    failed = [s for s in steps if not s.ok]

    if failed:
        print("未完成 {0} 项，按上面的提示处理后重跑本脚本。".format(len(failed)))
        return 1

    if args.check:
        print("检查通过。")
        return 0

    print("安装完成。让 AI 助手找到引擎，二选一：")
    print("  cd {0}   然后直接提要求".format(REPO))
    print("  export CADSOLAR_HOME={0}".format(REPO))
    print("")
    print("试一句：帮我算一下这个方案挡不挡北边住宅的日照")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
