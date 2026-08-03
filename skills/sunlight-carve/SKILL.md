---
name: sunlight-carve
version: 0.1.0
description: |
  日照约束体量切削：把一个设计体量按"周边保护点必须晒够几小时"的要求削成
  合规的可建体量，输出可以直接打开的 DXF。接受 CAD 图纸（块名带高度）或者
  纯自然语言描述的体量。不需要 Rhino、不需要 Grasshopper。
  Use when asked to "日照切削"、"体量削到达标"、"这栋楼挡了北边的日照怎么办"、
  "sunlight carving"、"日照可建体积"、"算一下这个方案挡不挡光"。
allowed-tools:
  - Bash
  - Read
  - Write
  - Glob
---

# /sunlight-carve — 日照约束体量切削

把设计体量切成"北边邻居也能晒够太阳"的形状。三步：体素化 → 按日照贪心切削 →
独立复核。引擎是纯 Python，跑一次通常一秒内。

## 第 0 步：定位引擎

```bash
CADSOLAR_ROOT=""
for candidate in "${CADSOLAR_HOME:-}" "$(pwd)" "$(git rev-parse --show-toplevel 2>/dev/null)" \
                 "$HOME/sunlightenvelope_rhino" "$HOME/sunlightenvelope-rhino"; do
  if [ -n "$candidate" ] && [ -f "$candidate/src/headless/cadsolar/cli.py" ]; then
    CADSOLAR_ROOT="$candidate"; break
  fi
done
if [ -z "$CADSOLAR_ROOT" ]; then
  echo "找不到引擎。请 cd 到项目目录，或设 CADSOLAR_HOME 指向仓库根目录。"; exit 1
fi
export PYTHONPATH="$CADSOLAR_ROOT/src/headless"
python3 -c "import ezdxf" 2>/dev/null || echo "缺依赖：pip install ezdxf"
echo "就绪：$CADSOLAR_ROOT"
```

找不到时不要猜路径，直接告诉用户上面那两个办法。后面所有命令写成
`python3 -m cadsolar ...`。

## 第 1 步：搞清楚在算什么

必须问出来的四件事，缺哪件问哪件，**不要替用户猜**：

| 要素 | 说明 | 缺了怎么办 |
|---|---|---|
| **设计体量** | 想盖的楼：平面轮廓 + 高度 | 必问 |
| **保护点** | 要保证日照的位置，通常是北侧既有住宅的窗 | 必问。位置和离地高度都要 |
| **周边建筑** | 已有的遮挡物 | 可以为空，但要确认"确实没有"而不是"忘了说" |
| **城市 + 分析日** | 决定太阳位置 | 可用预设，见下 |

**方位是最容易错的一件事。** 北半球冬季太阳在南边，所以**设计体量要在保护点的南侧
才会挡光**。如果用户描述的几何是设计体量在北、保护点在南，先回头确认，
多半是说反了——算出来会是"一点都不挡"，白跑一趟。

坐标系：+Y 是北，+X 是东。北向另有旋转时用 `--north-angle`（度，相对 +Y）。

## 第 2 步：拿到几何

### 情况 A：用户有 CAD 图纸

图纸要按块命名约定画。先只解析，确认读对了再算：

```bash
python3 -m cadsolar inspect --dxf <图纸.dxf>
```

块命名约定：

```
方案a-48m         设计体量，48 米高
周边建筑a-45m     周边建筑
建筑a-10m         同上
保护点a-1.5m      保护点，离地 1.5 米
地块-0m           用地边界（可选）
```

规则：体量画成**闭合多段线**放进块里；保护点块里放一个 `POINT`，平面位置取块的
插入点、高度取块名。单位支持 `m/米/mm/毫米`，缺省按米。角色前缀也接受
`scheme/design/context/building/point/site`。

解析失败一定会**报错并点名到具体的块**，不会静默跳过。常见错误：块名漏了连字符
（`周边建筑a50m`）、多段线没闭合、图纸没声明单位。把错误原话转给用户，不要自己
猜着改图。

### 情况 B：用户只是嘴上描述

不用让人家先去开 CAD。写一份场景 JSON：

```bash
python3 -m cadsolar template --out scene.json
```

```json
{
  "units": "m",
  "design":  [{"name": "方案a", "box": [12, 0, 56, 33], "height": 48}],
  "context": [{"name": "周边a", "box": [62, -34, 96, -2], "height": 45}],
  "protected_points": [{"name": "北侧住宅窗1", "x": 2, "y": 52, "z": 1.5}]
}
```

`box` 是 `[x0, y0, x1, y1]`；不规则轮廓改用 `"footprint": [[x,y], ...]`。
所有体量都从 z=0 起算。写完先 `inspect --scene scene.json` 让用户确认一遍
几何对不对，再往下算。

## 第 3 步：算

