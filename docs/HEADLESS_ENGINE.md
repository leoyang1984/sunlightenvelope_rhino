# Headless 引擎：CAD → 日照切削，不需要 Rhino

把输入约定成「CAD 图纸 + 带高度的块名」之后，整条流水线不再需要 Rhino。
结果与 Rhino 组件逐项一致，速度快约 450 倍，体积守恒更严格。

配套的 agent skill 是 `/sunlight-carve`。

---

## 怎么跑

```bash
export PYTHONPATH=src/headless
```

```bash
python3 -m cadsolar inspect  --dxf src/headless/scene/reference.dxf
python3 -m cadsolar template --out scene.json
python3 -m cadsolar analyze  --dxf src/headless/scene/reference.dxf \
    --city 上海 --day 大寒 --out ./result --json
```

`analyze` 接受 `--dxf`（按块命名约定绘制）或 `--scene`（JSON 描述，不需要 CAD）。
`--json` 把结构化结果打到 stdout，人类可读表格走 stderr。退出码 0 表示独立复核通过。

测试与基准：

```bash
python3 -m unittest discover -s tests
python3 src/headless/make_reference_scene.py      # 重新生成参考场景
python3 tools/bench_headless.py                   # 性能与粗筛等价性
python3 tools/crosscheck_rhino.py                 # 需经 rhinocode 在 Rhino 内运行
```

只依赖 `ezdxf` 和 `numpy`（numpy 仅基准脚本用）。不需要 Rhino、不需要 shapely。

---

## 做法：算法不重写，只换几何原语

`cadsolar/kernel.py` 直接解析 `src/rhino8/` 里的组件文件，把**不碰 RhinoCommon
的顶层函数原样抽出来执行**，只替换那几个绑 Rhino 的名字：

| 组件里的名字 | 换成 |
|---|---|
| `mesh_ray_distance` / `ray_mesh_hit` | `geom.ray_distance`（射线 vs 拉伸体） |
| `solar_position_to_vector` | 元组运算 |
| `check_escape_key` | 恒返回 False |
| `active_document_units` | 固定字符串 |
| `make_constraint_event` | 普通 dict，去掉 Rhino Line |

抽出来的量：**组件2 有 27 个函数、组件0 有 23 个函数原样运行**，包括太阳位置、
区间积分、连续时段规则、贪心顶部闭包搜索、报告生成。

这样做而不是手工移植的理由：如果结果和 Rhino 对不上，差异只可能来自被替换的几何
原语，因为算法本身是同一份字节。

真正新写的只有**组件1（体素化）**，因为它依赖的 Brep Boolean 在 2.5D 下有解析解。

### 四个 Rhino 内核操作的替代

| Rhino | 这里 | 性质 |
|---|---|---|
| `Intersect.Intersection.MeshRay` | `Prism.ray_distance` | 2D 射线-多边形 + Z 区间 |
| `Mesh.IsPointInside` | `point_in_polygon` + Z 区间 | 奇偶规则 |
| `Brep.CreateBooleanIntersection` | `clip_polygon_to_rect` | Sutherland–Hodgman |
| `VolumeMassProperties.Compute` | `polygon_area × height` | 解析解 |

---

## 块命名约定

```
<角色><标签>-<数值><单位>

方案a-48m         设计体量，48 米高
周边建筑a-45m     周边建筑，45 米高
建筑a-10m         同上
保护点a-1.5m      保护点，离地 1.5 米
地块-0m           用地边界（高度忽略）
```

角色前缀支持 `方案/设计/建筑/周边/周边建筑/既有建筑/保护点/日照点/测点/地块/场地`
和 `scheme/design/context/existing/building/point/pt/site`，最长匹配优先。
单位支持 `m/米/mm/毫米`，缺省按米。全角字符和 `－＿` 分隔符自动折叠。

体量画成**闭合多段线**放进块里；保护点块里放一个 `POINT`。平面位置来自块的插入点，
高度来自块名。

---

## 跑出来的结果

参考场景（`make_scene.py` 生成）：上海，大寒日 9:00–15:00，一个 48 米高的梯形方案
体量正南侧挡住四个保护点，两栋周边建筑分别吃掉东侧的早晨和西侧的下午。

```
组件1   328 体素 / 41 柱 / 边界裁切 104 个 / Boolean 失败 0
组件2   36 个太阳样本，8 轮迭代，移除 143 个，保留率 59.25%
        Baseline  [5.67, 4.33, 4.00, 3.17]
        Initial   [3.83, 0.00, 0.00, 0.00]
        Final     [4.17, 2.17, 2.00, 2.00]
组件0 After 独立复核   [4.17, 2.17, 2.00, 2.00]     偏差 0.00e+00
总耗时 0.37 秒
```

