# Agent Skills

给 AI 编程助手（Claude Code 等）用的技能包。装上之后，可以直接用自然语言让助手
跑日照切削，不必自己记命令行参数。

| Skill | 作用 |
|---|---|
| [`sunlight-carve`](sunlight-carve/SKILL.md) | 日照约束体量切削：CAD 图纸或口头描述进，削好的 DXF 出 |

## 安装

### Claude Code

复制到用户级 skills 目录：

```bash
mkdir -p ~/.claude/skills
cp -R skills/sunlight-carve ~/.claude/skills/
```

想让它跟仓库保持同步，用软链代替复制（macOS / Linux）：

```bash
ln -sfn "$(pwd)/skills/sunlight-carve" ~/.claude/skills/sunlight-carve
```

Windows PowerShell（需管理员或开发者模式）：

```powershell
New-Item -ItemType SymbolicLink -Path "$env:USERPROFILE\.claude\skills\sunlight-carve" -Target "$PWD\skills\sunlight-carve"
```

装完在 Claude Code 里直接说「帮我算一下这个方案挡不挡北边的日照」，或者
`/sunlight-carve`。

### 让 skill 找得到引擎

skill 会依次尝试 `$CADSOLAR_HOME`、当前目录、当前 git 仓库根、
`~/sunlightenvelope_rhino`。如果仓库不在这些位置，设一个环境变量：

```bash
export CADSOLAR_HOME=/path/to/sunlightenvelope_rhino
```

### 依赖

```bash
pip install ezdxf
```

`numpy` 只有性能基准脚本 `tools/bench_headless.py` 需要。引擎本身不需要 Rhino。

## 其它 agent 运行时

`SKILL.md` 是带 YAML frontmatter 的普通 Markdown，正文就是给模型看的操作手册。
其它支持技能包的运行时可以直接读，或者照着里面的命令行调用
`python3 -m cadsolar`——引擎的接口是稳定的，不依赖任何特定 agent。
