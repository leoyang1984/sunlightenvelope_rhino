# 快速开始

## 选择脚本

| 环境 | 统计方式 | 文件 |
|---|---|---|
| Rhino 8 Python 3 SDK-Mode | 累计日照 | `src/rhino8/SunlightEnvelope_Rhino8_SDK.py` |
| Rhino 8 Python 3 SDK-Mode | 最长连续日照 | `src/rhino8/SunlightEnvelope_Rhino8_Continuous_SDK.py` |
| Rhino 8 Python 3 Script-Mode | 累计日照 | `src/rhino8/SunlightEnvelope_Rhino8_GhPython.py` |
| Rhino 7 GhPython / IronPython 2.7 | 累计日照 | `src/rhino7/SunlightEnvelope_Rhino7_GhPython.py` |
| Rhino 7 GhPython / IronPython 2.7 | 最长连续日照 | `src/rhino7/SunlightEnvelope_Rhino7_Continuous_GhPython.py` |

前期可建空间分析优先使用累计版；需要比较最长连续无遮挡时段时使用连续版。

## Rhino 8 SDK-Mode

1. 放置 Python 3 Script Component。
2. 打开编辑器，点击 **Convert To GH_ScriptInstance**。
3. 用选定 SDK 文件的完整代码替换编辑器内容。
4. 保存，让 `RunScript` 同步15个输入端。
5. 关闭组件右键菜单中的 **Standard Output/Error Parameter**。
6. 输出端首次手动设置为从上到下 `P`、`H`、`I`。

当前 Rhino 8 小版本可能只自动同步输入端，不会根据 `return P, H, I` 自动建立输出端。

## Rhino 7 GhPython

Rhino 7 没有 SDK-Mode 自动接口。放置 GhPython Component 后，手动创建15个输入和3个输出，再粘贴完整代码。

## 端口设置

| 输入 | Access | Type Hint |
|---|---|---|
| Boundary | Item | Curve |
| Context | List | GeometryBase |
| North | Item | Vector3d |
| Latitude、Longitude、TimeZone | Item | float/double |
| Month、Day | Item | int |
| StartHour、EndHour、TimeStep | Item | float/double |
| GridSize、HeightStep、MaxHeight | Item | float/double |
| Run | Item | bool |

`Context` 建议 Flatten。`Boundary` 不要使用 Circle、Guid 或 ghdoc Object 类型提示。

输出顺序必须是：

```text
P
H
I
```

## 毫米模型的首次测试

```text
Boundary    = 10000 × 10000 mm 闭合矩形
Context     = 空，或一个南侧 Box
North       = Unit Y
Latitude    = 31.233333
Longitude   = 121.466667
TimeZone    = 8
Month       = 12
Day         = 21
StartHour   = 9
EndHour     = 15
TimeStep    = 10
GridSize    = 1000
HeightStep  = 1000
MaxHeight   = 5000
Run         = True
```

毫米文件中 `500` 表示0.5米，`1000` 表示1米。不要把 `GridSize` 设为 `0.5`，否则代表0.5毫米。

## 输出检查

- `P`：三维采样点 DataTree。
- `H`：与 P 一一对应的小时值。
- `I`：状态、统计和警告。

运行后先检查 I：

```text
Status: Completed
Obstruction Test: Enabled
Sun-Hour Evaluation: MeshRay
```

连续版还应显示：

```text
Sun-Hour Metric: Longest Continuous Direct Sun
```

没有 Context 时显示 `Unobstructed Fast Path`，属于正常状态。

