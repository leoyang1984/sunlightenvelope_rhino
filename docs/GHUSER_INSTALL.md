# 安装与使用 Grasshopper 组件

面向拿到 `.ghuser` 文件、要在 Grasshopper 里用起来的人。不需要读代码,
也不需要装任何开发工具。

第一次用建议直接看[完整教程](TUTORIAL.md),那份从装插件一路走到跑通
整条流水线,带具体数值。本文是更简略的安装参考。

想知道这些文件是怎么构建出来的,见
[构建 Grasshopper User Object](GHUSER_BUILD.md)。

## 1. 这是什么

三个 Grasshopper 组件,用日照条件反推建筑体量能建到哪里:

| 组件 | 名称 | 做什么 |
|---|---|---|
| 组件0 | **SolarConstraintSolver** | 算保护点能晒到多少太阳,并比较「有设计体量」和「只有周边建筑」两种情况 |
| 组件1 | **SolarDesignVoxelizer** | 把设计体量切成带编号的体素块 |
| 组件2 | **SolarVoxelOptimizer** | 算每个体素挡了谁的太阳,自上而下删除体素直到日照达标 |

标准接法:

```text
组件0（原方案日照）
          │
DesignVolume → 组件1（切体素）→ 组件2（日照 + 切削）
                                     │
                                     └→ 组件0（切削后独立验证）
```

组件0在同一个文件里放**两个实例**:一个分析原始体量,一个接组件2的
`KeptVoxels` 做独立复核。不是两个不同组件。

组件只负责计算,不判断是否合格、不套法规阈值。阈值判断留在 Grasshopper
里做。

## 2. 选哪一套

两套组件,算法完全相同,只是运行环境不同。**按你的 Rhino 版本选一套装,
不要两套都装。**

| 你的 Rhino | 取哪个目录 | 装完出现在 |
|---|---|---|
| Rhino 8 | `dist/ghuser/rhino8/` | Sunlight → **Voxel Pipeline** |
| Rhino 7 | `dist/ghuser/rhino7/` | Sunlight → **Voxel Pipeline (IronPython)** |

分组名特意分开,是为了万一两套都装进了 Rhino 8 还能分清。

## 3. 下载

仓库里直接放了构建好的组件,**不需要 GitHub 账号,也不用自己编译**:

```text
dist/ghuser/rhino8/    Rhino 8 用
dist/ghuser/rhino7/    Rhino 7 用
```

在 GitHub 上打开对应目录,逐个点开文件,右上角 **Download raw file**。
或者直接下载整个仓库的 ZIP(绿色 **Code** 按钮 → **Download ZIP**),解压
后到 `dist/ghuser/` 里取。

命令行:

```bash
git clone https://github.com/leoyang1984/sunlightenvelope_rhino
# 组件在 sunlightenvelope_rhino/dist/ghuser/
```

### 其他渠道

