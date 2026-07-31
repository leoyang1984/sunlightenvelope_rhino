# Solar Voxel Pipeline MVP

## 1. 组件定位

本项目固定使用以下简称：

- 组件0：Solar Constraint Solver，负责日照计算和前后验证；
- 组件1：Solar Design Voxelizer，负责切像素/体素块；
- 组件2：Solar Voxel Optimizer，负责日照计算和体素切削。

体素优化流程由三个职责分离的组件组成：

```text
原始 DesignVolume
├─→ 组件0 Before：原方案日照分析
└─→ 组件1：生成柱状体素
       ↓
    组件2：计算并删除不利体素
       ↓
    组件0 After：独立复核
```

现有 `SolarConstraintSolver_Rhino8_SDK.py` 不做切削。它可以在画布中放置两个副本，分别验证优化前和优化后的几何。

## 2. Solar Design Voxelizer

文件：

`src/rhino8/SolarDesignVoxelizer_Rhino8_SDK.py`

### 输入

| 名称 | Access | 类型 | 说明 |
|---|---|---|---|
| DesignVolume | List | GeometryBase | 与现有 Solver 共用的闭合设计实体 |
| VoxelSizeXY | Item | float | 平面网格尺寸，模型单位 |
| VoxelSizeZ | Item | float | 竖向层高，模型单位 |
| Run | Item | bool | True 时生成 |

### 输出

| 名称 | 数据结构 | 说明 |
|---|---|---|
| Voxels | List | 按统一索引排列的完整 Box 或边界裁切实体 |
| VoxelIDs | List[int] | 唯一体素编号 |
| ColumnIDs | List[int] | 每个体素所属柱编号 |
| LayerIDs | List[int] | World Z 层编号 |
| VoxelCenters | List[Point3d] | 体素中心 |
| VoxelVolumes | List[float] | 体素真实实体体积 |
| VoxelTree | DataTree | `{ColumnID}`，分支内从下到上 |
| Report | List[str] | 状态、数量、体积和警告 |

所有平面列表保持严格相同的项目顺序：

```text
Voxels[i]
↔ VoxelIDs[i]
↔ ColumnIDs[i]
↔ LayerIDs[i]
↔ VoxelCenters[i]
↔ VoxelVolumes[i]
```

### MVP几何规则

- World Z 为竖直方向。
- 输入必须是有效闭合实体。
- 网格从所有输入的联合包围盒最小点开始。
- 完整位于输入内部的单元保留为规则 Box。
- 边界单元通过 Brep Boolean Intersection 裁切到 DesignVolume 内部，
  不再因为只有部分进入边界而被整格删除。
- 每一个 World Z 层独立判断；较低层为空不会连带删除上方有效层。
- ColumnID 仍按相同 World XY 网格位置分组，LayerID 保留全局层号；
  输入几何本身存在竖向空隙时，层号允许跳跃。
- 第一版优先用于 Box、直墙和规则退台；复杂或容差不良的 Brep 应检查
  Report 中的 Boolean Operation Failures。

毫米模型建议从以下参数开始：

```text
VoxelSizeXY = 2000
VoxelSizeZ  = 2000
```

## 3. Solar Voxel Optimizer

文件：

`src/rhino8/SolarVoxelOptimizer_Rhino8_SDK.py`

### 输入

| 名称 | Access | 类型 |
|---|---|---|
| ProtectedPoints | List | Point3d |
| Voxels | List | GeometryBase |
| VoxelIDs | List | int |
| ColumnIDs | List | int |
| LayerIDs | List | int |
| ContextBuildings | List | GeometryBase |
| North | Item | Vector3d |
| Latitude、Longitude、TimeZone | Item | float |
| Year、Month、Day | Item | int |
| StartHour、EndHour、TimeStep | Item | float |
| MinimumContinuousMinutes | Item | float |
| RequiredSunHours | Item | float |
| MaxIterations | Item | int |
| Run | Item | bool |

Voxelizer 的前四个平面输出直接连接 Optimizer：

```text
Voxels    → Voxels
VoxelIDs  → VoxelIDs
ColumnIDs → ColumnIDs
LayerIDs  → LayerIDs
```

ProtectedPoints、ContextBuildings 和全部太阳参数与现有 Solver 共用。

第一轮建议：

```text
TimeStep = 3
MinimumContinuousMinutes = 3
RequiredSunHours = 2
MaxIterations = 200
```

### 输出

