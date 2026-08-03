"""
Command line interface.

    python3 -m cadsolar inspect  --dxf site.dxf
    python3 -m cadsolar template --out scene.json
    python3 -m cadsolar analyze  --dxf site.dxf --city 上海 --day 大寒 --out ./result
    python3 -m cadsolar analyze  --scene scene.json --lat 31.23 --lon 121.47 ...

Every subcommand accepts --json, which prints one machine-readable object on
stdout. Human-readable text goes to stderr, so `--json` output can be piped
without filtering.
"""

import argparse
import json
import pathlib
import sys

from . import dxfio, scene_spec
from .cities import known_cities, lookup_city, lookup_day
from .pipeline import Settings, bearing_to_north_angle, run


def eprint(*args):
    print(*args, file=sys.stderr)


def fail(message, as_json):
    if as_json:
        print(json.dumps({"ok": False, "error": message}, ensure_ascii=False))
    else:
        eprint("错误：{0}".format(message))

    return 2


def load_scene(args):
    if args.dxf:
        return dxfio.read_scene(args.dxf, unit_scale=args.unit_scale)

    return scene_spec.load_spec(args.scene)


def resolve_settings(args):
    """Merge city/day presets with explicit flags. Explicit flags win."""
    latitude, longitude, timezone = args.lat, args.lon, args.tz
    month, day = args.month, args.day
    start_hour, end_hour = args.start, args.end
    notes = []

    if args.city:
        found = lookup_city(args.city)

        if found is None:
            raise ValueError(
                "不认识城市 {0!r}。已知：{1}。"
                "也可以直接给 --lat/--lon/--tz。".format(
                    args.city, "、".join(known_cities())
                )
            )

        city_lat, city_lon, city_tz = found
        latitude = city_lat if latitude is None else latitude
        longitude = city_lon if longitude is None else longitude
        timezone = city_tz if timezone is None else timezone
        notes.append("城市预设 {0}".format(args.city))

    if args.day_preset:
        found = lookup_day(args.day_preset)

        if found is None:
            raise ValueError(
                "不认识分析日 {0!r}。已知：大寒 / 冬至 / 春分 / 夏至。"
                .format(args.day_preset)
            )

        preset_month, preset_day, preset_start, preset_end, label = found
        month = preset_month if month is None else month
        day = preset_day if day is None else day
        start_hour = preset_start if start_hour is None else start_hour
        end_hour = preset_end if end_hour is None else end_hour
        notes.append("分析日预设 {0}".format(label))

    missing = [
        name
        for name, value in (
            ("--lat", latitude), ("--lon", longitude), ("--tz", timezone),
            ("--month", month), ("--day", day),
            ("--start", start_hour), ("--end", end_hour),
        )
        if value is None
    ]

    if missing:
        raise ValueError(
            "缺少参数：{0}。可以用 --city 和 --day 预设一次补齐。"
            .format("、".join(missing))
        )

    if end_hour <= start_hour:
        raise ValueError("--end 必须大于 --start。")

    if args.north_bearing is not None and args.north_angle is not None:
        raise ValueError(
            "--north-bearing 和 --north-angle 只能给一个。"
            "口语描述（北偏东/北偏西）用 --north-bearing。"
        )

    if args.north_bearing is not None:
        north_angle = bearing_to_north_angle(args.north_bearing)
        notes.append(
            "北向 {0:g}°（{1}）".format(
                args.north_bearing,
                "北偏东" if args.north_bearing > 0 else
                ("北偏西" if args.north_bearing < 0 else "正北"),
            )
        )
    else:
        north_angle = args.north_angle or 0.0

    settings = Settings(
        latitude=latitude,
        longitude=longitude,
        timezone=timezone,
        year=args.year,
        month=month,
        day=day,
        start_hour=start_hour,
        end_hour=end_hour,
        time_step=args.step,
        minimum_continuous_minutes=args.min_continuous,
        required_sun_hours=args.required,
        impact_tolerance=args.impact_tolerance,
        max_iterations=args.max_iterations,
        north_angle=north_angle,
        voxel_size_xy=args.voxel_xy,
        voxel_size_z=args.voxel_z,
    )
    return settings, notes


# ------------------------------------------------------------------ inspect