**Release 附件** —— 打了版本标签的正式版在
[Releases](https://github.com/leoyang1984/sunlightenvelope_rhino/releases)
页面,同样匿名可下,链接可以直接发给别人。

**CI Artifact** —— 每次构建的产物在 Actions 页面。**需要登录 GitHub**
才能下载,而且有保留期,过期就没了。只在需要某次特定构建时才用这个。

`dist/ghuser/MANIFEST.txt` 记录了这批文件构建自哪次运行、以及源码摘要,
可以用来确认手上的文件是不是最新的。

## 4. 安装

把三个 `.ghuser` 复制到 Grasshopper 的 User Objects 文件夹。

**最省事的找法**:打开 Grasshopper,菜单
**File → Special Folders → User Object Folder**,系统会直接打开那个目录。

手动路径:

**Windows**

```text
%APPDATA%\Grasshopper\UserObjects
```

**macOS**

```text
~/Library/Application Support/McNeel/Rhinoceros/8.0/Plug-ins/
  Grasshopper (b45a29b1-4343-4035-989e-044e8580d9cf)/UserObjects
```

Rhino 7 把路径里的 `8.0` 换成 `7.0`。

复制完**重启 Grasshopper**。

## 5. 确认装好了

在 Grasshopper 的组件面板找 **Sunlight** 标签页,应该看到三个带图标的
组件。拖一个 `SolarDesignVoxelizer` 出来,端口应该是齐的:

```text
输入   DesignVolume, VoxelSizeXY, VoxelSizeZ, Run
输出   Voxels, VoxelIDs, ColumnIDs, LayerIDs,
       VoxelCenters, VoxelVolumes, VoxelTree, Report
```

端口是预置的,**不需要手工创建或重命名**。如果拖出来是空白组件,说明装
错了目录或者没重启。

## 6. 第一次使用

先用组件1单独跑通,再接后面两个。

1. 在 Rhino 里画一个**闭合实体**当设计体量(`Box` 最简单)。
2. 拖出 `SolarDesignVoxelizer`。
3. `DesignVolume` 接那个实体。
4. `VoxelSizeXY` 和 `VoxelSizeZ` 各接一个 Number Slider。**注意单位是
   模型单位**:毫米文件里填 `3000` 表示 3 米,填 `3` 表示 3 毫米,会直接
   撞上体素数量上限。
5. `Run` 接一个 Boolean Toggle,先保持 `False`。
6. `Report` 接一个 Panel。
7. 接完再把 `Run` 切成 `True`。

**每次运行后先看 `Report`。** 所有状态、统计、警告和错误都从这里出:

```text
Status: Completed        正常
Status: Waiting          Run 还是 False
Status: Input Error      输入有问题，下面会写是哪一个
Status: Cancelled        被 ESC 中断了
Status: Runtime Error    运行时异常
```

跑通之后再接组件2和组件0,接线要求见
[Rhino 7 使用指南第4节](RHINO7_PIPELINE_GUIDE.md)——那一节讲的接线规则
对 R8 同样适用。

## 7. 用的时候要注意

**组件1到组件2之间不能加东西。** `Voxels`、`VoxelIDs`、`ColumnIDs`、
`LayerIDs` 四个列表按同一个体素索引对齐,中间插 Sort、Cull、Dispatch
会打乱顺序,组件2的切削结果就不再对应实际几何。要筛选请在组件2**输出
之后**做。

**两个组件0实例的参数必须完全一致。** 太阳参数、日期、`TimeStep`、
`MinimumContinuousMinutes`、`RequiredSunHours` 建议用同一组 Slider 同时
喂给两个实例,不要各接各的,否则前后对比没有意义。

**几何输入的 Type Hint 可以不设。** 三个组件都能自动解析 Grasshopper
几何、Rhino 文档 `Guid`、`ObjRef`、RhinoObject。但 **Access 必须设对**
(`List` 误设成 `Item` 是最常见的错,组件只会拿到第一项)。User Object
版本的 Access 已经预置好了,除非你手动改过。

**引用的 Rhino 对象删掉了会报出来。** 看到 `could not be resolved`,
说明引用的对象已经不在了,不是计算错误。

**SubD 在 R7 版会被忽略并告警**,需要先在 Rhino 里转成 Brep 或闭合
Mesh。R8 版直接支持。

**算得慢就先降精度。** 顺序是:增大体素尺寸 → 增大 `TimeStep` → 减少
周边建筑的网格面数。改参数前先把 `Run` 设回 `False`。

**长时间计算可以按 ESC。** 组件会丢弃部分结果并在 `Report` 标记
`Status: Cancelled`,不会输出半套不同步的数据,重新运行即可。

## 8. 更新

重新下载 `dist/ghuser/` 里对应版本的文件,覆盖 User Objects 文件夹里的
旧文件,重启 Grasshopper。

**注意一个限制:已经放在画布上的组件不会跟着更新。** `.ghuser` 在拖到
画布的那一刻把代码复制进了组件实例,更新只影响**之后新拖出来的**。旧
文件里的老实例仍然跑旧代码。

所以排查问题时**不能凭组件外观判断代码版本**。确认用的是新版最可靠的
办法是:删掉画布上的旧组件,重新拖一个出来。

## 9. 卸载

删掉 User Objects 文件夹里那三个 `.ghuser` 文件,重启 Grasshopper。
没有其他残留,不写注册表也不改 Rhino 配置。

## 10. 遇到问题

**组件面板里找不到 Sunlight 标签页**

文件没放对目录,或者没重启 Grasshopper。用 File → Special Folders →
User Object Folder 确认路径。

**拖出来是空白组件,没有端口**

同上,通常是装到了另一个 Rhino 版本的目录。检查路径里的版本号。

**组件报红,Report 里是 Runtime Error**

先确认装的是与 Rhino 版本匹配的那一套。R7 的组件装进 R8 也能加载,但
不一定能正常运行。

**结果和预期不符**

按顺序查:

1. `Report` 里有没有 SubD 或 Boolean 失败的警告;
2. Access 有没有被改过(`List` vs `Item`);
3. 组件1到组件2中间有没有插入改变顺序的组件;
4. 两个组件0实例的参数是不是完全一致;
5. 模型的绝对公差。

**想确认结果对不对**

用同一组输入跑组件1 → 组件2,与已验收的基线比较:

```text
组件1  560个候选体素，38个边界裁切体素，Boolean失败0
组件2  移除104个体素，保留率 86.22%
       FinalSunHours = [2.85, 2.45, 2.00]
```

## 当前状态

User Object 打包已完成、通过 CI 构建,并已于 2026-08-04 在 Grasshopper 中
**完成装载验收**:六个组件正常加载,端口齐全,能够计算。

首次用于真实项目前仍建议按第5节和第6节走一遍,确认你这边的 Rhino 版本
和模型单位下结果合理。

进度记录在[开发路线图](ROADMAP.md)。
