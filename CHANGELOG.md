# 更新日志

本文件记录对外可见的变化。最新的在最上面。

## 未发布

本轮的主题是**让组件能被别人用上**:补齐 Rhino 7 版本,统一三个组件的
输入接法,并把六个组件打包成拖出来即用的 Grasshopper User Object。

### 新增

**Rhino 7 版组件0、1、2**

原先 Solar Voxel Pipeline 只有 Rhino 8 版本,没有 R8 的协作方用不了。
现在三个组件各有一个 IronPython 2.7 版本,与 R8 版共用同一套算法、编号
规则和输出契约:

- `src/rhino7/SolarConstraintSolver_Rhino7_GhPython.py`
- `src/rhino7/SolarDesignVoxelizer_Rhino7_GhPython.py`
- `src/rhino7/SolarVoxelOptimizer_Rhino7_GhPython.py`

使用方法见[Rhino 7 组件0、1、2使用指南](docs/RHINO7_PIPELINE_GUIDE.md)。

**Grasshopper User Object 打包**

三个组件的 R7 和 R8 版本都打包成了 `.ghuser`,端口预置,拖到画布上就能
接线。脚本版需要按 Rhino 版本手工创建41个输入和22个输出,这一步没有了。

构建好的组件直接提交在 `dist/ghuser/` 下,**不需要 GitHub 账号也不需要
自己编译**,点进仓库就能下载。CI Artifact 需要登录才能下载而且有保留期,
因此只作为备用渠道。安装方法见
[安装与使用 Grasshopper 组件](docs/GHUSER_INSTALL.md)。

**构建工具链**

- `tools/ghuser_spec.py` —— 端口的唯一定义,一份出两套 flavour;
- `tools/build_ghuser_bundles.py` —— 从脚本和端口定义生成六个 bundle;
- `tools/check_ghuser_bundle.py` —— 不依赖 Rhino 的 bundle 校验;
- `tools/make_icons.py` —— 生成 24×24 组件图标;
- `tools/stamp_ghuser_release.py` —— 给提交的成品打戳,并检测其是否已经
  落后于源码;
- `.github/workflows/build-ghuser.yml` —— CI 构建两套 `.ghuser`。

说明见 [tools/README.md](tools/README.md) 和
[构建 Grasshopper User Object](docs/GHUSER_BUILD.md)。

**新增文档**

- [完整教程](docs/TUTORIAL.md)
- [安装与使用 Grasshopper 组件](docs/GHUSER_INSTALL.md)
- [Rhino 7 组件0、1、2使用指南](docs/RHINO7_PIPELINE_GUIDE.md)
- [构建 Grasshopper User Object](docs/GHUSER_BUILD.md)
- [tools/README.md](tools/README.md)
- 本更新日志

### 变更

**组件0补齐几何输入自适应(路线图 P0)**

组件0原先只能解开 Grasshopper Goo,不能解析 Rhino 文档 `Guid`、`ObjRef`
或 RhinoObject,而组件1、组件2可以。同一个 Rhino 对象引用在组件1、2上
能用、在组件0上不能用,一条流水线要用两种接法。

现在三个组件共用同一份 `resolve_rhino_geometry`,接法统一:Access 仍需
按文档设置,几何输入的 Type Hint 变成建议而非必需。R8 和 R7 同步完成,
两个版本的解析逻辑逐字一致。

无法解析的 `Guid`(引用对象已删除,或 Rhino 文档不可用)会被明确报出:
`ProtectedPoints` 作为输入错误,`DesignVolume` 和 `ContextBuildings`
作为警告。不再静默当作空输入。

17个输入和4个输出不变,太阳计算、连续时长、射线判断和输出结构不变。

### 修复

**组件2在 IronPython 上的结果确定性**

组件2的贪心搜索在候选评分打平时保留先遇到的候选。R8 依靠 CPython 3
字典的插入序保证可复现,IronPython 2.7 的字典不保证顺序——同样的输入
会在平局时删掉不同的体素,结果偏离 R8 已验收的基线。

R7 版对顺序可观测的字典改用 `collections.OrderedDict`,复刻 R8 的遍历
顺序。`column_top_closure` 内返回集合的字典顺序不可观测,保持普通字典,
代码里有注释说明原因。

**CI 构建 R8 组件失败**

- componentizer 的 cpython 版通过 pythonnet 驱动 GH_IO.dll,而 action
  不安装它,构建报 `No module named 'clr'`;
- cpython 版不会自建目标目录(IronPython 版会),补上后报 `WinError 3`。

两条都已补进 workflow。

### 已知限制

- **R7 管线尚未完成实机验收。** 判据见
  [使用指南第6节](docs/RHINO7_PIPELINE_GUIDE.md)。
- **`.ghuser` 尚未在 Grasshopper 中装载验证。** CI 能证明构建成功,但
  `.ghuser` 内容经 GH_IO 压缩,不借助 Grasshopper 无法核对。
- **已放置的组件实例不随更新变化。** `.ghuser` 在拖到画布时把代码复制
  进实例,更新只影响新拖出来的。这与手工粘贴脚本是同一个限制。
- R7 管线忽略 SubD 并输出警告,需先在 Rhino 中转为 Brep 或闭合 Mesh。

---

## 此前

Solar Voxel Pipeline 的 Rhino 8 实现与验收记录见
[开发路线图](docs/ROADMAP.md)和
[Solar Voxel Pipeline MVP](docs/SOLAR_VOXEL_PIPELINE_MVP.md)。
