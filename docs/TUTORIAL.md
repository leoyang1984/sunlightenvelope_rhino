# 完整教程：从装插件到跑通日照切削

从零走一遍整条流水线。跟着做完，你会得到一个被日照条件切削过的建筑体量，
并且能独立复核它确实达标。

前提只有一条：Rhino 7 或 Rhino 8，会基本的 Grasshopper 操作。
**不需要写代码，不需要编译任何东西。**

想要更简略的安装说明见[安装与使用 Grasshopper 组件](GHUSER_INSTALL.md)；
本文是带具体数值的完整走查。

---

## 第 0 步：装上插件

### 下载

组件已经构建好放在仓库里，**不需要 GitHub 账号**：

| 你的 Rhino | 下载这个目录 |
|---|---|
| Rhino 8 | `dist/ghuser/rhino8/` |
| Rhino 7 | `dist/ghuser/rhino7/` |

在 GitHub 上打开目录，逐个点开三个 `.ghuser` 文件，右上角
**Download raw file**。或者绿色 **Code** 按钮 → **Download ZIP** 下载整个
仓库，解压后到对应目录里取。

**只装与自己 Rhino 版本匹配的那一套。**

### 安装

打开 Grasshopper，菜单 **File → Special Folders → User Object Folder**，
把三个 `.ghuser` 复制进去，**重启 Grasshopper**。

手动路径：

```text
Windows   %APPDATA%\Grasshopper\UserObjects
macOS     ~/Library/Application Support/McNeel/Rhinoceros/8.0/Plug-ins/
            Grasshopper (b45a29b1-4343-4035-989e-044e8580d9cf)/UserObjects
```

Rhino 7 把 `8.0` 换成 `7.0`。

### 确认装好

组件面板出现 **Sunlight** 标签页，下面三个组件：

```text
Solve   SolarConstraintSolver    组件0
Voxel   SolarDesignVoxelizer     组件1
Optim   SolarVoxelOptimizer      组件2
```

拖一个 `Voxel` 出来，应该自带 4 个输入和 8 个输出。如果是空白组件，
说明放错目录或者没重启。

---

## 第 1 步：在 Rhino 里准备几何

新建一个 Rhino 文件，**单位设为毫米**（本教程的数值按毫米写）。

需要四样东西：

**1. 设计体量** — 一个闭合实体，就是你想盖的楼。

```text
Box：60000 × 30000 × 60000 mm（60 × 30 × 60 米）
```

必须是**闭合**的。用 `SelClosedSrf` 确认，开放曲面会被判为输入错误。

**2. 周边建筑** — 已有的遮挡物，可以是多个。

```text
Box：40000 × 20000 × 40000 mm，放在设计体量南侧约 40 米处
```

**3. 保护点** — 需要保证日照的位置，比如南侧住宅的窗台。

在周边建筑南侧地面上方约 1.5 米处放 3 个点，横向间隔 10 米左右。

**4. 北向** — 用一个 Vector 表示。正北就是 `Unit Y`。

---

## 第 2 步：组件0 — 先看原方案挡了多少

在切削之前，得先知道现状有多糟。这一步用组件0 比较两种情况：只有周边
建筑时保护点能晒多久，加上设计体量后还剩多久。

拖出一个 `Solve`，按下表接线。参数用上海设计阶段的推荐值
（来源见[上海设计阶段参数](SHANGHAI_DESIGN_PROFILE.md)）：

| 输入 | 接什么 |
|---|---|
| `ProtectedPoints` | 那 3 个点 |
| `DesignVolume` | 设计体量 Box |
| `ContextBuildings` | 周边建筑 Box |
| `North` | Unit Y |
| `Latitude` | `31.233333` |
| `Longitude` | `121.466667` |
| `TimeZone` | `8` |
| `Year` | `2024` |
| `Month` | `12` |
| `Day` | `21` |
| `StartHour` | `9` |
| `EndHour` | `15` |
| `TimeStep` | `10` |
| `MinimumContinuousMinutes` | `60` |
| `RequiredSunHours` | `2` |
| `ImpactTolerance` | `0.1` |
| `Run` | Boolean Toggle，**先 False** |

`Report` 接一个 Panel。接完再把 `Run` 切成 `True`。

### 读结果

**永远先看 `Report`。** 正常应该是：

```text
Status: Completed
```

看到别的先停下来：

| 状态 | 意思 |
|---|---|
| `Waiting` | `Run` 还是 False |
| `Input Error` | 输入有问题，下面几行会写是哪一个 |
| `Cancelled` | 被 ESC 中断了 |
| `Runtime Error` | 运行时异常 |

然后看两个输出：

