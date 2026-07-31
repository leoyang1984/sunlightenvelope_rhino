# Solar Voxel Pipeline 开发路线图

更新日期：2026-07-31

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

- Rhino 8 Python 3 SDK-Mode。
- 累计直射日照。
- 最小连续日照段门槛。
- Context-only 与 Context + Design 双场景比较。
- 输出日照时长、受影响点、违规数据和设计遮挡事件。
- 已支持 Grasshopper Goo 解包。
- 尚未支持无 Type Hint 时的 Rhino `Guid`/`ObjRef` 自动查询。

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

## 下一阶段计划

### P0：补齐组件0几何接口自适应

目标：组件0在保持现有17个输入和4个输出不变的前提下，达到与组件1、
组件2一致的几何引用兼容性。

实施项：

1. 增加统一的 `resolve_rhino_geometry`。
2. `ProtectedPoints` 自动处理 `Guid`、`ObjRef`、Rhino Point 和 Point3d。
3. `DesignVolume`、`ContextBuildings` 自动处理 `Guid`、`ObjRef`、
   RhinoObject、Brep、Mesh、Extrusion、Surface 和 SubD。
4. 无效或失效 Guid 输出明确的输入错误或警告。
5. 不改变太阳计算、连续时长、射线判断和输出数据结构。

验收条件：

- Type Hint 正确设置时，现有测试结果保持不变。
- Type Hint 设为 No Type Hint 时，Rhino 引用点和引用实体仍可计算。
- 两种接口设置的 `SunHours`、`ViolationData` 和 `ConstraintData` 一致。
- Context 为空时仍按无遮挡基准处理。
- 自动化核心测试和 Rhino 8 上机冒烟测试均通过。

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