**组件0 After 与组件2 逐位一致。** 这正是 ROADMAP 里 P-Verify 那一项在 Rhino
上还「待验收」的端到端复核——在这里是自动跑的，每次运行都验一遍。

---

## 验证

`test_geom.py`（21 项）不验证「管线和自己一致」，验证的是**替换掉的几何和闭式解一致**：

- 射线打盒子的距离对照手算，含从内部出发返回远面（MeshRay 语义）
- 高 H 的墙在距离 D 处的遮挡边界，对照 `D = H / tan(高度角)` 两侧各取一点
- 多边形裁剪对照手算面积，含三角形被切角
- **整个网格裁剪后面积之和 == 原多边形面积**（体积不能在体素化过程中丢失）
- **网格偏移不变性**：把体量挪 (2.37, 1.11) 米，体素化体积不变
- 柱内层号递增不重复、VoxelID 唯一
- 上海冬至正午高度角 35.3°、夏至 82.2°，对照天文值
- 同一输入跑两次结果逐位相同

`test_badinput.py`（15 项）验证的是**错的图纸必须报错，不能算出一个像模像样的错答案**：
块名漏写连字符、多段线没闭合、保护点块里没有 POINT、图纸没声明单位、缺方案体量、
缺保护点——全部 raise 且错误信息点名到具体块。

体积守恒是这里最值得看的一条：梯形 (12,0)(56,0)(44,33)(12,33) 面积 1254 m²，
乘 48 米 = 60,192 m³，体素化后**精确等于** 60,192.0 m³。Rhino 版之所以要输出
`Boolean Operation Failures` 这个指标，就是因为它的路径会丢单元。

---

## 与 Rhino 8 的数值对照（已完成）

`rhino/drive_components.py` 通过 `rhinocode` 把**真的 Rhino 组件**跑在同一个场景上——
不经过 Grasshopper 画布，直接调三个组件的模块级 `execute()`。同一台机器、同一组输入。

| 项目 | Rhino 8 组件 | 纯 Python 引擎 |
|---|---|---|
| 组件1 Output Voxels | 328 | 328 |
| 组件1 Output Columns | 41 | 41 |
| 组件1 Full Box Voxels | 264 | 264 |
| 组件1 Boundary-Clipped | 64 | 64 |
| 组件1 Voxelized Volume | 60192.000 m³ | 60192.000 m³ |
| 组件2 射线次数 | 35,568 | 35,568 |
| 组件2 迭代轮数 | 8 | 8 |
| 组件2 Kept / Removed | 185 / 143 | 185 / 143 |
| 组件2 保留率 | 59.25% | 59.25% |
| Baseline | [5.6667, 4.3333, 4.0000, 3.1667] | 同 |
| Initial | [3.8333, 0, 0, 0] | 同 |
| **Final** | **[4.1667, 2.1667, 2.0000, 2.0000]** | **同** |
| 组件0 After | [4.1667, 2.1667, 2.0000, 2.0000] | 同 |

**逐项一致，没有一处偏差。**

耗时（同机）：

| | Rhino 8 | 纯 Python |
|---|---:|---:|
| 组件1 | 107.80 s | 0.002 s |
| 组件2 | 58.65 s | 0.10 s |
| 组件0 After | — | 0.03 s |
| 合计 | **166.4 s** | **0.37 s** |

约 450 倍。组件1 的差距最大：Boolean 求交 108 秒 vs 2D 裁剪 2 毫秒。

### 对照过程中发现的一个真实差异

第一次对照时组件1 的 Full/Clipped 计数对不上：Rhino 报 264/64，我报 224/104
（总数都是 328，体积都精确相等）。原因是**组件1 把末排格子夹到包围盒**，
再判断是否完整；我只在 Z 方向夹了，XY 没夹。几何和体积不受影响，只有这个诊断
计数会差。已按组件1 的做法修正。

这正是对照的价值——差异出在我这边，而且只有跑一次真组件才会暴露。

### 对照的前提与限制

- `rhinocode` 环境下 `RhinoDoc.ActiveDoc` 和 `scriptcontext.doc` 都是 `None`，
  组件回退到 tolerance 0.001、units "Unknown"。真实 GH 会话是毫米文档、
  tolerance 0.01。**Boolean 行为在不同容差下可能不同**，这一点没有覆盖。
