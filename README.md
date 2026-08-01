# Sunlight Envelope｜日照可建空间分析

本项目提供五个既有 Grasshopper Python 脚本，用于在地块边界内生成三维采样点，并计算每个采样点的累计或最长连续直射日照时间。另有一套由组件0、组件1和组件2组成的 Solar Voxel Pipeline，用于双场景日照分析、设计体量体素化和日照约束切削；它不修改原有五个脚本。

管线组件有 Rhino 8 和 Rhino 7 两套实现，并已打包为 Grasshopper User
Object，端口预置，拖出来即可接线。

## 我该从哪里开始

| 你的情况 | 看这里 |
|---|---|
| 拿到 `.ghuser`，想装上用 | [安装与使用 Grasshopper 组件](docs/GHUSER_INSTALL.md) |
| 想用五个日照采样脚本 | [快速开始](docs/QUICK_START.md) |
| 要在 Rhino 7 上手工粘贴管线脚本 | [Rhino 7 组件0、1、2使用指南](docs/RHINO7_PIPELINE_GUIDE.md) |
| 要改代码或重新构建组件 | [构建 Grasshopper User Object](docs/GHUSER_BUILD.md)、[tools/README](tools/README.md) |
| 想知道最近改了什么 | [更新日志](CHANGELOG.md) |

其余文档：

- [上海设计阶段参数](docs/SHANGHAI_DESIGN_PROFILE.md)
- [Rhino / Grasshopper 上机验收清单](docs/ON_MACHINE_TESTS.md)
- [示例文件说明](examples/README.md)
- [Solar Constraint Solver MVP](docs/SOLAR_CONSTRAINT_SOLVER_MVP.md)
- [Solar Constraint Solver MVP 验收清单](docs/SOLAR_CONSTRAINT_SOLVER_TESTS.md)
- [Solar Voxel Pipeline MVP](docs/SOLAR_VOXEL_PIPELINE_MVP.md)
- [开发路线图](docs/ROADMAP.md)

## 项目结构

```text
SunlightEnvelope_Rhino8/
├── README.md
├── src/
│   ├── rhino8/        Rhino 8 Python 3 脚本
│   ├── rhino7/        Rhino 7 IronPython 2.7 脚本
│   └── ghuser/        User Object 源 bundle（生成物，勿手改）
├── dist/ghuser/       构建好的 .ghuser，可直接下载安装
├── tools/             bundle 生成与校验脚本
├── docs/              使用、上海参数与验收文档
└── examples/          Rhino 8 测试模型
```

## 版本文件

| Rhino 版本 | Python 环境 | 脚本文件 |
|---|---|---|
| Rhino 8 | Python 3 Script Component / Script-Mode | [`SunlightEnvelope_Rhino8_GhPython.py`](src/rhino8/SunlightEnvelope_Rhino8_GhPython.py) |
| Rhino 8 | Python 3 Script Component / SDK-Mode / 累计日照 | [`SunlightEnvelope_Rhino8_SDK.py`](src/rhino8/SunlightEnvelope_Rhino8_SDK.py) |
| Rhino 8 | Python 3 Script Component / SDK-Mode / 最长连续日照 | [`SunlightEnvelope_Rhino8_Continuous_SDK.py`](src/rhino8/SunlightEnvelope_Rhino8_Continuous_SDK.py) |
| Rhino 7 | GhPython / IronPython 2.7 / 累计日照 | [`SunlightEnvelope_Rhino7_GhPython.py`](src/rhino7/SunlightEnvelope_Rhino7_GhPython.py) |
| Rhino 7 | GhPython / IronPython 2.7 / 最长连续日照 | [`SunlightEnvelope_Rhino7_Continuous_GhPython.py`](src/rhino7/SunlightEnvelope_Rhino7_Continuous_GhPython.py) |

新增独立 MVP：