- **`SunHours`** — 每个保护点在**有设计体量**时的合格日照小时数，顺序与
  `ProtectedPoints` 一致。
- **`ViolationData`** — 受影响或不达标的点的记录。

如果 `SunHours` 里有低于 `RequiredSunHours`（这里是 2 小时）的点，说明
设计体量确实挡了人家的太阳。**这就是接下来要解决的问题。**

如果一个都没低于 2 小时，说明这个体量本来就不构成日照问题，把设计体量
做大些或者往南挪一点再试。

### 关于 MinimumContinuousMinutes

这个参数是中国日照规范的核心：`60` 表示**只有连续晒满 1 小时以上的时段
才计入总数**。晒 20 分钟被挡一下、再晒 20 分钟，累计 40 分钟但一段都不
够 1 小时，按这个设置算作 0。

填 `0` 就退化成单纯累计，不做连续性要求。

---

## 第 3 步：组件1 — 把体量切成体素

组件0 告诉你有问题，但没说该削哪儿。要削就得先把体量切成能单独删除的块。

拖出一个 `Voxel`：

| 输入 | 接什么 |
|---|---|
| `DesignVolume` | **同一个**设计体量 Box |
| `VoxelSizeXY` | `6000` |
| `VoxelSizeZ` | `6000` |
| `Run` | Boolean Toggle |

> **单位陷阱**：毫米文件里 `6000` 是 6 米。写成 `6` 表示 6 毫米，会生成
> 天文数字的体素，直接撞上 25 万的安全上限报错。

### 读结果

`Report` 里会写：

```text
Output Columns:            柱子数量
Output Voxels:             体素总数
Full Box Voxels:           完整的方块
Boundary-Clipped Voxels:   被边界裁切过的
Boolean Operation Failures: 应该是 0
```

`Voxels` 接一个几何预览，应该看到原体量变成了一摞方块。

**八个输出是一套契约**：`Voxels[i]`、`VoxelIDs[i]`、`ColumnIDs[i]`、
`LayerIDs[i]`、`VoxelCenters[i]`、`VoxelVolumes[i]` 说的都是同一个体素。
`VoxelTree` 的分支 `{c}` 是第 c 根柱子，自下而上排列。

**Boolean 失败数不是 0** 的话，先检查设计体量是不是干净的闭合实体，
再考虑调整体素尺寸避开退化的相交情况。

---

## 第 4 步：组件2 — 自上而下削到达标

这一步是核心：算出每个体素挡了谁的太阳，然后从上往下删，直到保护点达标。

拖出一个 `Optim`：

| 输入 | 接什么 |
|---|---|
| `ProtectedPoints` | 与组件0**同一组**点 |
| `Voxels` | 组件1 的 `Voxels` |
| `VoxelIDs` | 组件1 的 `VoxelIDs` |
| `ColumnIDs` | 组件1 的 `ColumnIDs` |
| `LayerIDs` | 组件1 的 `LayerIDs` |
| `ContextBuildings` | 与组件0**同一个**周边建筑 |
| `North` 到 `RequiredSunHours` | 与组件0**完全相同的值** |
| `MaxIterations` | `50` |
| `Run` | Boolean Toggle |

> **最容易犯的错**：在组件1 和组件2 之间插了 Sort、Cull、Dispatch 或
> 任何改变项目顺序的组件。四个列表按同一个体素索引对齐，任何一个被重排，
> 切削结果就不再对应实际几何。**要筛选请在组件2 的输出之后做。**

强烈建议太阳参数用**同一组 Slider** 同时喂给组件0 和组件2，不要各接各的。

### 读结果

```text
KeptVoxels        削完剩下的体素 —— 这就是新的建筑体量
RemovedVoxels     被删掉的
KeepMask          每个输入体素保留与否，顺序与输入一致
InitialSunHours   削之前的日照
FinalSunHours     削之后的日照
IterationData     每一轮删了什么、代价多少、收益多少
```

把 `KeptVoxels` 接几何预览，就看到被日照条件"啃"出缺口的体量了。

对比 `InitialSunHours` 和 `FinalSunHours`，后者应该都达到或接近
`RequiredSunHours`。

`Report` 里的保留率告诉你牺牲了多少体积。

### 顶部闭包规则

删体素不是想删哪个删哪个：**要删一个体素，必须连同它上面所有还留着的
体素一起删**。否则会得到悬空的楼板，不是能盖的东西。

这也是为什么切削总是从顶部开始。

---

## 第 5 步：组件0 再来一次 — 独立复核

这一步经常被跳过，但它是整条流水线里最有价值的一步。

组件2 说结果达标了，但那是它自己算的自己。**用一个独立的组件0 重新算一遍
切削后的体量**，如果两边数字对得上，结果才可信。

