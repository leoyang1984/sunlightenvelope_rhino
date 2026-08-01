# Solar Voxel Pipeline 开发路线图

更新日期：2026-08-01

## 固定组件编号

| 编号 | 名称 | 职责 |
|---|---|---|
| 组件0 | Solar Constraint Solver | 日照计算、Context/Design 双场景比较、原方案分析和切削后验证 |
| 组件1 | Solar Design Voxelizer | 将设计体量转换为带 ID、ColumnID 和 LayerID 的像素/体素块 |
| 组件2 | Solar Voxel Optimizer | 计算点—时间—体素遮挡关系，并按日照要求切削体素 |

标准流程：

```text
组件0 Before
     ↓
组件1 → 组件2 → 组件0 After
```

组件0 Before 和组件0 After 是同一个脚本的两个 Grasshopper 实例。

## 当前能力

### 组件0：日照计算

- Rhino 8 Python 3 SDK-Mode，另有 Rhino 7 IronPython 2.7 版。
- 累计直射日照。
- 最小连续日照段门槛。
- Context-only 与 Context + Design 双场景比较。
- 输出日照时长、受影响点、违规数据和设计遮挡事件。
- 已支持 Goo、Rhino `Guid`、`ObjRef`、RhinoObject 和 Rhino Point 解析。
- 无法解析的 `Guid` 会明确报错或告警，不静默当作空输入。

### 组件1：切像素块

- 与组件0共用 `DesignVolume`。
- World XY / World Z 网格。
- 边界单元与 `DesignVolume` 求实体交集，不再整格丢弃。
- 每个高度层独立判断，不因下方空层删除上方有效体素。
- 输出同步的 VoxelID、ColumnID、LayerID、中心、真实体积和 DataTree。
- 已支持 Goo、Rhino `Guid`、`ObjRef`、RhinoObject 和直接几何输入。

### 组件2：日照 + 切削

- 与组件0共用 Protected Points、Context 和太阳参数。
- 建立完整的点—时间—体素射线路径。
- 按最小连续时长计算有效累计日照。
- 使用顶部闭包规则和确定性贪心策略删除体素。
- 输出保留体素、删除体素、最终日照和迭代报告。
- 已支持 Goo、Rhino `Guid`、`ObjRef`、RhinoObject 和直接几何输入。

## 当前实机验收状态

| 环节 | 状态 | 结果摘要 |
|---|---|---|
| 组件1 | 已通过 | 560个候选体素全部输出，38个边界裁切体素，Boolean失败0 |
| 组件1 → 组件2 | 已通过 | 最新组件2正确读取3个保护点和560个临时体素 |
| 组件2 | 已通过 | 4轮移除104个体素，保留率86.22%，三个点最终为2.85、2.45、2.00小时 |
| 组件2 → 组件0 After | 待验收 | 需要独立复核最终 SunHours |

Grasshopper Python组件不会自动跟随仓库脚本更新。发生类型或接口异常时，
必须先确认画布组件已经完整替换为最新脚本；端口名称正确不代表内部代码
是最新版本。

## Grasshopper User Object 打包

三个组件的 R7 和 R8 版本都已打包为 `.ghuser`,端口预置,不需要手工创建。
bundle 由 `tools/build_ghuser_bundles.py` 从脚本和 `tools/ghuser_spec.py`
生成,构建由 CI 完成。

**构建好的成品提交在 `dist/ghuser/` 下**,匿名可下载,不需要 GitHub 账号
也不需要编译。CI Artifact 需要登录且有保留期,只作为构建暂存。
安装见[安装与使用 Grasshopper 组件](GHUSER_INSTALL.md),
构建见[构建 Grasshopper User Object](GHUSER_BUILD.md)。

打包状态:

| 环节 | 状态 |
|---|---|
| 六个 bundle 生成与同步校验 | 已通过 |
| metadata 与 RunScript 签名一致性 | 已通过 |
| CI 构建两套 `.ghuser` | 已通过 |
| 成品过期检测(源码摘要) | 已通过 |
| 在 Rhino 中装载并计算 | **待验收** |

CI 能证明构建成功、产物大小合理,但 `.ghuser` 的内容经 GH_IO 压缩,
不借助 Grasshopper 无法核对。**首次分发前必须在 Rhino 里装一次**,确认
端口齐全、能算出与脚本版一致的结果。

componentizer 每次运行都给端口分配新 GUID,`.ghuser` 因此不是字节可
复现的,无法靠重新构建比对来判断仓库里的成品是否过期。改为对
`src/ghuser` 取摘要记入 `dist/ghuser/MANIFEST.txt`,由
`tools/stamp_ghuser_release.py --check` 校验,CI 每次都跑。

**替换 `dist/ghuser/` 的内容后必须重新打戳**,否则下一次推送会报 STALE。

### 打版本

打 `v*` 标签会让 CI 把六个 `.ghuser` 自动挂到 Release 附件。建议**在
Rhino 装载验收通过之后**再打第一个版本号。

## Rhino 7 分支

三个组件各有一个 IronPython 2.7 版本，供没有 Rhino 8 的协作方使用：

- `src/rhino7/SolarConstraintSolver_Rhino7_GhPython.py`
- `src/rhino7/SolarDesignVoxelizer_Rhino7_GhPython.py`
- `src/rhino7/SolarVoxelOptimizer_Rhino7_GhPython.py`

由对应 R8 版本逐行回移，算法、编号规则和输出契约不变。适配项：