| Rhino 版本 | Python 环境 | 脚本文件 |
|---|---|---|
| Rhino 8 | Python 3 Script Component / SDK-Mode / 双场景约束分析 | [`SolarConstraintSolver_Rhino8_SDK.py`](src/rhino8/SolarConstraintSolver_Rhino8_SDK.py) |
| Rhino 8 | Python 3 Script Component / SDK-Mode / 柱状体素生成 | [`SolarDesignVoxelizer_Rhino8_SDK.py`](src/rhino8/SolarDesignVoxelizer_Rhino8_SDK.py) |
| Rhino 8 | Python 3 Script Component / SDK-Mode / 体素日照优化 | [`SolarVoxelOptimizer_Rhino8_SDK.py`](src/rhino8/SolarVoxelOptimizer_Rhino8_SDK.py) |
| Rhino 7 | GhPython / IronPython 2.7 / 双场景约束分析 | [`SolarConstraintSolver_Rhino7_GhPython.py`](src/rhino7/SolarConstraintSolver_Rhino7_GhPython.py) |
| Rhino 7 | GhPython / IronPython 2.7 / 柱状体素生成 | [`SolarDesignVoxelizer_Rhino7_GhPython.py`](src/rhino7/SolarDesignVoxelizer_Rhino7_GhPython.py) |
| Rhino 7 | GhPython / IronPython 2.7 / 体素日照优化 | [`SolarVoxelOptimizer_Rhino7_GhPython.py`](src/rhino7/SolarVoxelOptimizer_Rhino7_GhPython.py) |