复制第 2 步那个 `Solve` 组件（Ctrl+C / Ctrl+V），只改一个接线：

```text
DesignVolume  ←  组件2 的 KeptVoxels
```

**其余全部保持与第一个实例完全一致**：保护点、周边建筑、北向、经纬度、
时区、年月日、起止时间、`TimeStep`、`MinimumContinuousMinutes`、
`RequiredSunHours`、`ImpactTolerance`。

### 判据

```text
组件0 After 的 SunHours  ≈  组件2 的 FinalSunHours
```

两者应当一致。不一致说明两个组件的输入参数没对齐，**先逐项核对参数，
不要先怀疑算法**。

完整接法：

```text
组件0（原方案）
        │
体量 → 组件1（切体素）→ 组件2（日照 + 切削）
                              │
                              └→ 组件0（切削后复核）
```

组件0 是**同一个组件的两个实例**，不是两个不同组件。

---

## 调参：跑太慢怎么办

第一轮永远先用粗参数跑通，再逐步加密。降低耗时的优先顺序：

1. **增大体素尺寸** —— `VoxelSizeXY` / `VoxelSizeZ` 从 6000 起步；
2. **增大 `TimeStep`** —— 先用 60 分钟跑通，再降到 10 或 5；
3. **减少周边建筑** —— 删掉明显不可能产生遮挡的；
4. **降低周边建筑的网格面数**。

改参数前先把 `Run` 设回 `False`，改完再打开。

### 安全上限

```text
组件1  候选体素        250,000
组件2  保护点          10,000
组件2  体素            10,000
组件2  射线 × 体素测试  20,000,000
```

撞上限会直接报错而不是硬算。通常意味着体素尺寸给小了。

### 算到一半想停

按 **ESC**。组件会丢弃部分结果并标记 `Status: Cancelled`，不会输出半套
不同步的数据。重新运行即可。

---

## 常见问题

**组件全红，Report 说 Input Error**

照着 `Report` 里的行读，它会指名是哪个输入。最常见的是设计体量不闭合，
或者数值输入没接。

**体素数量明显偏少**

`List` 类型的输入被设成了 `Item`，组件只拿到了第一项。打包版的 Access
是预置好的，除非你手动改过。

**结果里少了一块体量**

`Report` 里查有没有 SubD 警告。R7 版不处理 SubD，会跳过并告警，需要先在
Rhino 里转成 Brep 或闭合 Mesh。R8 版直接支持。

**看到 `could not be resolved`**

引用的 Rhino 对象被删掉了。不是计算错误，去 Rhino 里确认对象还在不在。

**改了脚本但组件行为没变**

`.ghuser` 在拖到画布的那一刻就把代码复制进了组件实例，更新文件只影响
**之后新拖出来的**。删掉画布上的旧组件重新拖一个。

**组件0 After 和组件2 对不上**

按顺序查：两个组件0 实例的参数是否完全一致 → 组件1 到组件2 中间有没有
插入改变顺序的组件 → 模型绝对公差。

---

## 这个工具不做什么

写在最前面反而容易被忽略，放在这里：

- **不判断是否合格**，不套任何法规阈值。`RequiredSunHours` 是你自己填的。
- **不生成正式日照分析报告。** 采样对象是三维点，不是法规规定的窗台、
  满窗测点。正式报审涉及规定坐标高程体系和检测合格的软件，本项目不是
  替代品。
- **不做全局最优。** 组件2 用的是确定性贪心启发式，能给出一个可用解，
  不声称是体积最大的那个解。

上海参数的适用边界见[上海设计阶段参数](SHANGHAI_DESIGN_PROFILE.md)，
其中说明了本项目的基准年与规范边界参数的差异。

---

## 接下来

- 参数细节和端口全表：[Rhino 7 组件0、1、2使用指南](RHINO7_PIPELINE_GUIDE.md)
  （接线规则对 R8 同样适用）
- 更简的安装说明：[安装与使用 Grasshopper 组件](GHUSER_INSTALL.md)
- 算法边界和验收记录：[Solar Voxel Pipeline MVP](SOLAR_VOXEL_PIPELINE_MVP.md)
- 只想算日照、不需要切削：[快速开始](QUICK_START.md) 里的五个采样脚本

## 当前状态

打包组件已通过构建校验，并已于 2026-08-04 **完成 Grasshopper 装载验收**：
六个 User Object 正常加载，端口齐全，能够计算。

首次用于真实项目前，仍建议按本教程跑一遍最小场景，确认在你的 Rhino 版本
和模型单位下结果合理。进度见[开发路线图](ROADMAP.md)。
