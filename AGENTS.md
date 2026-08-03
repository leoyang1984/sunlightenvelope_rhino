# 给 AI 助手

这个文件是 AI 编程助手进入本仓库的入口。人类读者请看 [README.md](README.md)。

## 这个仓库是什么

日照约束体量切削：把一个设计体量，按"周边保护点必须晒够几小时"的要求削成合规
的可建体量。两套实现，同一套算法：

- **Grasshopper 组件**（`src/rhino8/`、`src/rhino7/`、`dist/ghuser/`）——给已经在
  用 Rhino 的人
- **headless 引擎**（`src/headless/`）——纯 Python，不需要 Rhino，从 CAD 图纸或
  一段文字描述算到结果

两者在同一场景上逐项对过，数值一致，记录在 [docs/HEADLESS_ENGINE.md](docs/HEADLESS_ENGINE.md)。

配套的 agent skill 在 [`skills/sunlight-carve/`](skills/sunlight-carve/SKILL.md)。

## 用户说"帮我装一下"时

**先告诉用户你要做什么，再动手。** 安装会写入用户的 skills 目录
（默认 `~/.claude/skills`）；带 `--with-deps` 还会往用户的 Python 里装包。这些是
用户机器上的改动，不要默默做。

```bash
git clone https://github.com/leoyang1984/sunlightenvelope_rhino.git
cd sunlightenvelope_rhino
python3 tools/install_skill.py
```

脚本是幂等的，重复跑安全。它做四件事并逐条报告：查 Python 版本、查 `ezdxf`、
安装 skill、**用内置参考场景跑一遍并与已核对的基准比对**。最后一步是关键——
文件复制成功不等于能用。

常用参数：

| 参数 | 作用 |
|---|---|
| `--check` | 只检查不写文件，用来诊断"装了但用不了" |
| `--link` | 软链而非复制，让 skill 跟仓库更新同步 |
| `--with-deps` | 缺 `ezdxf` 时执行 pip install |
| `--dest DIR` | 换一个 skills 目录 |

**任何一步 FAIL 都不要跳过。** 脚本会给出具体命令。特别是
`externally-managed-environment`（Debian/Ubuntu、Homebrew Python 常见）：
**不要用 `--break-system-packages` 绕过**，按提示建虚拟环境。

装完还要让 skill 找得到引擎，二选一：`cd` 进仓库目录再提要求，或者

```bash
export CADSOLAR_HOME=/path/to/sunlightenvelope_rhino
```

验证安装成功的判据不是"没报错"，而是自检那行输出：

```
[OK  ] 引擎自检通过
       参考场景：328 体素 / 保留 185 / 切除 143，逐点 [4.1667, 2.1667, 2.0, 2.0]，独立复核一致
```

这组数字与 Rhino 8 组件在同一场景上的结果逐项一致。对不上就是有问题，不要
继续往下用。

## 用户说"帮我算日照"时

用 [`skills/sunlight-carve/SKILL.md`](skills/sunlight-carve/SKILL.md)，它是完整的
操作手册。几条最容易踩的，先记住：

- **方位**：北半球冬季太阳在南，所以设计体量要在保护点**南侧**才会挡光。
  算出来"一点都不挡"，先怀疑方位说反了。
- **北向**：用 `--north-bearing`（北偏东为正），不要用底层的 `--north-angle`
  （逆时针为正，符号相反）。填反不会报错，只会给出一个看着合理的错答案。
- **算之前复述参数**给用户确认。几何错了看得出来，城市或日期错了看不出来。
- **产出物一律由工具生成**，不要手写 HTML 或几何文件。

## 改代码时

```bash
python3 -m unittest discover -s tests     # 75 项，改完必须全过
```

几条硬约束：

- `src/headless/cadsolar/kernel.py` 直接从 `src/rhino8/` 的组件文件里抽取算法执行，
  **不是复制粘贴**。改组件脚本会同时影响 headless 引擎，这是有意的。
- `report.py` 产出的 HTML 必须**自包含、零外部依赖**。加一个 CDN 引用就会让报告
  在离线环境失效，而且要等打开时才发现。
- 改动可能影响数值时，用 `tools/crosscheck_rhino.py` 与真组件对一遍（需要
  Rhino 8 和 `rhinocode`）。
- 提交 Rhino 文件前跑 `tools/sanitize_3dm.py`——`.3dm` 会嵌入作者的本机绝对路径。

## 这个工具不做什么

不出日照报审报告。采样对象是三维点，不是法规规定的窗台或满窗测点；切削用的是
贪心启发式，不声称全局最优；几何限于平面轮廓竖直拉伸，没有悬挑、斜屋面和曲面
表皮。**向用户交付结果时必须说明这一点。**