```bash
python3 -m cadsolar analyze \
  --dxf <图纸.dxf> \
  --city 上海 --day 大寒 \
  --required 2 --min-continuous 60 \
  --voxel-xy 6 --voxel-z 6 \
  --out ./result --json
```

`--scene scene.json` 替换 `--dxf` 即可。

预设：城市 `上海/北京/广州/深圳/杭州/南京/成都/武汉/西安/天津/重庆/沈阳/哈尔滨/
青岛/郑州/长沙/昆明/乌鲁木齐`；分析日 `大寒`(1-20, 8–16点) / `冬至`(12-22, 9–15点) /
`春分` / `夏至`。显式给的 `--lat/--lon/--tz/--month/--day-of-month/--start/--end`
优先于预设。城市坐标是市中心近似值，真实项目应给实测坐标。

关键参数：

| 参数 | 含义 | 建议 |
|---|---|---|
| `--required` | 每个保护点要求的日照小时 | 住宅常用 2 |
| `--min-continuous` | 最短连续段（分钟），短于此不计入 | 中国规范核心，常用 60；填 0 退化为纯累计 |
| `--voxel-xy` `--voxel-z` | 体素尺寸（**米**） | 先 6 跑通，再降到 3 加密 |
| `--step` | 时间步长（分钟） | 先 10，精细时 5 |
| `--north-angle` | 北向相对 +Y 的旋转 | 默认 0 |

`--json` 会把结构化结果打到 stdout，人类可读的表格走 stderr，可以直接管道解析。

## 第 4 步：读结果

先看两个字段，其余都是细节：

```
verified                     独立复核是否通过（必须 true）
all_points_meet_requirement  是否所有点都达标
```

`verified` 是**用另一个独立的求解器**重算切削后的体量，跟切削器自己的答案对。
不一致说明有 bug，**不要把结果给用户**，直接报告异常。

然后按点看 `protected_points[]`：

| 字段 | 含义 |
|---|---|
| `baseline_hours` | 只有周边建筑时能晒多久 |
| `initial_hours` | 加上原设计体量后剩多少 |
| `final_hours` | 切削后 |
| `solvable_from_baseline` | `false` 表示**周边建筑本身就已经让它不达标**，删设计体量也救不回来 |

`solvable_from_baseline: false` 要单独说明——这不是方案的锅，是现状条件。

再看 `optimizer.retained_volume_ratio`：保留率。这是用户最关心的数字，
"为了让邻居达标，我损失了多少建筑面积"。

输出文件：`result/carved.dxf`（保留体量和切除体量分层，可直接在 CAD 打开）、
`result/carved.obj`（快速看形）、`result/result.json`。

## 第 5 步：怎么跟用户讲

按这个顺序：

1. **结论**：达标了没有，损失多少体积
2. **逐点**：哪个点原来多少、现在多少
3. **不可解的点**（如果有）：说清是现状造成的
4. **文件**：DXF 在哪，怎么用
5. **边界**：见下，**每次都要说**

一定要说的边界：

> 这是**设计阶段近似**。采样对象是三维点，不是法规规定的窗台或满窗测点，
> 不能作为日照报审结果。切削用的是贪心启发式，给出一个可用解，不声称是
> 体积最大的解。

## 调参和排错

**算得慢**：优先调大 `--voxel-xy/--voxel-z`，其次调大 `--step`，最后减周边建筑。
6 米体素通常一秒内出结果。

**一个点都没被挡**（`initial_hours` 全等于 `baseline_hours`，0 轮迭代，保留率
100%）：几乎一定是方位反了，设计体量不在保护点南侧。回第 1 步确认。

**保留率低得离谱**（比如 20%）：说明要求太苛刻——可能是保护点贴得太近、
设计体量太高，或者 `--required` 给大了。把这个事实告诉用户，让人家决定是改
方案还是改预期，不要自己偷偷放宽参数。

**结果随体素尺寸变化**：正常。贪心启发式在不同离散度下解不同（同一场景 6/4/3 米
体素的保留率可能是 57%/65%/67%）。**报数时必须连体素尺寸一起报。**

**`ok: false`**：把 `error` 原文转给用户。错误信息都点名到具体的块或参数。

## 这个工具做不了什么

- **不做非垂直几何**。只支持平面轮廓竖直拉伸：悬挑、斜屋面、曲面表皮做不了。
  退台和裙房+塔楼可以拆成多个块绕过去。
- **不出报审报告**。见上面的边界声明。
- **不做全局最优**。贪心。
- **同一格子里多个设计体量重叠时不做实体并集**，会取面积最大的那个并告警。
  看到 `voxelizer.warnings` 非空要转告用户。

## 相关

- 引擎说明与验证记录：`docs/HEADLESS_ENGINE.md`
- 同一套算法的 Rhino/Grasshopper 版本：项目 `README.md`，适合要在 GH 里继续
  深化的用户