def command_inspect(args):
    try:
        scene = load_scene(args)
    except Exception as error:
        return fail(str(error), args.json)

    payload = {
        "ok": True,
        "source": scene.source,
        "unit_scale_metres_per_unit": scene.unit_scale,
        "design": [
            {
                "vertices": len(prism.polygon),
                "height_m": round(prism.height, 4),
                "footprint_area_m2": round(prism.volume / prism.height, 4),
                "volume_m3": round(prism.volume, 4),
            }
            for prism in scene.design
        ],
        "context": [
            {"height_m": round(prism.height, 4),
             "volume_m3": round(prism.volume, 4)}
            for prism in scene.context
        ],
        "protected_points": [
            {"x": round(x, 4), "y": round(y, 4), "z": round(z, 4)}
            for x, y, z in scene.protected_points
        ],
        "has_site_boundary": scene.site is not None,
    }

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        eprint("来源            {0}".format(scene.source))
        eprint("单位            {0} m/绘图单位".format(scene.unit_scale))
        eprint("方案体量        {0} 个，合计 {1:,.1f} m³".format(
            len(scene.design), sum(p.volume for p in scene.design)))
        eprint("周边建筑        {0} 个".format(len(scene.context)))
        eprint("保护点          {0} 个".format(len(scene.protected_points)))

        for index, (x, y, z) in enumerate(scene.protected_points):
            eprint("  [{0}] ({1:.2f}, {2:.2f}, {3:.2f})".format(index, x, y, z))

    return 0


# ----------------------------------------------------------------- template

def command_template(args):
    text = json.dumps(scene_spec.TEMPLATE, ensure_ascii=False, indent=2)

    if args.out:
        pathlib.Path(args.out).write_text(text + "\n", encoding="utf-8")
        eprint("已写入 {0}".format(args.out))
    else:
        print(text)

    return 0


# ------------------------------------------------------------------ analyze

def command_analyze(args):
    try:
        scene = load_scene(args)
        settings, notes = resolve_settings(args)
    except Exception as error:
        return fail(str(error), args.json)

    try:
        result = run(scene, settings)
    except Exception as error:
        return fail("计算失败：{0}".format(error), args.json)

    grid = result["grid"]
    outcome = result["outcome"]
    optimizer_hours = outcome["final_hours"]
    solver_hours = result["verification"]["sun_hours"]
    deltas = [abs(a - b) for a, b in zip(optimizer_hours, solver_hours)]
    worst = max(deltas) if deltas else 0.0
    verified = worst < 1.0e-9

    out_dir = pathlib.Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    dxf_path = dxfio.write_result(
        out_dir / "carved.dxf",
        result["kept"],
        result["removed"],
        scene.protected_points,
        scene.context,
        scene.unit_scale,
    )
    obj_path = dxfio.write_obj(
        out_dir / "carved.obj", result["kept"], scene.protected_points
    )

    points = []

    for index in range(len(scene.protected_points)):
        final = optimizer_hours[index]
        points.append(
            {
                "index": index,
                "baseline_hours": round(outcome["baseline_hours"][index], 4),
                "initial_hours": round(outcome["initial_hours"][index], 4),
                "final_hours": round(final, 4),
                "meets_requirement": bool(
                    final + 1e-9 >= settings.required_sun_hours
                ),
                "solvable_from_baseline": bool(outcome["solvable_mask"][index]),
            }
        )

    payload = {
        "ok": True,
        "verified": verified,
        "verification_max_delta_hours": worst,
        "presets_applied": notes,
        "settings": {
            "latitude": settings.latitude,
            "longitude": settings.longitude,
            "timezone": settings.timezone,
            "date": "{0:04d}-{1:02d}-{2:02d}".format(
                settings.year, settings.month, settings.day),
            "hours": [settings.start_hour, settings.end_hour],
            "time_step_minutes": settings.time_step,
            "minimum_continuous_minutes": settings.minimum_continuous_minutes,
            "required_sun_hours": settings.required_sun_hours,
            "voxel_size_xy_m": settings.voxel_size_xy,
            "voxel_size_z_m": settings.voxel_size_z,
            "north_angle_degrees": settings.north_angle,
            "north_bearing_degrees": -settings.north_angle,
        },
        "voxelizer": {
            "voxels": len(grid.records),
            "columns": grid.columns,
            "full_box": grid.full_count,
            "boundary_clipped": grid.clipped_count,
            "total_volume_m3": round(grid.total_volume, 4),
            "warnings": grid.warnings,
        },
        "optimizer": {
            "sun_samples": len(result["samples"]),
            "ray_tests": result["mapping"]["ray_test_count"],
            "iterations": len(outcome["iteration_data"]),
            "stop_reason": outcome["stop_reason"],
            "kept_voxels": len(result["kept"]),
            "removed_voxels": len(result["removed"]),
            "kept_volume_m3": round(result["kept_volume"], 4),
            "retained_volume_ratio": round(result["retained_ratio"], 6),
        },
        "protected_points": points,
        "all_points_meet_requirement": all(
            p["meets_requirement"] for p in points
        ),
        "outputs": {"dxf": dxf_path, "obj": obj_path},
        "timing_seconds": {
            key: round(value, 4)
            for key, value in result["timing"].items()
        },
        "disclaimer": (
            "设计阶段近似。采样对象是三维点，不是法规规定的窗台或满窗测点，"
            "不构成日照报审结果。"
        ),
    }

    (out_dir / "result.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        eprint("体素      {0} 个（{1} 柱，边界裁切 {2}）".format(
            len(grid.records), grid.columns, grid.clipped_count))
        eprint("切削      保留 {0} / 删除 {1}，保留率 {2:.2%}".format(
            len(result["kept"]), len(result["removed"]),
            result["retained_ratio"]))
        eprint("迭代      {0} 轮，{1}".format(
            len(outcome["iteration_data"]), outcome["stop_reason"]))
        eprint("")
        eprint("{0:>5}  {1:>10}  {2:>10}  {3:>10}  {4}".format(
            "点", "基准", "切削前", "切削后", "状态"))

        for point in points:
            eprint("{0:>5}  {1:>9.4f}h  {2:>9.4f}h  {3:>9.4f}h  {4}".format(
                point["index"], point["baseline_hours"],
                point["initial_hours"], point["final_hours"],
                "达标" if point["meets_requirement"] else (
                    "不达标" if point["solvable_from_baseline"]
                    else "基准即不可解")))

        eprint("")
        eprint("独立复核  {0}（最大偏差 {1:.2e} 小时）".format(
            "通过" if verified else "不一致", worst))
        eprint("输出      {0}".format(dxf_path))
        eprint("          {0}".format(obj_path))

    return 0 if verified else 1