- 走的是 `src/rhino8/*.py`，**不是 `dist/ghuser/*.ghuser`**。打包组件的装载验收
  仍然要在 Grasshopper 里做一次，本次对照不能替代。
- 只对了一个场景。

## 性能：和预期相反

`bench.py` 拿仓库原版 `build_event_voxel_paths` 和加了 numpy 包围盒粗筛的版本对跑，
两者输出逐位一致：

| 场景 | 体素 | 标称射线测试 | 原版 | 加粗筛 | 倍数 |
|---|---:|---:|---:|---:|---:|
| 6m/10min | 328 | 47,232 | 0.07s | 0.01s | 10.4x |
| 4m/10min | 1,080 | 155,520 | 0.21s | 0.01s | 17.4x |
| 3m/5min | 2,352 | 677,376 | 0.91s | 0.04s | 21.3x |
| 2m/5min | 7,968 | 2,294,784 | 3.18s | 0.11s | 27.7x |
| 2m/2min | 7,968 | 5,736,960 | 7.76s | 0.33s | 23.3x |

- 纯 Python：**739,000 次/秒**
- 加粗筛：**17,200,000 次/秒**
- 组件里 2000 万次的安全上限：纯 Python 27 秒，加粗筛约 1 秒

对照 Rhino 实机验收记录的 165,560 次 MeshRay / 6.223 秒 = **26,605 次/秒**。

也就是说纯 Python 的 2.5D 射线测试比 RhinoCommon 的 MeshRay 快了约 28 倍。原因不
神秘：MeshRay 打的是三角网格，要走 BVH 和逐三角形求交，还要跨 Python/.NET 边界；
拉伸体的射线测试是十几次浮点运算。

**这一条推翻了我此前「必须先向量化否则要跑几十分钟」的判断。** numpy 粗筛是锦上添花，
不是先决条件。（跨机器对比，只能看数量级，不能当精确基准。）

端到端在 3 米体素 / 5 分钟步长下：2352 体素、19 轮迭代、总耗时 1.9 秒。

---

## 边界

**几何限制是真的。** 2.5D 只能表达竖直拉伸体：悬挑、斜屋面、非垂直表皮做不了。
退台和裙房+塔楼可以拆成多个块绕过去，曲面造型不行。

**同一格子内多个方案体量重叠时没有做实体并集**，当前取面积最大的那个并告警。
真做的话需要多边形并集（shapely 或自己实现 Greiner–Hormann）。

**块的旋转和非等比缩放没有测过。** `virtual_entities()` 会应用变换，但没有覆盖到。

**结果依赖体素分辨率**：同一场景 6m/4m/3m 体素的保留率分别是 57.3% / 65.2% / 67.1%。
贪心启发式本来就不声称全局最优，但这意味着报数时必须连体素尺寸一起报。

**仓库原有的验收基线复现不了。** 记录的 560 体素、`FinalSunHours = [2.85, 2.45, 2.00]`、
保留率 86.22% 只记了输出没记输入——设计体量形状、保护点坐标、周边建筑、北向、
日期时段都不在仓库里。那组数字现在无法被任何人复现，包括 Rhino 版自己。
ROADMAP 里「R7 用同一组输入验证」这一步，目前缺少「同一组输入」。

本 spike 的 `scene/reference.dxf` + `rhino/drive_components.py` 补上了这个缺口：
一个脚本生成、可复现、两个引擎都能跑的场景。

---

## 文件

```
src/headless/cadsolar/geom.py        2.5D 棱柱、射线求交、多边形裁剪 —— 替代 Rhino 内核的全部
src/headless/cadsolar/naming.py      块名约定解析
src/headless/cadsolar/dxfio.py       DXF 读写（读场景、写回切削结果、导 OBJ）
src/headless/cadsolar/scene_spec.py  JSON 场景描述 → Scene（无需 CAD）
src/headless/cadsolar/cities.py      城市坐标与分析日预设
src/headless/cadsolar/kernel.py      从 src/rhino8/ 抽取真算法并注入几何原语
src/headless/cadsolar/pipeline.py    组件1（新写）+ 组件2、组件0（原样调用）
src/headless/cadsolar/cli.py         命令行接口
src/headless/make_reference_scene.py 生成参考场景
src/headless/scene/reference.dxf     参考场景（两个引擎的共同基准）
src/headless/rhino_result.json       Rhino 侧对照的原始输出
tools/crosscheck_rhino.py            经 rhinocode 驱动真组件做数值对照
tools/bench_headless.py              性能与粗筛等价性
tests/test_headless_geometry.py      几何原语对照闭式解
tests/test_headless_input.py         坏图纸必须报错
```
