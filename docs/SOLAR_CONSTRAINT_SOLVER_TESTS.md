# Solar Constraint Solver MVP 验收

## 第一次运行

先使用一个保护点、一个设计 Box，ContextBuildings 留空。

建议输入：

```text
North                       = Unit Y
Latitude                    = 31.2304
Longitude                   = 121.4737
TimeZone                    = 8
Year / Month / Day          = 2026 / 12 / 21
StartHour / EndHour         = 9 / 15
TimeStep                    = 1
MinimumContinuousMinutes    = 3
RequiredSunHours            = 2
ImpactTolerance             = 0.001
Run                          = True
```

先看 `Report`。第一行应为 `Status: Completed`，不能出现 Point3d 转换错误。

## A–I 验收清单

### A. 接口

- 共 17 个输入、4 个输出。
- ProtectedPoints、DesignVolume、ContextBuildings 为 List Access。
- 其余为 Item Access。

### B. 点输入兼容

直接把 Rhino Point 参数连接到 ProtectedPoints。GH_Point 应被正确转换，不再出现 `cannot be converted to Point3d`。

### C. 无遮挡

DesignVolume 使用一个不可能挡住太阳的远处 Box，ContextBuildings 留空。`SunHours` 应大于 0，`ConstraintData` 应为空。

### D. 设计完全遮挡

把封闭 Box 放到保护点上方，使分析时段太阳射线都穿过 Box。最终 `SunHours` 应明显降低，`ConstraintData` 应出现事件。

### E. Context 完全遮挡

把同一遮挡 Box 接入 ContextBuildings，同时把 DesignVolume 移开。基准与最终均受 Context 遮挡，不应产生设计 ConstraintData。

### F. 双场景归因

Context 只挡一部分时刻，Design 再挡另一部分。ConstraintData 只能包含“Context 清晰、Design 遮挡”的时刻。

### G. 最小连续时长

使用能把日照切成短段和长段的遮挡模型：

- `MinimumContinuousMinutes = 0` 时记录原始累计值。
- 改为 `3` 后，少于 3 分钟的连续段应被剔除。
- `RawSunHours` 不随门槛变化；`SunHours` 可以降低。

### H. 顺序与树结构

- `SunHours[i]` 必须对应 `ProtectedPoints[i]`。
- `ConstraintData` 的 `{i}` 分支必须对应第 i 个保护点。

### I. 输入错误与中断

- TimeStep 大于 MinimumContinuousMinutes 时，Report 应给出精度警告。
- 无效日期、负门槛或空保护点应返回 `Status: Input Error`。
- 大计算按 Esc 后，只保留已完整计算的保护点。

## 当前功能边界

此轮只验收日照比较与约束数据。Forbidden Volume、布尔切割和法规报告均不属于当前 MVP。
