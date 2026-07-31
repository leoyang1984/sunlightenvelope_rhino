# Solar Constraint Solver MVP

这是独立于原有五个 Sunlight Envelope 脚本的新组件，文件为：

`src/rhino8/SolarConstraintSolver_Rhino8_SDK.py`

## 目标

对一组扁平的 Protected Points 比较两个场景：

1. 基准场景：仅 Context Buildings。
2. 设计场景：Context Buildings + Design Volume。

计算设计体量造成的日照损失，并记录仅由设计遮挡产生的事件。当前版本不生成 Forbidden Volume。

## Rhino 8 组件

使用 Python 3 Script Component，并转换为 `GH_ScriptInstance`。保存完整脚本后应同步 17 个输入：

| 输入 | Access | 类型 | 说明 |
|---|---|---|---|
| ProtectedPoints | List | Point3d | 扁平保护点列表 |
| DesignVolume | List | GeometryBase | 方案体量，可包含 Brep 或 Mesh |
| ContextBuildings | List | GeometryBase | 现状遮挡，可为空 |
| North | Item | Vector3d | 项目北向 |
| Latitude | Item | float | 纬度 |
| Longitude | Item | float | 经度 |
| TimeZone | Item | float | UTC 时差，中国为 8 |
| Year、Month、Day | Item | int | 分析日期 |
| StartHour、EndHour | Item | float | 当地时间范围 |
| TimeStep | Item | float | 采样步长，分钟 |
| MinimumContinuousMinutes | Item | float | 可累计的最小连续日照段，分钟 |
| RequiredSunHours | Item | float | 合格小时数 |
| ImpactTolerance | Item | float | 认定设计影响的小时容差 |
| Run | Item | bool | True 时运行 |

输出保持四个：

- `SunHours`：与 ProtectedPoints 顺序一致的合格累计日照小时。
- `ViolationData`：受影响或不合格保护点的字典记录列表。
- `ConstraintData`：按保护点索引分支的设计遮挡事件。
- `Report`：状态、统计、警告与错误。

## 最小连续时长规则

`MinimumContinuousMinutes` 不是“最长连续日照”。它是累计日照的资格门槛：

- 每段连续直射日照单独计时。
- 达到门槛的整段计入累计值。
- 短于门槛的整段不计入累计值。

例如三段日照分别为 2、4、3 分钟，门槛为 3 分钟，最终累计为 7 分钟。

设为 `0` 时等同于原始累计日照。为了可靠识别门槛，`TimeStep` 应小于或等于 `MinimumContinuousMinutes`。例如门槛为 3 分钟时，建议 `TimeStep = 1` 分钟。

`ViolationData` 的记录还保留 `RawSunHours`、`RawBaselineHours` 和各连续段时长，便于对比过滤前后结果。

## ConstraintData 归因

事件仅在以下条件同时满足时产生：

1. Context Buildings 没有遮挡该时刻的太阳；
2. Design Volume 遮挡该时刻的太阳。

因此它表示设计新增的遮挡事件，不把既有建筑造成的遮挡误归因给方案。