| 项目 | 处理方式 |
|---|---|
| `RunScript` 签名与 `GH_ScriptInstance` | 改为模块级 `execute(...)` 入口，端口手工创建 |
| `list[...]` 类型注解 | 随 SDK 包装层一并移除 |
| `nonlocal` | 改用单元素列表可变格，沿用文件中既有的计数器写法 |
| `time.perf_counter()` | 改为 `time.time()` |
| `timedelta.total_seconds()` 与 `timedelta / 2` | 改用 `timedelta_to_seconds()` 辅助函数 |
| SubD | 安全忽略并输出警告 |
| 字典遍历顺序 | 顺序可观测处改用 `collections.OrderedDict` |

最后一项是唯一会影响结果的适配。组件2的 `choose_best_action` 在
`comparison_key` 打平时保留先遇到的候选，CPython 3 靠字典插入序保证
可复现，IronPython 2.7 不保证。`action_sources` 因此改为 `OrderedDict`，
以复刻 R8 的遍历顺序。`column_top_closure` 内的 `lowest_layer_by_column`
返回集合，顺序不可观测，保持普通字典。

### R7 验收状态

| 环节 | 状态 |
|---|---|
| IronPython 2.7 语法兼容性扫描 | 已通过 |
| 与 R8 原件逐行差异复核 | 已通过 |
| 字典顺序确定性审计 | 已通过 |
| Rhino 7 实机验收 | **待验收** |

R7 实机验收的判据是与 R8 结果一致：用同一组输入运行组件1 → 组件2，
`FinalSunHours` 应为 `[2.85, 2.45, 2.00]`，保留率 86.22%，移除104个体素。
出现偏差时优先检查端口 Access 设置和 SubD 输入，再检查体素编号是否
直接来自组件1。

## 下一阶段计划

### P-Verify：完成端到端独立复核

1. 复制组件0作为组件0 After。
2. 将组件2的 `KeptVoxels` 接入组件0 After 的 `DesignVolume`。
3. 保持 Protected Points、Context、日期时间、太阳参数、`TimeStep`、
   `MinimumContinuousMinutes` 和 `RequiredSunHours` 完全一致。
4. 验证组件0 After 的 SunHours 与组件2 FinalSunHours 一致：
   `[2.85, 2.45, 2.00]`。
5. 保存完整 Report，完成本轮端到端验收记录。

### P0：补齐组件0几何接口自适应（代码已完成，待上机验收）

目标：组件0在保持现有17个输入和4个输出不变的前提下，达到与组件1、
组件2一致的几何引用兼容性。

实施项：

1. 增加统一的 `resolve_rhino_geometry`。**已完成**，与组件1、组件2
   的实现逐字一致。
2. `ProtectedPoints` 自动处理 `Guid`、`ObjRef`、Rhino Point 和 Point3d。
   **已完成**，Rhino `Point` 取 `Location` 后再转 `Point3d`。
3. `DesignVolume`、`ContextBuildings` 自动处理 `Guid`、`ObjRef`、
   RhinoObject、Brep、Mesh、Extrusion、Surface 和 SubD。**已完成**，
   两个角色共用 `build_analysis_mesh`，一处改动同时覆盖。
   R7 版仍按既定约定忽略 SubD 并告警。
4. 无效或失效 Guid 输出明确的输入错误或警告。**已完成**，新增
   `is_unresolved_guid`：`ProtectedPoints` 报输入错误，两个几何角色
   报警告。
5. 不改变太阳计算、连续时长、射线判断和输出数据结构。**已确认**，
   改动只落在输入解析层，逐行 diff 复核无其他变更。

R8 与 R7 同步完成，两个版本的解析逻辑逐字一致。

验收条件（**待上机**）：

- Type Hint 正确设置时，现有测试结果保持不变。
- Type Hint 设为 No Type Hint 时，Rhino 引用点和引用实体仍可计算。
- 两种接口设置的 `SunHours`、`ViolationData` 和 `ConstraintData` 一致。
- Context 为空时仍按无遮挡基准处理。
- 失效 Guid（先引用再删除对象）应出现明确报错或告警，而不是被当作
  空输入静默跳过。
- 自动化核心测试和 Rhino 8 上机冒烟测试均通过。
- Rhino 7 侧重复同一组验收。

### P1：三个组件的接口兼容性回归矩阵

针对组件0、1、2分别测试：

| 输入来源 | Point | Brep | Mesh | Guid | ObjRef | GH Goo |
|---|---:|---:|---:|---:|---:|---:|
| Rhino 文档引用 | 验证 | 验证 | 验证 | 验证 | 验证 | 不适用 |
| Grasshopper 原生几何 | 验证 | 验证 | 验证 | 不适用 | 不适用 | 验证 |
| Python组件直接输出 | 验证 | 验证 | 验证 | 验证 | 验证 | 验证 |

同时检查：

- Item/List Access 配置错误能否给出明确提示；
- 空输入、空列表和失效引用；
- Brep/Mesh 混合列表；
- 组件1输出直接连接组件2；
- 组件2的 `KeptVoxels` 直接连接组件0 After。

### P2：共享接口规范

三个脚本仍保持可独立复制到 Grasshopper 的单文件形式，但应遵守同一套：

- 几何解析顺序；
- 类型名称和错误信息；
- Guid 失效处理；
- 输入列表扁平化规则；
- Report 状态字段；
- 回归测试规范。

## 暂不进入本阶段

- Forbidden Volume 连续扇面生成；
- 全局最优整数规划；
- 自动平滑外表皮；
- 法规报告自动生成；
- Agent/MCP 自动操作 Grasshopper。