R7 版与 R8 版共用同一套算法、编号规则和输出契约。差异集中在运行环境，
详见[R7 与 R8 的差异](#r7-与-r8-的差异)。

## 组件0、1、2命名约定

后续讨论、文档和验收统一使用以下简称：

| 简称 | 正式职责 | Rhino 8 脚本 | Rhino 7 脚本 | 主要输出 |
|---|---|---|---|---|
| **组件0** | 日照计算与前后方案验证 | [`SolarConstraintSolver_Rhino8_SDK.py`](src/rhino8/SolarConstraintSolver_Rhino8_SDK.py) | [`SolarConstraintSolver_Rhino7_GhPython.py`](src/rhino7/SolarConstraintSolver_Rhino7_GhPython.py) | `SunHours`、`ViolationData`、`ConstraintData`、`Report` |
| **组件1** | 将 `DesignVolume` 划分为可编号、可追踪的像素/体素块 | [`SolarDesignVoxelizer_Rhino8_SDK.py`](src/rhino8/SolarDesignVoxelizer_Rhino8_SDK.py) | [`SolarDesignVoxelizer_Rhino7_GhPython.py`](src/rhino7/SolarDesignVoxelizer_Rhino7_GhPython.py) | `Voxels`、编号、柱号、层号、体积和 `VoxelTree` |
| **组件2** | 对体素执行日照计算和约束切削 | [`SolarVoxelOptimizer_Rhino8_SDK.py`](src/rhino8/SolarVoxelOptimizer_Rhino8_SDK.py) | [`SolarVoxelOptimizer_Rhino7_GhPython.py`](src/rhino7/SolarVoxelOptimizer_Rhino7_GhPython.py) | `KeptVoxels`、`RemovedVoxels`、`FinalSunHours` 和优化报告 |

组件0可以在同一 Grasshopper 文件中放置两个实例：第一个分析原始
`DesignVolume`，第二个独立验证组件2输出的 `KeptVoxels`。

固定流程：

```text
组件0（原方案日照）
          │
DesignVolume → 组件1（切像素块）→ 组件2（日照 + 切削）
                                      │
                                      └→ 组件0（切削后独立验证）
```

### 几何输入接口自适应状态

这里的“接口自适应”专指：即使几何输入端没有设置 Type Hint，组件也能
将 Grasshopper Goo、Rhino `Guid`、`ObjRef` 或 RhinoObject 自动解析为
实际 Rhino 几何。它不代替 Item/List/Tree Access 设置，也不替代数值
输入校验。

| 组件 | 当前状态 | 说明 |
|---|---|---|
| 组件0 | **已实现** | `ProtectedPoints`、`DesignVolume` 和 `ContextBuildings` 可自动解析 Goo、`Guid`、`ObjRef`、RhinoObject 和 Rhino Point |
| 组件1 | **已实现** | `DesignVolume` 可自动解析 Goo、`Guid`、`ObjRef`、RhinoObject、Brep 和 Mesh |
| 组件2 | **已实现** | `ProtectedPoints`、`Voxels` 和 `ContextBuildings` 已使用相同的引用解析兜底 |

三个组件现在共用同一份 `resolve_rhino_geometry`，接法要求一致：Access
必须按文档设置，几何输入的 Type Hint 则是建议而非必需。

无法解析的 `Guid`（引用对象已删除，或 Rhino 文档不可用）会被明确报出：
`ProtectedPoints` 作为输入错误，两个几何角色作为警告。不会静默当作空输入。

上表同时适用于 R8 和 R7：R7 版从对应 R8 版逐行回移，这份解析逻辑在两个
版本中逐字一致。

### R7 与 R8 的差异

组件0、1、2各有一个 R7 版本。算法、编号规则、输出端名称和输出契约
与 R8 完全一致，差异只在运行环境：

| 项目 | Rhino 8 | Rhino 7 |
|---|---|---|
| 组件类型 | Python 3 Script Component，SDK-Mode | GhPython Component |
| 端口配置 | `RunScript` 签名自动同步输入端 | **全部输入和输出必须手工创建和重命名** |
| 入口形式 | `Script_Instance.RunScript` | 模块级 `execute(...)` 调用 |
| 计时 | `time.perf_counter()` | `time.time()` |
| 时长换算 | `timedelta.total_seconds()` 与 `timedelta / 2` | `timedelta_to_seconds()` 辅助函数 |
| SubD | 直接支持 | **安全忽略并输出警告**，需先在 Rhino 中转为 Brep 或 Mesh |
| 字典遍历顺序 | CPython 3 字典保持插入序 | 用 `collections.OrderedDict` 复刻插入序 |

最后一项影响的是结果而不只是报告。组件2的贪心搜索在 `comparison_key`
打平时保留先遇到的候选，所以候选字典的遍历顺序会决定平局时删除哪些
体素。IronPython 2.7 的字典不保证顺序，R7 版因此对该字典改用
`OrderedDict`，使其与 R8 的遍历顺序一致、结果可复现。

R7 端口数量：组件0为17个输入、4个输出；组件1为4个输入、8个输出；
组件2为20个输入、10个输出。名称区分大小写，必须与代码完全一致。
完整清单写在各脚本的文件头文档串中。

五个脚本保持相同的输入输出名称、采样方法、太阳位置算法和射线遮挡逻辑。连续版只改变 H 的时间统计方式：遮挡会中断当前时段，H 输出最长的一段连续直射日照时间。Script-Mode 版本手动设置接口，SDK-Mode 版本通过 `RunScript` 签名同步输入接口。

主要版本差异：

- R8 使用 Python 3、`time.perf_counter()` 和 Python 3 的 `timedelta` 运算。
- R8 支持 Mesh、Brep、Extrusion、Surface 和 SubD。
- R7 使用 IronPython 2.7 兼容的时间计算和 `time.time()`。
- R7 支持 Mesh、Brep、Extrusion 和 Surface；SubD 会被安全忽略，并在 I 中输出警告。

## 组件职责

Python 组件只负责：

1. 根据地块边界生成三维采样点。
2. 根据地点、日期和时间计算太阳方向。
3. 将周边体量转换为分析网格并执行射线遮挡检测。
4. 输出每个采样点对应的累计或最长连续直射日照时间。

Python 组件不负责：

1. 判断日照是否合格。
2. 应用法规或设计阈值。
3. Dispatch 分拣。
4. 生成体素。
5. 生成最终建筑或可建空间几何。

阈值判断、筛选和最终几何生成应在 Grasshopper 中完成。

## 安装与使用

### Rhino 8

#### SDK-Mode（推荐用于自动同步输入接口）

1. 打开 Rhino 8 和 Grasshopper。
2. 放置一个 **Python 3 Script Component**。
3. 双击组件打开编辑器。
4. 点击编辑器工具栏中的 **Convert To GH_ScriptInstance**。
5. 根据目标打开累计版 `src/rhino8/SunlightEnvelope_Rhino8_SDK.py`，或连续版 `src/rhino8/SunlightEnvelope_Rhino8_Continuous_SDK.py`。
6. 删除编辑器原有代码，并粘贴 SDK 文件的完整代码。
7. 保存脚本，让 `RunScript` 签名同步 15 个输入端；`Context` 应为 List Access，其余输入应为 Item Access。
8. 确认输出端依次为 `P`、`H`、`I`。如果当前 Rhino 8 小版本没有自动更新输出名称，只需首次手动创建或重命名这三个输出。
9. 组件右键关闭未使用的 **Standard Output/Error Parameter**，移除特殊的 `out` 输出端。
10. 将 `Run` 设为 `False`，连接输入后再切换为 `True`。

#### Script-Mode（手动设置接口）

1. 打开 Rhino 8 和 Grasshopper。
2. 放置一个 **Python 3 Script Component**。
3. 确认组件处于 **Script-Mode**。
4. 创建并重命名输入、输出端口。
5. 按下文表格设置 Access 和 Type Hint。
6. 打开 `src/rhino8/SunlightEnvelope_Rhino8_GhPython.py`。
7. 将完整代码复制到 Python 3 Script Component。
8. 将 `Run` 设为 `False`，连接输入后再切换为 `True`。

### Rhino 7

1. 打开 Rhino 7 和 Grasshopper。
2. 放置一个 **GhPython Component**。
3. 创建并重命名输入、输出端口。
4. 按下文表格设置 Access 和 Type Hint。
5. 根据目标打开累计版 `src/rhino7/SunlightEnvelope_Rhino7_GhPython.py`，或连续版 `src/rhino7/SunlightEnvelope_Rhino7_Continuous_GhPython.py`。
6. 将完整代码复制到 GhPython 编辑器。
7. 将 `Run` 设为 `False`，连接输入后再切换为 `True`。

输入、输出名称区分大小写，必须与代码完全一致。

## 输入端口

| 名称 | Access | 建议 Type Hint | 说明 |
|---|---|---|---|
| `Boundary` | Item | Curve | 闭合、平面且近似平行于 World XY 的地块边界 |
| `Context` | List | GeometryBase | 周边遮挡几何；允许空列表 |
| `North` | Item | Vector3d | 项目北向，水平 XY 分量不能为零 |
| `Latitude` | Item | float/double | 纬度，范围 -90～90° |
| `Longitude` | Item | float/double | 经度，东经为正、西经为负 |
| `TimeZone` | Item | float/double | UTC 时区偏移，例如中国为 8 |
| `Month` | Item | int | 月份 |
| `Day` | Item | int | 日期 |
| `StartHour` | Item | float/double | 当地时间起点，范围 0～24 |
| `EndHour` | Item | float/double | 当地时间终点，必须大于 StartHour |
| `TimeStep` | Item | float/double | 时间步长，单位为分钟 |
| `GridSize` | Item | float/double | XY 平面采样间距，使用 Rhino 模型单位 |
| `HeightStep` | Item | float/double | Z 方向采样层高，使用 Rhino 模型单位 |
| `MaxHeight` | Item | float/double | 最大分析高度，使用 Rhino 模型单位 |
| `Run` | Item | bool | `True` 开始计算，建议默认值为 `False` |

### Boundary 要求

`Boundary` 必须满足：

- Rhino Curve；
- 有效；
- 闭合；
- 平面；
- 平面法向近似平行于 World Z。

脚本使用世界 XY 网格生成采样点，不支持倾斜地块平面。

### Context 要求

`Context` 必须使用 **List Access**，建议 Type Hint 为 **GeometryBase**。

支持类型：

- Mesh；
- Brep；
- Extrusion；
- Surface；
- SubD，仅 R8 直接支持。

所有有效 Context 会被转换并合并为分析 Mesh。

如果 Context 为空，或所有 Context 都无法转换，脚本会将所有采样点视为无遮挡，并在 I 中输出警告。

## 输出端口

创建以下三个输出：

| 名称 | 数据结构 | 说明 |
|---|---|---|
| `P` | DataTree | 三维采样点，每个高度层一个分支 |
| `H` | DataTree | 累计版输出累计小时数；连续版输出最长连续小时数 |
| `I` | List | 状态、统计、警告和错误信息 |

### 累计版与连续版

- `src/rhino8/SunlightEnvelope_Rhino8_SDK.py`：H 为分析时段内所有无遮挡时间步的累计值。
- `src/rhino8/SunlightEnvelope_Rhino8_Continuous_SDK.py`：H 为最长一段连续无遮挡时间；任何遮挡时间步或太阳样本时间缺口都会中断当前连续段。
- `src/rhino7/SunlightEnvelope_Rhino7_GhPython.py` 与 `src/rhino7/SunlightEnvelope_Rhino7_Continuous_GhPython.py` 分别提供相同两种统计方式的 IronPython 2.7 版本；R7 接口需要手动建立。
- 所有版本都不在 Python 中判断是否合格。阈值、Dispatch、体素和最终几何仍由 Grasshopper 负责。
- 连续结果的时间精度由 `TimeStep` 决定；需要分钟级判断时应使用较小的时间步长。

### P/H 对应关系

P 和 H 保持完全一致的路径和项目顺序：

```text
P{n}[i] ↔ H{n}[i]
```

例如：

```text
P
{0}: 第 0 层采样点
{1}: 第 1 层采样点
{2}: 第 2 层采样点

H
{0}: 第 0 层采样点对应的日照小时
{1}: 第 1 层采样点对应的日照小时
{2}: 第 2 层采样点对应的日照小时
```

脚本会检查 P/H 的层数和每层项目数。如果内部结构不一致，将停止输出并在 I 中报告运行错误，不会静默截断数据。

## 采样规则

### 平面采样

采样点位于 `GridSize × GridSize` 网格单元的中心，而不是网格交点。

对于一个 10 m × 10 m 的矩形边界：

```text
GridSize = 2 m
```

每层生成：

```text
5 × 5 = 25 个采样点
```

### 高度采样

第一个采样层位于：

```text
HeightStep / 2
```

例如：

```text
HeightStep = 0.5 m
MaxHeight  = 5.0 m
```

输出 10 层，中心高度为：

```text
0.25
0.75
1.25
1.75
2.25
2.75
3.25
3.75
4.25
4.75 m
```

对应路径为 `{0}` 至 `{9}`。

## 时间和太阳方向

太阳位置根据以下输入计算：

- Latitude；
- Longitude；
- TimeZone；
- Month；
- Day；
- 当地时间。

经度规则：

```text
东经为正
西经为负
```

北向和方位角规则：

```text
0°   = North
90°  = East
180° = South
270° = West
```

每个时间区间使用中点进行太阳位置计算，并使用该区间的实际持续时间作为积分权重。

例如：

```text
StartHour = 8
EndHour   = 10
TimeStep  = 60 分钟
```

计算时刻为：

```text
08:30，权重 1 小时
09:30，权重 1 小时
```

如果最后一个区间不足一个完整 TimeStep，脚本会自动使用实际剩余时长。

## 无 Context 快速路径

当没有有效 Context Mesh 时，不需要为每个采样点重复遍历所有太阳时刻。

脚本会：

1. 累计版计算无遮挡总时长；连续版计算最长连续的太阳样本时段；
2. 将相同结果写入每个采样点的 H；
3. 继续保持 P/H 的 DataTree 结构一致；
4. 每隔固定数量的项目检查 ESC。

此优化只减少无 Context 时的重复计算，不改变任何结果。

I 中会显示：

```text
Sun-Hour Evaluation: Unobstructed Fast Path
```

有有效 Context 时显示：

```text
Sun-Hour Evaluation: MeshRay
```

## 最小测试示例

### 测试 1：无遮挡

```text
Boundary    = 10 m × 10 m 矩形
Context     = 空列表
North       = (0, 1, 0)
Latitude    = 39.9042
Longitude   = 116.4074
TimeZone    = 8
Month       = 6
Day         = 21
StartHour   = 9
EndHour     = 15
TimeStep    = 60
GridSize    = 2
HeightStep  = 1
MaxHeight   = 3
Run         = True
```

预期：

- 3 个分支；
- 每个分支 25 个点；
- P/H 总数均为 75；
- 所有点获得相同 H；
- I 显示 `Unobstructed Fast Path`。

### 测试 2：盒体遮挡

1. 创建一个矩形 Boundary。
2. 在 Boundary 南侧放置一个盒状 Brep 或 Mesh。
3. 使用冬季日期，例如 12 月 21 日。
4. 将盒体连接到 Context。

预期：

- Context 后方低层采样点的 H 减少；
- 远离盒体的采样点 H 较大；
- 删除 Context 后，同层采样点恢复为相同 H；
- I 显示 `Sun-Hour Evaluation: MeshRay`。

### 测试 3：分层

```text
Boundary   = 4 m × 4 m 矩形
GridSize   = 1 m
HeightStep = 0.5 m
MaxHeight  = 5 m
```

预期：

- P 和 H 均包含 `{0}` 至 `{9}`；
- 每个分支 16 项；
- 总数均为 160；
- 任意 `P{n}[i]` 都对应 `H{n}[i]`。

## I 信息说明

建议每次计算后将 I 连接到 Panel。

常见状态：

```text
Status: Waiting
Status: Completed
Status: Cancelled
Status: Input Error
Status: Runtime Error
```

I 同时包含：

- 计算时间；
- 平面采样点数量；
- 输出层数；
- 输出采样点总数；
- 时间区间数量；
- 太阳位于地平线以上的区间数量；
- Context Mesh 顶点数和面数；
- 日照小时最小值、最大值和平均值；
- 被忽略的 Context 类型；
- MeshRay 异常数量。

如果 MeshRay 发生异常，对应射线会被保守地视为被遮挡，并在 I 中输出警告。

## 性能和安全限制

脚本默认最大采样点数量：

```text
2,000,000
```

预估或实际采样点超过限制时，计算会停止。

采样点数量近似为：

```text
ceil(边界宽度 / GridSize)
×
ceil(边界深度 / GridSize)
×
ceil(MaxHeight / HeightStep)
```

有 Context 时，最大射线数量近似为：

```text
采样点数量 × 地平线以上的时间区间数量
```

提高性能的优先顺序：

1. 增大 GridSize；
2. 增大 HeightStep；
3. 减少 MaxHeight；
4. 增大 TimeStep；
5. 删除不参与遮挡的 Context；
6. 降低不必要的 Context Mesh 面数。

不建议直接提高 2,000,000 点限制。大量 Point3d、小时值、DataTree 项和 MeshRay 调用可能造成长时间计算和高内存占用。

## 取消计算

长时间计算时可以按 ESC。

脚本会返回已经完成的部分结果，并确保：

```text
P 和 H 的路径一致
P 和 H 的每个分支项目数一致
P{n}[i] 与 H{n}[i] 一一对应
```

I 会显示：

```text
Status: Cancelled
```

## 常见问题

### Boundary 报错

检查：

- 是否为 Curve；
- 是否闭合；
- 是否平面；
- 是否近似平行于 World XY；
- Rhino 模型单位是否正确。

### 没有生成采样点

可能原因：

- GridSize 相对 Boundary 过大；
- Boundary 形状过窄；
- Boundary 或模型单位错误；
- Boundary 不符合水平平面要求。

### 输入了建筑，但所有点日照相同

检查 I：

- `Source Mesh Parts` 是否大于 0；
- `Joined Mesh Faces` 是否大于 0；
- 是否显示 `Unobstructed Fast Path`；
- 是否有 Context 被忽略或转换失败警告。

同时确认 Context 使用：

```text
List Access
GeometryBase Type Hint
```

### 计算过慢

先将 `Run` 设为 `False`，然后：

1. 增大 GridSize；
2. 增大 HeightStep；
3. 增大 TimeStep；
4. 减少 Context 数量和网格面数；
5. 使用较小测试区域验证输入。

### R7 的 SubD 没有参与遮挡

R7 版本会安全忽略 SubD。请先在 Rhino 中将 SubD 转换为 Mesh 或 Brep，再连接到 Context。

## 推荐的 Grasshopper 后续流程

Python 输出原始 P 和 H 后，可以在 Grasshopper 中继续：

1. 使用比较组件对 H 应用项目日照阈值；
2. 使用 Dispatch 分离合格和不合格点；
3. 根据 P 创建体素或其他设计几何；
4. 合并或分析最终可建空间。

这些步骤应保持在 Grasshopper 中，不应加入本 Python 脚本。

## 当前验证状态

五个脚本已经完成：

- Python 语法检查；
- R7 IronPython 2.7 语法兼容检查；
- 时间区间测试；
- 太阳位置合理性测试；
- 分层采样测试；
- P/H DataTree 结构模拟测试；
- ESC 部分结果测试；
- ActiveDoc 空值测试；
- MeshRay 错误计数测试；
- 无 Context 快速路径等价性测试。

已在 Rhino 8 中完成人工冒烟测试：

- SDK 输入接口同步与输出端手动配置；
- Curve Boundary、多个 Brep Context 和 MeshRay 遮挡；
- P/H DataTree 及 I Panel 输出。

尚未完成或仍需扩大覆盖：

- Rhino 7 实机验证；
- R8 Extrusion、Surface 和 SubD 的独立网格化验证；
- ESC 实际按键交互；
- 不同 Context 面数下的性能测试。

首次上机建议先运行本文的三个最小测试模型，再用于真实项目。

### R7 组件0、1、2的验证状态

三个 R7 管线组件由对应 R8 版本逐行回移，已完成：

- IronPython 2.7 语法兼容性检查（AST 白名单扫描，无 Python 3 专有构造）；
- 与 R8 原件的逐行差异复核，确认改动仅限运行环境适配；
- 字典遍历顺序审计，确认组件2的贪心平局路径已恢复确定性。

**尚未完成实机验证。** 首次在 Rhino 7 上使用前，应当先用与 R8 相同的
输入跑一遍，并核对 `FinalSunHours` 与 R8 已验收结果一致，再用于真实
项目。R8 侧的参照基线记录在[开发路线图](docs/ROADMAP.md)。

## 开源许可

本项目采用 [MIT License](LICENSE) 开源。你可以使用、复制、修改、合并、发布和分发本项目，但须保留原始版权声明和许可声明。

Copyright © 2026 leoyang1984
