# VibeBench Arena

**面向 vibe coding 项目的 Codex-first 质量门禁：在本地运行检查、生成可审阅证据，并说明一个 AI 辅助仓库是否已经具备 adoption 或 release 准备度。**

> Codex 负责写代码，VibeBench 负责说明到底发生了什么。

[![CI](https://github.com/wemby-1/vibebench-arena/actions/workflows/ci.yml/badge.svg)](https://github.com/wemby-1/vibebench-arena/actions/workflows/ci.yml)
![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)
![License Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-green)

![VibeBench report preview](docs/assets/report-preview.svg)

<!-- VIBEBENCH_STATUS_START -->
## VibeBench Status

- Overall status: passed
- VibeScore: 100
- Risk level: low
- Changed files: 0
- Patch lines: 0
- Risk findings: 0

<!-- VIBEBENCH_STATUS_END -->

VibeBench Arena 是一个 local-first 的 AI coding 质量门禁。它位于“agent 已经改完代码”和“人类准备信任、合并、分享或发布”之间，把结果变成可检查的工程证据。

![VibeBench flow](docs/assets/vibebench-flow.svg)

## 30 秒理解

VibeBench 不是另一个聊天机器人，也不是 benchmark 排行榜。它是面向 AI 辅助工程的 evidence-first CLI：运行本地检查，捕获 score/risk/diff 信号，生成 proof packet 和 review artifacts，并验证仓库是否具备 adoption、workflow CI 或 release-readiness 审阅条件。

## 3 步快速开始

```bash
python3 -m pip install -e ".[dev]"
python3 -m vibebench ci
python3 -m vibebench latest --all-paths
```

1. 安装并在仓库根目录运行 VibeBench。
2. 跑一次本地 CI 风格质量门禁，生成时间戳 run 目录。
3. 检查最新 artifacts，决定是否分享、接入 GitHub Actions，或继续做 adoption/release 检查。

如果只想先看流程，不想真正执行检查，可以先跑 `python3 -m vibebench ci --dry-run --json`。

## Showcase Demo

如果你想快速评估项目，建议先看 [showcase page](docs/showcase.md) 和 [showcase demo kit](examples/showcase-artifacts/README.md)。它们用 5 分钟路径串起 readiness、workflow coverage、CI plan、evidence packet 和 trust boundary，不把 README 变成大段命令清单。

如果是投资人、技术尽调或评审场景，可以继续看 [investor brief](docs/investor-brief.md)、[technical due diligence](docs/technical-due-diligence.md)、[proof matrix](docs/proof-matrix.md)、[demo script](docs/demo-script.md) 和 [Trust Center](docs/trust-center.md)。

## 为什么这个项目存在

AI coding 让“写出来”越来越快，但“如何 review、如何证明、如何复现、如何放心地给别人看”并没有自动变简单。

很多仓库的问题不是没有测试，而是缺少一套让人快速回答这些问题的证据层：

- 到底改了什么？
- 实际跑了哪些检查？
- 留下了哪些 artifacts？
- 这个仓库是否准备好给团队 adoption？
- release readiness 是否可复现、可复查？

VibeBench 试图补上这层证据，但不会宣称自己替代人工 review，也不会夸大为“保证质量”。

## 你会得到什么

- 本地 CI 风格 runs，包含 lint、tests、gate、summary 和可打包 artifacts。
- adoption、workflow、release readiness 检查，帮助团队判断仓库是否进入更正式的工程流程。
- JSON、Markdown、HTML 三类证据输出，适合脚本、reviewer 和 GitHub 展示。
- GitHub Actions step summary 与可下载 artifacts，不依赖 GitHub API 发评论。
- 一个更像“evidence packet”的输出模型，而不只是一个 passed/failed。

## 适合谁

- 使用 Codex、Cursor、Claude Code 等 agent 工作流的独立开发者。
- 正在引入 AI coding agents、又希望保持可信质量信号的小团队。
- 需要 evidence 而不是 vibes 的 reviewer、技术评估者或投资人。
- 希望为 AI 辅助贡献建立可复现质量信号的开源维护者。

## Demo Funnel

在仓库根目录运行：

```bash
python3 -m vibebench ci
python3 -m vibebench adoption-ready --json
python3 -m vibebench bundle
python3 -m vibebench doctor --strict
```

- `python3 -m vibebench ci` 证明项目能跑完整本地质量门禁，并写出 run 目录。
- `python3 -m vibebench adoption-ready --json` 证明仓库可以输出 machine-readable 的 adoption readiness 信号。
- `python3 -m vibebench bundle` 证明最新 run 可以被打包成可分享的证据包。
- `python3 -m vibebench doctor --strict` 证明本地环境和关键 artifacts 已经满足更严格的 CI/release 风格检查。

如果想先看将要执行什么，再决定是否正式运行，可以先用 `python3 -m vibebench ci --dry-run --json`。如果要看 release readiness，再补 `python3 -m vibebench release-check --json`。

## Evidence Packet

VibeBench 的核心不是一句状态，而是一组可审阅证据。常规 run 或 proof workflow 可以产生：

- `metrics.json`：记录 score、risk 和核心运行指标。
- `manifest.json`：记录这次 run 产出了什么、路径在哪里。
- `vibebench-bundle.zip`：把最新 run 打成一个便于分享或归档的 zip。
- `github-step-summary.md`：给 GitHub Actions 展示的简洁摘要。
- `proof.html`、`proof.json`、`proof.md` 和 `proof.zip`：使用 `vibebench proof` 时生成的聚焦 proof packet。
- `preflight.json` / `preflight.md`：启用 preflight 时留下的 adoption setup 信号。
- `workflow-check.json` / `workflow-check.md`：启用 workflow-check 时留下的 workflow readiness 证据。
- `release-check.json` / `release-check.md`：本地 release readiness 证据。
- `evidence-room/`：当可用时，包含 `index.html`、trust notes、questionnaire、scorecard、share-check 等对外审阅材料。

这些 artifacts 的目标很具体：回答跑了什么、改了什么、留下了什么，以及 reviewer 下一步该看什么。

## 它和普通 CI 有什么不同

普通 CI 主要回答一个问题：检查有没有通过。

VibeBench 还会继续回答：

- 改动到底是什么？
- 生成了哪些证据？
- 项目是否准备好进入 adoption？
- workflow 是否处于期望的 VibeBench CI mode？
- release/adoption 信号能不能从仓库本地复现？

所以它更强调 manifest、summary、bundle、readiness checks 和 review artifacts，而不是只给一个 badge。

## Readiness 模型

VibeBench 的 readiness 不是一个单点，而是一层层叠加的：

- `preflight`：最安全的只读入口，用来看 setup signals。
- `workflow-check`：检查仓库 workflow 是否符合期望的 VibeBench CI mode。
- `adoption-ready`：把 workflow、doctor、release readiness 等信号压缩成一个 adoption 视角答案。
- `release-check`：只读地产生 release readiness 证据，不会打 tag、发布包或创建 GitHub Release。
- `doctor --strict`：确认环境与关键 artifacts 是否健康到可以做更严格门禁。

实操路径见 [quickstart](docs/quickstart.md)、[adoption](docs/adoption.md) 和 [Trust Center](docs/trust-center.md)。

## 从 GitHub 怎么快速评估

- [Showcase](docs/showcase.md)：面向 reviewer 的产品演示叙事。
- [Showcase demo kit](examples/showcase-artifacts/README.md)：可复制命令和 artifact 解读。
- [Investor brief](docs/investor-brief.md)：产品价值、市场假设、成熟度、风险和非承诺。
- [Technical due diligence](docs/technical-due-diligence.md)：架构、证据生命周期、测试、风险和评估清单。
- [Proof matrix](docs/proof-matrix.md)：把 claim、command 和 artifact 对齐。
- [Demo script](docs/demo-script.md)：5 分钟和 15 分钟演示脚本。
- [Quickstart](docs/quickstart.md)：从 clone 到本地证据的最短路径。
- [Adoption guide](docs/adoption.md)：团队如何安全引入这套流程。
- [Artifact gallery](docs/artifact-gallery.md)：给非核心维护者看的 artifact 说明。
- [Trust Center](docs/trust-center.md)：local-first、artifact、安全边界和非承诺说明。
- [Demo guide](docs/demo.md)：适合演示时使用的紧凑命令序列。
- [Evaluate in 5 minutes](docs/evaluate.md)：新访客最快的可信度判断路径。
- [Positioning](docs/positioning.md)：项目和品类定位。
- [Use cases](docs/use-cases.md)：这套工具主要帮谁解决什么问题。
- [Case study](docs/case-study.md)：一次 AI 辅助改动如何变成可审阅证据。

## 常用补充命令

```bash
python3 -m vibebench ci --dry-run --json
python3 -m vibebench preflight --json
python3 -m vibebench workflow-check
python3 -m vibebench release-check --json
python3 -m vibebench evidence-room --output-dir /tmp/vibebench-evidence-room --zip
python3 -m vibebench latest --artifact evidence-room-index-html --path-only
```

- `ci --dry-run --json` 用来预览质量流水线。
- `preflight --json` 用来只读查看 adoption/setup 信号。
- `workflow-check` 用来只读检查现有 GitHub Actions workflow。
- `release-check --json` 用来记录本地 release readiness。
- `evidence-room --zip` 用来生成可对外检查的自包含审阅包。
- `latest --artifact ... --path-only` 用来直接定位某个具体 artifact。

## 项目边界

- 不宣称保证质量。
- 不宣称替代人工 review。
- 正常本地流程不会偷偷 publish、tag、release 或调用 GitHub API。
- 不要求托管服务才能评估核心价值。

如果想继续看更完整的产品叙事，可阅读 [product strategy](docs/product-strategy.md)、[public roadmap](docs/roadmap-public.md) 和 [commercial potential](docs/commercial-potential.md)。