# --------------------------------------------------------------------- main

def build_parser():
    parser = argparse.ArgumentParser(
        prog="cadsolar",
        description="日照约束体量切削（headless，不需要 Rhino）",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    def add_input(sub):
        group = sub.add_mutually_exclusive_group(required=True)
        group.add_argument("--dxf", help="按块命名约定绘制的 DXF")
        group.add_argument("--scene", help="场景描述 JSON")
        sub.add_argument("--unit-scale", type=float, default=None,
                         help="每绘图单位多少米，覆盖 DXF 的 $INSUNITS")
        sub.add_argument("--json", action="store_true",
                         help="向 stdout 输出机器可读 JSON")

    inspect = subparsers.add_parser("inspect", help="只解析输入并报告读到了什么")
    add_input(inspect)
    inspect.set_defaults(func=command_inspect)

    template = subparsers.add_parser("template", help="打印场景描述 JSON 模板")
    template.add_argument("--out", help="写入文件而不是 stdout")
    template.set_defaults(func=command_template)

    analyze = subparsers.add_parser("analyze", help="跑完整的体素化 + 切削 + 复核")
    add_input(analyze)
    analyze.add_argument("--out", default="./cadsolar-out", help="输出目录")
    analyze.add_argument("--city", help="城市预设，如 上海 / 北京")
    analyze.add_argument("--day", dest="day_preset",
                         help="分析日预设：大寒 / 冬至 / 春分 / 夏至")
    analyze.add_argument("--lat", type=float)
    analyze.add_argument("--lon", type=float)
    analyze.add_argument("--tz", type=float)
    analyze.add_argument("--year", type=int, default=2024)
    analyze.add_argument("--month", type=int)
    analyze.add_argument("--day-of-month", dest="day", type=int)
    analyze.add_argument("--start", type=float)
    analyze.add_argument("--end", type=float)
    analyze.add_argument("--step", type=float, default=10.0,
                         help="时间步长，分钟")
    analyze.add_argument("--min-continuous", type=float, default=60.0,
                         help="最短连续日照段，分钟；0 表示纯累计")
    analyze.add_argument("--required", type=float, default=2.0,
                         help="每个保护点要求的日照小时")
    analyze.add_argument("--impact-tolerance", type=float, default=0.1)
    analyze.add_argument("--max-iterations", type=int, default=200)
    analyze.add_argument(
        "--north-bearing", type=float, default=None,
        help="项目北向的方位角，度，自 +Y 起顺时针为正。"
             "北偏东15度写 15，北偏西15度写 -15。口语描述用这个")
    analyze.add_argument(
        "--north-angle", type=float, default=None,
        help="底层写法：北向自 +Y 起逆时针的旋转角，度。"
             "与 --north-bearing 符号相反，二选一")
    analyze.add_argument("--voxel-xy", type=float, default=6.0, help="米")
    analyze.add_argument("--voxel-z", type=float, default=6.0, help="米")
    analyze.set_defaults(func=command_analyze)

    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)
