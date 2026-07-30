# 示例文件

本目录包含用户在 Rhino 8 中保存的当前测试模型：

- `SunlightEnvelope_Rhino8_Example.3dm`
- `SunlightEnvelope_Rhino8_Example.gh`

建议先打开 `.3dm`，再打开 `.gh`。如果 Grasshopper 中出现失效引用，请重新为 Boundary 和 Context 选择 Rhino 几何。

该示例用于人工上机检查，不是经过认证的法规日照分析样例。连接 I 到 Panel，并通过以下字段确认实际使用的统计方式：

```text
Sun-Hour Evaluation
Sun-Hour Metric
```

如需切换累计版和连续版，复制现有 Python 组件并替换内部代码，保持15个输入以及 `P、H、I` 输出不变。

