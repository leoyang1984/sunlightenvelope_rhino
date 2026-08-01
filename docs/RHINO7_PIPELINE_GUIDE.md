# Rhino 7 组件0、1、2使用指南

面向没有 Rhino 8 的协作方。三个管线组件的 IronPython 2.7 版本与 R8 版
共用同一套算法、编号规则和输出契约，差异只在运行环境。

R8 版差异对照见 [README 的「R7 与 R8 的差异」](../README.md#r7-与-r8-的差异)。

## 1. 文件对应

| 组件 | 职责 | R7 文件 | 输入 | 输出 |
|---|---|---|---:|---:|
| 组件0 | 日照计算与前后方案验证 | `src/rhino7/SolarConstraintSolver_Rhino7_GhPython.py` | 17 | 4 |
| 组件1 | 体量切分为可编号体素块 | `src/rhino7/SolarDesignVoxelizer_Rhino7_GhPython.py` | 4 | 8 |
| 组件2 | 体素日照计算与约束切削 | `src/rhino7/SolarVoxelOptimizer_Rhino7_GhPython.py` | 20 | 10 |

固定流程与 R8 一致：

```text
组件0（原方案日照）
          │
DesignVolume → 组件1（切像素块）→ 组件2（日照 + 切削）
                                      │
                                      └→ 组件0（切削后独立验证）
```

组件0在同一个 Grasshopper 文件中放置两个实例，不是两个不同脚本。

## 2. 建立组件的顺序

> 本节描述的是粘贴脚本的接法。组件1另有 `.ghuser` 打包版本,端口是预置
> 的,不需要手工创建;见[构建 Grasshopper User Object](GHUSER_BUILD.md)。
> 组件0和组件2目前仍需按本节手工建端口。


R7 没有 SDK-Mode，端口不会由方法签名自动同步。**必须先建好全部端口，
再粘贴代码。** 顺序反了组件会因为找不到输入名直接报运行时错误，而且这
个错误信息不会告诉你缺的是哪一个端口。

1. 放置一个 **GhPython Component**（不是 Rhino 8 的 Python 3 组件）。
2. 缩放组件，用 ZUI 的 `+` / `-` 把输入端数量调到目标数量。
3. 逐个右键重命名输入端，并设置 Access 与 Type Hint（见下文表格）。
4. 同样方式建立并重命名输出端，顺序必须与表格一致。
5. 打开编辑器，删除原有代码，粘贴完整 `.py` 文件内容。
6. `Run` 先接 `False`，把其余输入接完后再切换为 `True`。

名称区分大小写，必须与代码完全一致。`SunHours` 和 `Sunhours` 不是同一
个端口。

## 3. 端口配置

**Access 必须按表设置，Type Hint 是建议而非必需。** 三个组件的几何输入
都能自动解析 Grasshopper Goo、Rhino 文档 `Guid`、`ObjRef`、RhinoObject
和 Rhino `Point`，所以直接引用 Rhino 对象时，设不设 Type Hint 结果一致。

Access 设错则不行。`List` 误设为 `Item` 是最常见的接线错误，组件只会
拿到第一项，报告里的数量会明显偏小。

### 组件1 SolarDesignVoxelizer

| 输入 | Access | Type Hint |
|---|---|---|
| DesignVolume | List | GeometryBase |
| VoxelSizeXY | Item | float/double |
| VoxelSizeZ | Item | float/double |
| Run | Item | bool |

输出顺序：

```text
Voxels
VoxelIDs
ColumnIDs
LayerIDs
VoxelCenters
VoxelVolumes
VoxelTree
Report
```

### 组件0 SolarConstraintSolver

| 输入 | Access | Type Hint |
|---|---|---|
| ProtectedPoints | List | Point3d |
| DesignVolume | List | GeometryBase |
| ContextBuildings | List | GeometryBase |
| North | Item | Vector3d |
| Latitude | Item | float/double |
| Longitude | Item | float/double |
| TimeZone | Item | float/double |
| Year | Item | int |
| Month | Item | int |
| Day | Item | int |
| StartHour | Item | float/double |
| EndHour | Item | float/double |
| TimeStep | Item | float/double |
| MinimumContinuousMinutes | Item | float/double |
| RequiredSunHours | Item | float/double |
| ImpactTolerance | Item | float/double |
| Run | Item | bool |

输出顺序：

```text
SunHours
ViolationData
ConstraintData
Report
```

### 组件2 SolarVoxelOptimizer

| 输入 | Access | Type Hint |
|---|---|---|
| ProtectedPoints | List | Point3d |
| Voxels | List | GeometryBase |
| VoxelIDs | List | int |
| ColumnIDs | List | int |
| LayerIDs | List | int |
| ContextBuildings | List | GeometryBase |
| North | Item | Vector3d |
| Latitude | Item | float/double |
| Longitude | Item | float/double |
| TimeZone | Item | float/double |
| Year | Item | int |
| Month | Item | int |
| Day | Item | int |
| StartHour | Item | float/double |
| EndHour | Item | float/double |
| TimeStep | Item | float/double |
| MinimumContinuousMinutes | Item | float/double |
| RequiredSunHours | Item | float/double |
| MaxIterations | Item | int |
| Run | Item | bool |

输出顺序：

```text
KeptVoxels
RemovedVoxels
OptimizedColumns
KeepMask
InitialSunHours
FinalSunHours
VoxelImpactHours
EventVoxelPaths
IterationData
Report
```

## 4. 连接要点

### 组件1 → 组件2

`VoxelIDs`、`ColumnIDs`、`LayerIDs` 必须**直接**来自组件1的同名输出。

```text
组件1.Voxels     → 组件2.Voxels
组件1.VoxelIDs   → 组件2.VoxelIDs
组件1.ColumnIDs  → 组件2.ColumnIDs
组件1.LayerIDs   → 组件2.LayerIDs
```

中间不要插入 Sort、Cull、Dispatch 或任何改变项目顺序的组件。四个列表
按同一个体素索引对齐，任何一个被重排或过滤，索引契约就会失效，组件2
的切削结果不再对应实际几何。

需要筛选体素时，应当在组件2输出之后做，不是在输入之前。

### 组件2 → 组件0 After

把组件2的 `KeptVoxels` 接到第二个组件0实例的 `DesignVolume`。两个组件0
实例的以下输入必须**完全一致**，否则前后对比没有意义：

```text
ProtectedPoints
ContextBuildings
North / Latitude / Longitude / TimeZone
Year / Month / Day
StartHour / EndHour / TimeStep
MinimumContinuousMinutes
RequiredSunHours
```

建议用同一组 Number Slider 或 Panel 同时喂给两个实例，不要各接各的。

## 5. 注意事项

### SubD 会被忽略

R7 管线不处理 SubD，遇到时安全跳过并在 `Report` 中输出警告。这与 R7
日照脚本的既有约定一致。需要 SubD 参与计算时，先在 Rhino 中转为 Brep
或闭合 Mesh 再连接。

如果发现结果比预期少了体量，先查 `Report` 里有没有 SubD 警告。

### 失效的对象引用会被报出来

从 Rhino 文档引用几何后又把对象删掉，组件不会静默当作空输入，而是明确
报出：`ProtectedPoints` 作为输入错误，`DesignVolume` 和
`ContextBuildings` 作为警告。看到 `could not be resolved` 字样时，检查
Rhino 里对应的对象是否还在。

### 画布组件不会自动更新

Grasshopper 画布中的 Python 组件保存的是代码副本，不随仓库文件更新。
换了新版脚本后必须打开编辑器**完整替换**内容。端口名称正确不代表内部
代码是最新版本——这一点在 R7 上尤其容易踩，因为端口是手工建的，看起来
一直没变。

### DesignVolume 必须是闭合实体

组件1要求一个或多个有效闭合实体。开放曲面、非流形体或自相交实体会被
判为输入错误。先在 Rhino 中用 `SelClosedSrf` 或 `ShowEdges` 确认。

### 性能与安全上限

R7 的 IronPython 直连 .NET，射线求交性能不比 R8 差，但两边都有硬上限：

```text
组件1  候选体素      250,000
组件2  保护点        10,000
组件2  体素          10,000
组件2  射线×体素测试 20,000,000
```

首轮先用大体素、大 `TimeStep` 跑通，再逐步加密：

```text
VoxelSizeXY = 3000 mm
VoxelSizeZ  = 3000 mm
TimeStep    = 60
```

参数调整前先把 `Run` 设为 `False`。

### 长时间计算可以按 ESC

三个组件都会周期性检查 Escape。组件1和组件2被中断时**丢弃**部分结果并
在 `Report` 中标记 `Status: Cancelled`，不会输出半套不同步的数据。重新
运行即可。

### 单位是模型单位

`VoxelSizeXY`、`VoxelSizeZ` 使用 Rhino 模型单位。毫米文件里 `3000` 是
3米，写成 `3` 表示 3 毫米，会直接撞上候选体素安全上限。

## 6. 与 R8 结果对齐

R7 版由 R8 版逐行回移，同一组输入应当得到同一组结果。首次使用建议先做
一次对齐核对。

R8 侧已验收的参照基线：

```text
组件1  560个候选体素，38个边界裁切体素，Boolean失败0
组件2  4轮移除104个体素，保留率 86.22%
       FinalSunHours = [2.85, 2.45, 2.00]
```

出现偏差时的排查顺序：

1. `Report` 里有没有 SubD 或 Boolean 失败警告；
2. 端口 Access 是否设错（`List` 误设为 `Item` 最常见）；
3. 体素编号是否直接来自组件1，中间有没有被重排；
4. 两个组件0实例的太阳参数是否完全一致；
5. 模型绝对公差是否与 R8 侧一致。

### 关于确定性

组件2的贪心搜索在候选评分打平时保留先遇到的候选。R8 依靠 CPython 3
字典的插入序保证可复现，IronPython 2.7 的字典不保证顺序，因此 R7 版对
顺序可观测的字典改用 `collections.OrderedDict` 复刻 R8 的遍历顺序。

这意味着 R7 的结果既是可复现的，也与 R8 一致。若两边出现差异，应当先
按上面五步排查输入，而不是归因于运行环境。

## 7. 当前验证状态

三个 R7 组件已完成：

- IronPython 2.7 语法兼容性扫描；
- 与 R8 原件的逐行差异复核；
- 字典遍历顺序确定性审计。

**尚未完成 Rhino 7 实机验收。** 首次用于真实项目前，应先按第6节做一次
与 R8 的结果对齐核对。验收判据和记录格式见
[开发路线图](ROADMAP.md) 与 [上机验收清单](ON_MACHINE_TESTS.md)。
