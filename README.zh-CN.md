# VibeBench Arena

**AI 生成代码提交前的本地质量门禁。**

> Codex 负责写代码，VibeBench 负责验收。

[![CI](https://github.com/wemby-1/vibebench-arena/actions/workflows/ci.yml/badge.svg)](https://github.com/wemby-1/vibebench-arena/actions/workflows/ci.yml)
![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)
![License Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-green)

![VibeBench report preview](docs/assets/report-preview.svg)

VibeBench Arena 是一个面向 Codex-first 和 AI 辅助开发流程的本地验证工具。AI coding agent 可以很快生成代码，但开发者仍然需要一个清晰的本地质量门禁，判断这些改动是否适合进入 review、commit 和交付流程。

当前 v0.1.0 仍然保持小而清晰：CLI、配置初始化、命令检查、Git diff 风险分析、VibeScore，以及静态 HTML 报告。

## 为什么需要 VibeBench？

AI 生成代码提升了速度，也增加了审查压力。VibeBench 的目标是在“代码生成”和“准备提交”之间增加一个本地验收步骤，让开发者更快看见明显风险。

它的设计取向是：

- 本地优先，可以直接在现有仓库里运行
- 输出清晰，对 Python 工具链新手也友好
- 适合 Codex-first 工作流，但不替代人工 review
- 小步迭代，每个里程碑只增加一个明确能力

## 现在会检查什么？

VibeBench v0.1.0 已经支持：

- 通过 `.vibebench/config.yaml` 初始化项目配置
- 运行配置中的 test 和 lint 命令
- 计算 VibeScore 和风险等级
- 分析未提交改动的 Git diff 风险
- 生成适合本地 review 和截图的静态 HTML 报告
- 生成可粘贴到 PR / issue / code review 的 Markdown 摘要

Git diff 风险分析会标记：

- 删除测试文件
- 修改或新增 `.env`、`.env.*`、`secrets/` 路径
- 路径中包含 `token`、`api_key`、`password` 等疑似密钥关键词
- 修改 `package-lock.json`、`poetry.lock`、`uv.lock` 等 lockfile
- patch 行数超过配置阈值
- 一次改动超过 20 个文件

## 快速开始

```bash
python -m pip install -e ".[dev]"
python -m vibebench init
python -m vibebench check
python -m vibebench report
python -m vibebench pr-comment
```

默认配置示例：

```yaml
project:
  name: vibebench-project

checks:
  test:
    - pytest -q
  lint:
    - ruff check .

risk_rules:
  forbidden_paths:
    - .env
    - .env.*
    - secrets/
  warn_if_tests_deleted: true
  warn_if_lockfiles_changed: true
  large_patch_lines: 500
```

## 示例流程

```bash
# 第一次使用时创建配置
python -m vibebench init

# 提交前运行本地质量门禁
python -m vibebench check

# 生成静态 HTML 报告
python -m vibebench report

# 生成可粘贴到 PR 或 review 里的 Markdown 摘要
python -m vibebench pr-comment
```

`vibebench check` 会写入：

```text
.vibebench/runs/<timestamp>/metrics.json
.vibebench/runs/<timestamp>/check.log
```

`vibebench report` 会写入：

```text
.vibebench/runs/<timestamp>/report/index.html
```

`vibebench pr-comment` 会写入：

```text
.vibebench/runs/<timestamp>/pr-comment.md
```

## HTML 报告展示什么？

静态 HTML 报告不需要前端构建工具，适合本地查看、截图和 README 展示。它包含：

- 项目名和运行时间
- overall status、VibeScore、risk level
- test 和 lint 命令结果
- Git diff 风险发现
- changed files 和 patch lines 摘要
- 简短的 review / ship 建议

`.vibebench/runs/` 下的报告是本地运行产物，不应该提交到仓库。`docs/assets/report-preview.svg` 是专门用于 README 的静态预览图。

## PR Comment 摘要

`vibebench pr-comment` 会生成一份简洁的 Markdown 检查摘要，可以粘贴到 GitHub Pull Request、issue 或 code review 讨论里。它包含：

- overall status、VibeScore、risk level、项目名和运行时间
- 配置命令的执行结果
- Git diff 风险摘要计数
- 最多 10 条风险发现和相关路径
- 与 HTML 报告一致的 review / ship 建议

自动发布 GitHub PR comment 会在后续实现；当前命令只在本地生成文件，不调用 GitHub API。

## 试运行风险检测 Demo

一个干净的 100/100 报告很适合展示基础能力，但 VibeBench 的核心价值还包括：在 AI 生成代码进入交付前，发现那些看起来危险的改动。这个 demo 会创建一个临时仓库，先提交干净基线，然后故意制造几类未提交风险改动，让 VibeBench 去检测。

```bash
python examples/risk-demo/create_risky_repo.py
cd /tmp/vibebench-risk-demo
python -m vibebench check
python -m vibebench report
python -m vibebench pr-comment
```

这个 demo 会故意制造 `.env.local`、`secrets/`、删除测试、修改 lockfile、大 patch 等改动，用来证明 VibeBench 不只是跑测试，还能发现 AI 生成代码中的交付风险。因为包含 critical finding，`vibebench check` 预期会失败。

![VibeBench risk demo preview](docs/assets/risk-demo-preview.svg)

更多细节见 [examples/risk-demo/README.md](examples/risk-demo/README.md)。

## Roadmap

后续计划：

- 自动发布 GitHub PR comment
- GitHub Action integration
- multi-agent arena workflows
- AI 生成改动的 replay timeline

v0.1.0 不包含：

- 托管式 benchmark 排行榜
- 浏览器应用或 dashboard server
- multi-agent tournament system

## Built With A Codex-First Workflow

VibeBench Arena 围绕一个简单原则构建：

> Codex 负责写代码，VibeBench 负责验收。

这意味着小步迭代、测试清晰、实现可读，并把本地验证自然接入 AI 辅助开发流程。VibeBench 不替代人工 review，它让 review 有一个更可靠的起点。