| 名称 | 数据结构 | 说明 |
|---|---|---|
| KeptVoxels | List[GeometryBase] | 优化后保留的原始体素 |
| RemovedVoxels | List[GeometryBase] | 被删除的原始体素 |
| OptimizedColumns | List[Mesh] | 每个 XY 柱保留体素的组合网格，不填补原有空隙 |
| KeepMask | List[bool] | 与输入 Voxels 同序，True 表示保留 |
| InitialSunHours | List[float] | 原始体素方案的有效累计日照 |
| FinalSunHours | List[float] | 优化后的有效累计日照 |
| VoxelImpactHours | List[float] | 每个体素被 Context-clear 射线穿过的累计时长 |
| EventVoxelPaths | DataTree | `{点;样本}` 分支内为完整射线路径的 VoxelID |
| IterationData | List[dict] | 每轮删除体素、体积和改善小时 |
| Report | List[str] | 最终状态和逐点结果 |

## 4. 优化逻辑

### 完整路径

RhinoCommon `MeshRay` 返回一张 Mesh 的第一处命中。为了知道一条太阳射线经过哪些体素，Optimizer 对每个体素分别执行检测，然后按距离排序：

```text
Protected Point + Sample Time
→ V12 → V13 → V14
```

只有移除路径中仍然存在的全部遮挡体素，该样本才恢复直射日照。

### 顶部删除规则

若射线穿过某柱第3层，则删除动作必须包含：

```text
第3层 + 当前仍保留的所有更高层
```

这样不会留下悬空体素。

### 连续时长

候选动作按连续时间窗口生成，而不是只统计单条射线。`TimeStep = 1`、`MinimumContinuousMinutes = 3` 时，孤立恢复一分钟不会被当作有效改善。

### 停止条件

- 所有 Context 基准可达标的点均达到 RequiredSunHours；
- 没有能够降低有效日照缺口的顶部删除动作；
- 达到 MaxIterations；
- 用户按 Esc。

如果一个点在 Context-only 基准中已经低于 RequiredSunHours，Optimizer 将其标记为无法通过删除 Design 修复，不会为该点删除全部体量。

## 5. MVP算法边界

当前优化器是确定性的贪心启发式：

```text
有效日照缺口改善 ÷ 新删除体积
```

每轮选择比值最优的候选动作。它追求保留更多体积，但不保证数学意义上的全局最优解。

第一版暂不包含：

- 连续扇面 Forbidden Volume；
- 整数规划或全局组合优化；
- 任意方向的内部挖空；
- 结构、交通、采光和建筑功能约束；
- 平滑建筑表皮；
- 自动 Brep Solid Union。

## 6. 最终复核

推荐将 Optimizer 的 `KeptVoxels` 直接连接到第二个现有 Solver 的 `DesignVolume`。现有 Solver 支持 List Access，不要求先进行 Solid Union。

也可以连接 `OptimizedColumns`；它按 XY 柱合并精确体素网格，不再用一个
包围盒填满边界或输入几何原有的竖向空隙。两者的日照结果应一致：

```text
KeptVoxels → Solver After
OptimizedColumns → Solver After
```

最终必须核对：

- Solver After 的 SunHours 与 Optimizer FinalSunHours 一致；
- 所有可修复点达到 RequiredSunHours；
- MinimumContinuousMinutes 完全相同；
- Context 参数和日期时间参数完全相同。

只有通过独立复核后，才建议对 `OptimizedColumns` 执行一次最终 Solid Union 或生成外表皮。

## 7. Rhino 8 首轮验收

使用当前 12m × 4m × 18m 的直墙 Box，毫米单位：

```text
VoxelSizeXY = 2000
VoxelSizeZ = 2000
```

Voxelizer 应输出：

```text
12根柱子
每根9层
108个体素
```

然后检查：

1. 所有平面输出列表均为108项。
2. VoxelTree 有12个分支，每个分支9项。
3. Optimizer 的 InitialSunHours 与原始 DesignVolume Solver 结果接近；体素边界与原体量完全吻合时应一致。
4. RemovedVoxels 只能出现在每根柱子的顶部。
5. Optimizer FinalSunHours 达标后，把 KeptVoxels 接入 Solver After。
6. Solver After SunHours 与 Optimizer FinalSunHours 应一致。
7. 把某个点设置成 Context-only 已不足2小时，Optimizer 不应为它删除全部设计体量。
8. `EventVoxelPaths` 应出现 `{点;时间样本}` 分支，并列出完整 VoxelID 路径。
