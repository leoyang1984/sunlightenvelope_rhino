# Rhino / Grasshopper 上机验收清单

## 1. 接口检查

- 输入顺序与 README 一致。
- `Boundary` 为 Item Access + Curve。
- `Context` 为 List Access + GeometryBase，并建议 Flatten。
- 输出从上到下为 `P`、`H`、`I`。
- R8 SDK 组件已关闭特殊 `out` 输出。

## 2. 无 Context 测试

使用10 m × 10 m矩形：

```text
GridSize   = 2000 mm
HeightStep = 1000 mm
MaxHeight  = 5000 mm
```

预期：

- 5个高度分支。
- 每层25个点，总计125个点。
- 同一分析版本中所有点 H 相同。
- I 显示 `Unobstructed Fast Path`。
- 累计版与连续版在全天无遮挡且太阳样本连续时结果相同。

## 3. Box 遮挡测试

在地块南侧放置一个有效 Box/Brep，并接入 Context。

预期：

- I 中 `Source Mesh Parts`、`Joined Mesh Faces` 大于0。
- I 显示 `Obstruction Test: Enabled` 和 `Sun-Hour Evaluation: MeshRay`。
- 低层、靠近遮挡物的 H 通常小于高层或远处点。
- 删除 Context 后，同层 H 恢复一致。

## 4. 顶盖决定性测试

在整个 Boundary 上方放置一块覆盖全地块的水平封闭 Box，底面高于地面、低于或等于所有射线必须穿越的位置。确保全部采样点位于顶盖下方。

预期：

- 所有射线被顶盖拦截。
- H 应为0或接近0。

如果该测试不为0，优先检查 Context 类型、List Access、Flatten、模型位置和 I 中的 MeshRay 状态。

## 5. 连续版测试

对同一模型分别运行累计版和连续版。

必须满足：

```text
连续版 H <= 累计版 H
```

无遮挡且太阳样本连续时，两者相等；遮挡将日照切成多段时，连续版应严格小于累计版。

连续版 I 必须包含：

```text
Sun-Hour Metric: Longest Continuous Direct Sun
```

## 6. DataTree 合同

连接 Tree Statistics、Param Viewer 或 Panel，确认：

```text
P 与 H 分支路径一致
P 与 H 每个分支项目数一致
P{n}[i] 对应 H{n}[i]
```

不要只对 P 或 H 单独 Flatten、Graft 或 Simplify。

## 7. R7 专项

- R7 累计版和连续版必须粘贴到 GhPython / IronPython 2.7 组件。
- 不使用 `Convert To GH_ScriptInstance`。
- Mesh、Brep、Extrusion、Surface 应正常参与遮挡。
- SubD 应被安全忽略，并在 I 中出现警告；需要时先转 Mesh 或 Brep。

## 8. 性能分级

先以低负载启动：

```text
TimeStep   = 60
GridSize   = 2000 mm
HeightStep = 1000 mm
```

确认正确后依次提高到10分钟、5分钟或1分钟。参数变化前先将 `Run` 设为 False。

## 9. 验收记录

每次测试至少记录：

- Rhino 版本与系统平台。
- 使用的脚本文件。
- 模型单位和绝对公差。
- Boundary 尺寸。
- Context 类型与数量。
- 采样点、层数、太阳时间区间和射线数量。
- I 的完整文本。
- 计算耗时以及是否能用 ESC 中断。

