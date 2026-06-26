# VibeBench Arena

Codex-first quality gate for vibe coding projects.

> Codex writes code. VibeBench verifies it.

VibeBench Arena 是一个面向 Codex-first 和 AI 辅助开发流程的本地质量门禁工具。
AI coding agent 可以很快生成代码，但开发者仍然需要一个本地工具来判断这些代码是否适合进入交付流程。

v0.1.0 的目标很小：建立干净的 Python CLI 脚手架、配置模型和基础测试。它暂时不是大型 benchmark 平台。

## 为什么需要它

Vibe coding 提升了开发速度，也提高了代码审查压力。VibeBench Arena 希望在 AI 生成代码和最终交付之间，提供一个轻量、清晰、可本地运行的验证步骤。

项目原则：

- 优先本地运行
- 对新手友好
- 适合 Codex-first 工作流
- 每个里程碑只增加一个明确能力

## 快速开始

```bash
python -m pip install -e ".[dev]"
python -m vibebench --help
python -m vibebench init
python -m vibebench check
```

`init` 命令会创建：

```text
.vibebench/config.yaml
```

`check` 命令会读取 `.vibebench/config.yaml`，运行配置里的
`checks.test` 和 `checks.lint` 命令，打印 Rich 终端摘要，并把本次运行结果写入：

```text
.vibebench/runs/<timestamp>/metrics.json
.vibebench/runs/<timestamp>/check.log
```

示例输出：

```text
VibeBench check: vibebench-project
Status: passed
Score: 100
Risk: low

Group   Command        Status   Exit   Duration
test    pytest -q      passed   0      0.420s
lint    ruff check .   passed   0      0.120s

Metrics: .vibebench/runs/20260626_120000/metrics.json
```

Git diff 风险分析和 HTML 报告会在后续里程碑中实现。


## 当前 v0.1.0 范围

本版本包含：

- Python 3.11+ 包结构
- 基于 Typer 的 CLI
- Rich 终端输出
- Pydantic 配置模型
- YAML 配置加载和易读错误信息
- 执行配置中的 test 和 lint 命令
- JSON metrics 和可读 check 日志
- 简单 VibeScore 与风险等级计算
- pytest 测试
- ruff lint 配置
- GitHub Actions CI

可用命令：

```bash
vibebench --help
vibebench version
vibebench init
vibebench check
```

## Built with a Codex-First Workflow

VibeBench Arena 围绕一个简单理念构建：

> Codex writes code. VibeBench verifies it.

项目会优先保持小步迭代、测试清晰、实现可读，并把本地验证自然接入 AI 辅助开发流程。

## Roadmap

后续计划：

- 增加基础 git 工作区和 patch 感知能力
- 标记 secrets、测试删除等高风险变更
- 输出简单的终端验证摘要
- 增加适合 CI 的机器可读输出
- 在 CLI 足够有用后，再探索更丰富的报告形式

v0.1.0 不包含：

- git diff 分析
- HTML 报告
- benchmark 排行榜
- multi-agent arena 工作流
