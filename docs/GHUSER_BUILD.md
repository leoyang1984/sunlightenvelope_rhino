# 构建 Grasshopper User Object

把管线组件打包成 `.ghuser`,拖到画布上端口就是齐的,不用再手工创建和
重命名。面向需要把组件分发给协作方的场景。

覆盖 **Rhino 7 和 Rhino 8 各三个组件,共六个 bundle**。两边算法同源,
装哪一套取决于你的 Rhino 版本。

## 为什么是 .ghuser

R7 没有 SDK-Mode,脚本版组件0、1、2合计需要手工创建41个输入和22个输出。
`.ghuser` 把端口定义写进 `metadata.json`,构建时烧进组件,这一步就消失了。

代价见本文最后一节,不是没有的。

## 目录结构

```text
src/ghuser/
├── rhino7/            IronPython 2.7，Rhino 7
│   ├── SolarConstraintSolver/
│   ├── SolarDesignVoxelizer/
│   └── SolarVoxelOptimizer/
└── rhino8/            Python 3，Rhino 8
    ├── SolarConstraintSolver/
    ├── SolarDesignVoxelizer/
    └── SolarVoxelOptimizer/
```

每个目录下都是 `code.py` + `metadata.json` + `icon.png` 三件套,
**全部由脚本生成,不要手改**。事实源在别处:

| 内容 | 事实源 |
|---|---|
| 算法 | `src/rhino7/*.py`、`src/rhino8/*.py` |
| 端口 | `tools/ghuser_spec.py` |
| 图标 | `tools/icons/*.png` |

端口只在 `ghuser_spec.py` 里写一次,同一组件的 R7 和 R8 两个 flavour 由
它同时生成——手写六份 JSON 迟早会让配对漂移。

两个 flavour 需要不同的代码形状:

- **rhino7** —— GhPython advanced mode 要一个继承
  `ghpythonlib.componentbase.executingcomponent` 的类,所以脚本的模块级
  入口被换成该包装。
- **rhino8** —— Python 3 组件本来就认 SDK 脚本里的
  `Script_Instance(GH_ScriptInstance)`,所以代码逐字照搬,只加一行生成标记。
  `#! python 3` 必须留在第一行,那是 R8 判定语言用的。

## 本机准备(不需要 Rhino)

改完 R7 脚本后重新派生并自检:

```bash
python3 tools/build_ghuser_bundles.py
```

校验 bundle 是否符合 componentizer 的要求:

```bash
python3 tools/check_ghuser_bundle.py
```

`check_ghuser_bundle.py` 挡的是构建时才会暴露、或者构建能过但运行才炸的
错误:未知的 `typeHintID`、非法的 `scriptParamAccess`、缺 `instanceGuid`、
以及 `RunScript` 签名和 `inputParameters` 对不上。它的合法值表抄自
componentizer 源码,不依赖 Rhino,任何机器都能跑。

确认 生成物与事实源没有漂移:

```bash
python3 tools/build_ghuser_bundles.py --check
```

改了脚本或端口却忘了重新生成时,这条会报 `STALE`。

图标改动后先跑 `python3 tools/make_icons.py`,再跑生成器。

## 构建 .ghuser:优先用 CI

`.github/workflows/build-ghuser.yml` 已经配好,**不需要任何人本地装
IronPython**。

触发方式:

- 推送改动到 `src/ghuser/`、`src/rhino7/`、`src/rhino8/` 或 `tools/`;
- 在 GitHub 的 Actions 页面手动 **Run workflow**;
- 推送 `v*` 标签,构建产物会自动附加到 Release。

工作流分两段:

1. `validate`(Ubuntu)—— 跑派生同步检查和 bundle 校验,不需要 Windows,
   秒级失败;
2. `build`(Windows,矩阵两路)—— `rhino7` 用 IronPython 2.7.8.1 构建,
   `rhino8` 用 cpython 模式构建,各自上传 Artifact。

产出两个包:

| Artifact | 适用 | componentizer |
|---|---|---|
| `sunlight-ghuser-rhino7` | Rhino 7 | `ironpython` |
| `sunlight-ghuser-rhino8` | Rhino 8 | `cpython` |

公司那边拿组件只需要:进仓库 Actions 页面 → 打开最近一次成功的运行 →
下载对应版本的压缩包。不用装工具链,不用 Rhino。**只装与自己 Rhino
版本匹配的那一套。**

