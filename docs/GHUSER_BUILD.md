# 构建 Grasshopper User Object

把管线组件打包成 `.ghuser`,拖到画布上端口就是齐的,不用再手工创建和
重命名。面向需要把组件分发给协作方的场景。

当前状态:**组件1已完成样板,组件0和组件2尚未打包。**

## 为什么是 .ghuser

R7 没有 SDK-Mode,脚本版组件0、1、2合计需要手工创建41个输入和22个输出。
`.ghuser` 把端口定义写进 `metadata.json`,构建时烧进组件,这一步就消失了。

代价见本文最后一节,不是没有的。

## 目录结构

```text
src/ghuser/components/
└── SolarDesignVoxelizer/
    ├── code.py         由 src/rhino7 派生，不要手改
    ├── metadata.json   端口定义
    └── icon.png        24×24
```

`src/rhino7/*.py` 仍然是唯一事实源。`code.py` 是从它派生的,派生规则是
去掉模块级入口、换成 GhPython advanced mode 的 `executingcomponent` 类。

## 本机准备(不需要 Rhino)

改完 R7 脚本后重新派生并自检:

```bash
python3 tools/build_ghuser_code.py
```

校验 bundle 是否符合 componentizer 的要求:

```bash
python3 tools/check_ghuser_bundle.py
```

`check_ghuser_bundle.py` 挡的是构建时才会暴露、或者构建能过但运行才炸的
错误:未知的 `typeHintID`、非法的 `scriptParamAccess`、缺 `instanceGuid`、
以及 `RunScript` 签名和 `inputParameters` 对不上。它的合法值表抄自
componentizer 源码,不依赖 Rhino,任何机器都能跑。

确认 `code.py` 与 R7 脚本没有漂移:

```bash
python3 tools/build_ghuser_code.py --check
```

改了 R7 脚本却忘了重新派生时,这条会报 `STALE`。

## 构建 .ghuser(需要 Rhino 机器)

用 [compas-dev/compas-actions.ghpython_components](https://github.com/compas-dev/compas-actions.ghpython_components)
的 componentizer。

依赖:

- 独立安装的 **IronPython 2.7**(Rhino 自带的那份不行);
- **GH_IO.dll**,通常在 `C:/Program Files/Rhino 7/Plug-ins/Grasshopper`。
  componentizer 也能自己从 NuGet 拉。

```bash
git clone https://github.com/compas-dev/compas-actions.ghpython_components
ipy compas-actions.ghpython_components/componentize_ipy.py ^
    src/ghuser/components ^
    dist/ghuser ^
    --ghio "C:/Program Files/Rhino 7/Plug-ins/Grasshopper"
```

产物在 `dist/ghuser/`(已加入 `.gitignore`)。

## 安装

把 `.ghuser` 复制到 Grasshopper 的 User Objects 文件夹:

```text
Grasshopper → File → Special Folders → User Object Folder
```

重启 Grasshopper。组件出现在 **Sunlight** 标签页的 **Voxel Pipeline** 分组下。

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
| `isAdvancedMode` | 必须 `true`,因为 `code.py` 用的是 `RunScript` 类形式 |

`instanceGuid` 必须写死并保持不变。缺了它每次构建都会生成新 GUID,
Grasshopper 会当成一个不相干的新组件,旧文件里的实例就接不上了。

### 所有输入都是 optional

四个输入全部 `"optional": true`,这是有意的。输入缺失时组件照常运行,
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
