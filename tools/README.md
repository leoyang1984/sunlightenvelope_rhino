# tools

生成和校验 Grasshopper User Object 的脚本。都是纯 Python 3,不需要
Rhino、IronPython 或 .NET,任何机器都能跑。

真正把 bundle 编译成 `.ghuser` 的那一步需要 Windows 和 IronPython,由
CI 完成,见[构建 Grasshopper User Object](../docs/GHUSER_BUILD.md)。

## 文件

| 文件 | 作用 |
|---|---|
| `ghuser_spec.py` | 端口的唯一定义。三个组件的输入输出、类型、Access、说明文字都在这里 |
| `build_ghuser_bundles.py` | 从脚本和端口定义生成 `src/ghuser/` 下的六个 bundle |
| `check_ghuser_bundle.py` | 校验 bundle 是否符合 componentizer 的要求 |
| `make_icons.py` | 生成 `tools/icons/` 下的 24×24 组件图标,需要 Pillow |
| `stamp_ghuser_release.py` | 给 `dist/ghuser/` 里提交的成品打戳并校验是否过期 |
| `sanitize_3dm.py` | 重建 `.3dm`，丢掉渲染环境等会嵌入本机绝对路径的内容。提交 Rhino 文件到公开仓库前跑一次 |
| `crosscheck_rhino.py` | 经 rhinocode 驱动真组件，与 headless 引擎做数值对照 |
| `bench_headless.py` | headless 引擎的性能与包围盒粗筛等价性 |

## 数据流

```text
src/rhino7/*.py  ─┐
src/rhino8/*.py  ─┤
ghuser_spec.py   ─┼─→ build_ghuser_bundles.py ─→ src/ghuser/{rhino7,rhino8}/
tools/icons/*.png─┘                                      │
                                                         ↓
                                            CI: componentizer → *.ghuser
```

`src/ghuser/` 下的所有文件**都是生成的,不要手改**。改动应该落在上游:
算法改脚本,端口改 `ghuser_spec.py`,图标改 `make_icons.py`。

## 常用命令

重新生成六个 bundle:

```bash
python3 tools/build_ghuser_bundles.py
```

确认生成物与上游没有漂移(CI 也跑这条):

```bash
python3 tools/build_ghuser_bundles.py --check
```

改了脚本或端口却忘了重新生成时,这条会报 `STALE`。

校验 bundle 合法性:

```bash
python3 tools/check_ghuser_bundle.py
```

重新生成图标(改了 `make_icons.py` 之后):

```bash
python3 tools/make_icons.py && python3 tools/build_ghuser_bundles.py
```

## check_ghuser_bundle.py 挡住什么

componentizer 需要 Rhino 环境,通常只在 CI 的 Windows runner 上跑。这个
脚本在本地就能挡住那些**构建时才会失败、或者构建能过但运行才炸**的错误:

- 未知的 `typeHintID`(合法值全小写,写成 `GeometryBase` 不认);
- 非法的 `scriptParamAccess`(只接受 `item` / `list` / `tree`);
- 缺少或格式错误的 `instanceGuid`;
- 图标不是 24×24;
- `nickname` 超出 1–5 字符;
- **`RunScript` 签名与 `inputParameters` 不一致**。

最后一条最要紧:签名和端口定义对不上时构建照样成功,组件运行才报错,
而那时文件可能已经发出去了。两个 flavour 都会检查,R8 的类型注解会被
剥掉再比对。

合法值表抄自 componentizer 源码
([compas-dev/compas-actions.ghpython_components](https://github.com/compas-dev/compas-actions.ghpython_components))。
上游改了表,这里要跟着改。

## 为什么端口要集中定义

同一个组件有 R7 和 R8 两个 flavour,端口完全相同。手写六份
`metadata.json` 意味着组件0的端口说明存在两处、组件2的存在两处,改一处
忘一处只是时间问题。`ghuser_spec.py` 写一次,两个 flavour 一起生成。

两个 flavour 的差异只有三处,由生成器处理:

- **代码形状** —— R7 要 `executingcomponent` 包装类,R8 直接用脚本里
  现成的 `Script_Instance`;
- **`isAdvancedMode`** —— 只有 IronPython 版读这个字段;
- **subcategory** —— 分开命名,两套同时装进 R8 时还能分清。

## 提交的成品为什么需要打戳

`dist/ghuser/` 里放着构建好的 `.ghuser`,使用者不需要账号也不用编译就能
下载。风险是有人改了脚本或端口却忘了重新构建,仓库就会发出与源码不符的
组件。

componentizer 每次运行都给每个输入输出端口分配新 GUID
(`System.Guid.NewGuid()`),所以 `.ghuser` **不是字节可复现的**,没办法靠
重新构建再比对来判断新旧。可复现的是**构建的输入**:`src/ghuser` 下的
全部内容。

`stamp_ghuser_release.py` 把这份摘要记进 `dist/ghuser/MANIFEST.txt`,
`--check` 重算并比对。bundle 变了而二进制没跟上时会报 STALE,CI 里也跑
这一条。

替换 `dist/ghuser/` 的内容后必须重新打戳:

```bash
python3 tools/stamp_ghuser_release.py --run-url <CI 运行链接>
```

## 一个已经踩过的坑

仓库如果放在时间戳精度较粗的文件系统上(比如外置 exFAT 硬盘),刚改过的
`ghuser_spec.py` 可能与它的 `.pyc` 落在同一秒内,Python 会认为缓存有效,
于是**用旧端口定义生成文件,还报告一切同步**。

`build_ghuser_bundles.py` 因此设置了 `sys.dont_write_bytecode = True`。
不要去掉。