发正式版本时打标签即可:

```bash
git tag v0.1.0
git push origin v0.1.0
```

`.ghuser` 会出现在 Release 的附件里,链接可以直接发给别人。

## 本地构建(可选)

需要在自己机器上出包时,依赖是:

- 独立安装的 **IronPython 2.7**(推荐 2.7.8.1;2.7.9 和 2.7.11 已知与
  构建目标的 Rhino 6 SDK 冲突),Rhino 自带的那份不行;
- **GH_IO.dll**,通常在 `C:/Program Files/Rhino 7/Plug-ins/Grasshopper`。

```bash
git clone https://github.com/compas-dev/compas-actions.ghpython_components
ipy compas-actions.ghpython_components/componentize_ipy.py ^
    src/ghuser/rhino7 ^
    dist/ghuser/rhino7 ^
    --ghio "C:/Program Files/Rhino 7/Plug-ins/Grasshopper"
```

产物在 `dist/ghuser/`(已加入 `.gitignore`)。

R8 那套换 `componentize_cpy.py`,源目录用 `src/ghuser/rhino8`。

两个脚本不能混用:它们写入的组件 GUID 和 `typeHintID` 的 GUID 表都不同。
`componentize_cpy.py` 产出的是 Rhino 8 Python 3 组件,`componentize_ipy.py`
产出的是 IronPython 组件。用错了构建照样成功,组件却是错的类型。

## 安装

拿到 `.ghuser` 后(从 CI Artifact、Release 附件或本地构建),复制到
Grasshopper 的 User Objects 文件夹:

```text
Grasshopper → File → Special Folders → User Object Folder
```

重启 Grasshopper。组件出现在 **Sunlight** 标签页下:

- R8 一套在 **Voxel Pipeline** 分组;
- R7 一套在 **Voxel Pipeline (IronPython)** 分组。

分组特意分开,是为了万一两套都装进同一个 Rhino 8 时仍然分得清哪个是哪个。
正常情况下只装一套。

分发给多人时用 [Yak 包管理器](https://developer.rhino3d.com/guides/yak/creating-a-grasshopper-plugin-package/)
打成包,对方在 `_PackageManager` 里安装和更新,不用手动传文件。

## metadata.json 要点

端口的合法取值来自 componentizer,写错不会有友好提示:

| 字段 | 取值 |
|---|---|
| `scriptParamAccess` | `item` / `list` / `tree`(小写) |
| `typeHintID` | `geometrybase`、`point`、`float`、`int`、`bool`、`curve`、`mesh`、`brep`、`vector` 等,**全小写** |
| `nickname` | 1–5 个字符 |
| `exposure` | `-1, 2, 4, 8, 16, 32, 64, 128` |
| `isAdvancedMode` | 仅 IronPython 版读取,必须 `true`;cpython 版忽略它 |

`instanceGuid` 必须写死并保持不变。缺了它每次构建都会生成新 GUID,
Grasshopper 会当成一个不相干的新组件,旧文件里的实例就接不上了。

### 所有输入都是 optional

所有输入一律 `"optional": true`,这是有意的。输入缺失时组件照常运行,
由脚本自己的校验逻辑在 `Report` 里给出可读的错误,而不是让 Grasshopper
弹一句笼统的 "input failed to collect data"。这与整个项目「所有状态都从
Report 出」的设计一致。

## 已知局限

**已放置的实例不会随更新变化。** `.ghuser` 在拖到画布的那一刻把代码复制
进组件实例。之后更新 `.ghuser` 只影响新拖出来的实例,旧文件里的老实例
仍然运行旧代码——和现在手工粘贴脚本的处境一样。

要彻底解决,需要其中之一:

- 把算法主体装成 Python 模块放进 Rhino 的 IronPython 库路径,`.ghuser`
  只留调用壳。更新模块,所有实例下次运行即生效。
- 编译成 `.gha`。程序集在运行时加载,所有实例始终用当前代码。

在那之前,排查线上问题时**不能凭组件外观判断代码版本**,这一点和脚本版
一样。

**打包不替代上机验收。** `.ghuser` 只改变代码怎么到达组件,不改变它算
什么。R7 管线的实机验收仍然待做,判据见
[Rhino 7 组件0、1、2使用指南](RHINO7_PIPELINE_GUIDE.md)第6节。
