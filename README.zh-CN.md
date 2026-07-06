# VibeBench Arena

**面向 Codex / vibe-coding 时代，把 AI 辅助改动变成可检查证据的本地质量控制台。**

> Codex 负责写代码，VibeBench 负责验收。

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

AI coding 正在变得更容易；真正困难的是 review、审计、对比和信任 AI 生成的改动。VibeBench Arena 是 Codex-first / vibe-coding 质量控制台，面向 AI coding 工程化，把 AI 辅助改动变成本地优先、可检查、可审计、可复现的工程证据。

它不是通用聊天机器人、RAG demo、纯 benchmark 项目、prompt 合集或 leaderboard。VibeBench 位于“agent 写完代码”和“人类决定合并或发布”之间，把“感觉能跑”变成检查、风险审阅、artifact-backed 摘要和 release readiness 记录。

![VibeBench flow](docs/assets/vibebench-flow.svg)

## 工作方式

1. 运行本地 showcase 或 CI plan：`python3 -m vibebench demo` 或 `python3 -m vibebench ci --dry-run`。
2. 检查 score、risk、diff 变化和 findings。
3. 审阅生成的 artifacts，把 AI coding changes 变成可检查、可审计、可复现的工程证据。
4. 使用 release audit 输出做发布就绪审查。

继续查看 [architecture](docs/architecture.md)、[artifact gallery](docs/artifact-gallery.md)、[product strategy](docs/product-strategy.md)、[commercial potential](docs/commercial-potential.md) 和 [public roadmap](docs/roadmap-public.md)。

## 快速判断

- [3 分钟外部 review](docs/review-hub.html)：公开 review hub 和 [reviewer guide](docs/reviewer-guide.md)，帮助外部评估者检查 proof、site preview 和 evidence-room artifacts。
- [Trust Center](docs/trust-center.html)：项目维护的 local-first、privacy、reproducibility 和 artifact safety 边界说明；不是第三方认证。
- [Security Questionnaire](docs/security-questionnaire.html)：项目维护的 adopter-facing Q&A，说明 local-first 行为、artifact sharing、CI uploads、static HTML safety、JSON purity 和 non-claims；不是第三方认证或审计。
- [5 分钟评估路径](docs/evaluate.md)：给开发者、团队、维护者和观察者一个紧凑路径，用来验证本地优先、证据优先、可审计、可复现的工作流。
- [Pages entry](docs/index.html)：GitHub Pages-ready 的公开入口；手动设置见 [Pages setup](docs/pages.md)。
- [Product showcase](docs/showcase.html)：一个 GitHub Pages-ready 的概览页，串起 CLI、CI 证据包、artifacts 和自包含 `proof.html`。
- [采用指南](docs/adoption.md)：适合评估 Codex / vibe-coding / AI 辅助编程工作流的小团队，说明第一周如何安全试点。
- [Demo guide](docs/demo.md)：用本地命令证明核心流程，不依赖外部服务。
- 一条命令生成 evidence room：`python3 -m vibebench evidence-room --output-dir PATH --zip`，然后先打开 `index.html`，按需查看 `share-check.md` 里的本地预分享扫描摘要，并用 `review-scorecard.html` 做中立 review checklist；evidence room 也包含 `share-check.json`。也可以运行 `python3 -m vibebench ci`，并可用 `python3 -m vibebench latest --artifact evidence-room-index-html --path-only` 定位。
- 用 `python3 -m vibebench regression-check` 对比 candidate run 和 baseline；稳定门禁建议先运行 `python3 -m vibebench ci --json`，再用 `python3 -m vibebench baseline --promote-latest --label stable --dry-run --json` 预演，检查通过后运行 `python3 -m vibebench baseline --promote-latest --label stable`。`--set-latest` 是直接/手动固定，`--promote-latest` 是带检查的安全路径；CI 不会自动 promote baseline。需要迁移到另一台机器时，可用 `python3 -m vibebench baseline --export --label stable --output baseline.json` 导出便携 snapshot，用 `python3 -m vibebench baseline --verify --input baseline.json --require-portable` 验证，再用 `python3 -m vibebench baseline --import baseline.json --label stable` 导入。
- 对外分享 evidence room、proof packet、static preview 或 zip 前，先运行 `python3 -m vibebench share-check PATH`；机器可读输出用 `python3 -m vibebench share-check PATH --json`。它只是本地预分享辅助，不是安全认证、第三方审计或保证，发布前仍需人工检查 artifacts。
- 打开 evidence room 里的 `trust-center.html` 或 [docs Trust Center](docs/trust-center.html)，查看 local-first、privacy、reproducibility 和 artifact safety 边界。
- 打开 evidence room 里的 `security-questionnaire.html` 或 [docs Security Questionnaire](docs/security-questionnaire.html)，查看面向 adopter 的 local-first、artifact sharing、CI uploads、static HTML safety、JSON purity 和 non-claims Q&A；它是项目维护文档，不是第三方认证或审计。
- 生成可分享的本地证据包：`python3 -m vibebench proof --output-dir .vibebench/proof-packet --zip` 会写入 Markdown、JSON、自包含、证据优先的 HTML 报告、manifest 和 `proof.zip`。GitHub Actions 也会显示 proof packet summary card，并上传可下载的 `vibebench-proof-packet` artifact。
- 发布或编辑静态 Pages 入口前，可运行 `python3 -m vibebench site-preview --output-dir /tmp/vibebench-site-preview --zip` 生成静态预览包，并用 `python3 -m vibebench site-preview --verify /tmp/vibebench-site-preview/site-preview.zip` 校验；CI 复用同一命令上传 `vibebench-site-preview`，但不会自动启用 GitHub Pages。
- [对比与定位](docs/comparison.md)：说明 VibeBench 不是普通 CI、不是聊天机器人、不是排行榜，而是面向 AI coding / vibe-coding 的本地质量控制台。
- [常见问题](docs/faq.md)：直接说明范围、边界、artifacts、local-first 和人工 review 的关系。
- [案例研究](docs/case-study.md)：展示 AI 生成代码如何变成可检查、可审计、可复现的证据。
- [证据制品](docs/artifact-gallery.md)：浏览 reviewers 可以检查的具体输出。
- [架构图](docs/architecture.md)：理解本地优先的 evidence flow。

这条路径适合快速判断 VibeBench 是否值得继续试用：运行 demo，检查 JSON 和 artifacts，阅读案例研究，再决定是否在一个小仓库里试点。它是 Codex-first / vibe-coding 质量控制台，不是虚假榜单，也不是自动发布工具。

## 案例研究

阅读 [案例研究：从 vibe-coding 改动到可审计证据](docs/case-study.md)，了解一次 AI 辅助改动如何通过 checks、risk scoring、artifacts、comparison 和 release readiness 变成可检查、可审计、可复现的 review packet。也可以直接查看已提交的 [case-study artifact folder](examples/showcase-artifacts/case-study/README.md)，它是一个静态示例，不夸大融资、高 star、客户或收入结果。

```bash
python3 -m vibebench demo
```

这条命令可以一条命令看到效果：它会展示 public showcase 路径，并指向仓库中已提交的示例 artifact pack。也可以运行 `python3 -m vibebench demo --copy-to /tmp/vibebench-demo`，把证据包复制到本地检查。

## 你会得到什么

- CI 风格检查和 dry-run 质量流水线，适合本地与 GitHub Actions。
- 风险和 diff review，用来提示可疑路径、删除测试、lockfile 变化和大范围 patch。
- 基于 artifacts 的摘要：Markdown、JSON、report preview、manifest、compare、badge、bundle，以及适合 GitHub review 的文本。
- Release / publish readiness 检查，生成本地 audit records，同时不隐藏发布、打 tag 或创建 GitHub Release。
- 面向 Codex-first / vibe-coding 团队的本地优先流程，保留人工 review，并留下可检查、可审计、可复现证据。

## 为什么不一样

VibeBench 是 AI 辅助编码周围的证据层。它不替代 coding agent，也不替代 reviewer；它记录发生了什么、跑了什么、改了什么，以及人接下来可以检查哪些 artifacts。

这让 GitHub 新访客也能快速理解项目：仓库本身就能展示质量控制台、一条命令 demo、artifact gallery 和 release-readiness 流程，不需要 hosted account 或外部服务。

## 产品假设

VibeBench 不是玩具 CLI，而是一个早期的本地优先产品方向：面向 AI coding 工程化，把 CLI、demo、artifact gallery、release readiness 和公开文档组织成 Codex-first / vibe-coding 质量控制台。

可以继续阅读 [product strategy](docs/product-strategy.md)、[public roadmap](docs/roadmap-public.md) 和 [commercial potential](docs/commercial-potential.md)，了解产品假设、为什么现在需要、公开路线图、商业化潜力和诚实边界。项目可以有野心，但不承诺融资、不伪造用户、不夸大商业结果，也不替代人工 review。

## 从这里开始

1. 运行一条命令 demo：`python3 -m vibebench demo`。
2. 按 [3 分钟外部 review](docs/review-hub.html) 或 [5 分钟评估路径](docs/evaluate.md) 快速检查，再打开 [采用指南](docs/adoption.md)、[demo guide](docs/demo.md) 和 [artifact gallery](docs/artifact-gallery.md)。
3. 检查已提交的 [示例 artifact pack](examples/showcase-artifacts/sample/README.md)，或用 `python3 -m vibebench demo --copy-to /tmp/vibebench-demo` 复制到本地。
4. 阅读 [案例研究](docs/case-study.md)、[对比与定位](docs/comparison.md)、[常见问题](docs/faq.md)、[architecture](docs/architecture.md)、[positioning](docs/positioning.md)、[use cases](docs/use-cases.md)、[product strategy](docs/product-strategy.md)、[public roadmap](docs/roadmap-public.md) 和 [commercial potential](docs/commercial-potential.md)，理解它为什么面向 Codex-first / vibe-coding 和 AI coding 工程化。
5. 通过 GitHub issue templates 提交真实使用场景、demo feedback，或发起小范围 PR。

编写有边界、低成本的 Codex 里程碑时，可以使用 [Codex task template](docs/codex-task-template.md)。

## 为什么存在？

AI coding agent 可以很快生成有用改动，但速度也会制造审查压力。VibeBench 在“代码生成”和“准备交付”之间加上一个本地质量门禁，让团队看到证据，而不是只凭感觉：

- 可复现的本地和 CI 检查
- 易读的 Markdown / JSON artifacts
- latest-run、compare、package、release-check 和 release-audit 记录
- 不替代人工 review，也没有隐藏的发布、打 tag 或 GitHub Release 副作用

## 帮助完善 VibeBench

如果你关心更好的 AI coding review、可审计 artifacts 和本地质量控制台，欢迎 star 这个仓库。也欢迎提交 Codex、Cursor、Claude Code、GitHub Copilot 等工具下的真实使用场景，反馈 demo 或 artifact gallery 中不清楚的地方，并通过小范围、可验证 PR 改进项目。

## 5 分钟能看到什么？

- 运行 `python3 -m vibebench demo` 查看本地 demo 和 checked-in 示例证据包。
- 运行 `python3 -m vibebench demo --json` 或 `python3 -m vibebench demo --copy-to /tmp/vibebench-demo`，用机器可读输出或复制方式检查示例 artifacts。
- 运行 `python3 -m vibebench ci --dry-run` 查看质量流水线计划。
- 运行 `python3 -m vibebench proof --output-dir /tmp/vibebench-proof --zip` 生成包含自包含、证据优先 `proof.html` 的可分享本地证据包，再运行 `python3 -m vibebench proof --verify /tmp/vibebench-proof/proof.zip` 校验证据包。GitHub Actions 也会显示 proof packet summary card，并上传同类证据包 artifact。
- 运行 `python3 -m vibebench ci` 生成本地 run artifacts。
- 运行 `python3 -m vibebench latest --all-paths` 查看最新输出路径。
- 运行 `python3 -m vibebench release-check` 查看发布就绪状态。
- 运行 `python3 -m vibebench release-audit --zip --output-dir /tmp/vibebench-release-audit-demo` 生成本地 audit bundle，不会发布包、打 tag 或创建 GitHub Release。

## VibeBench 会产出什么

VibeBench 不是只给一个 passed/failed，而是留下可检查、可对比、可审计、可复现的证据。这些证据可以进入本地 review、GitHub Actions、发布审计和人工决策。可继续查看 [artifact gallery](docs/artifact-gallery.md)、[示例 artifact pack](examples/showcase-artifacts/sample/README.md)、[public demo](docs/demo.md)、[quickstart demo](examples/quickstart-demo/README.md) 和 [showcase artifacts](examples/showcase-artifacts/README.md)。

| Artifact / Output | 用途 | 命令 | 为什么重要 |
| --- | --- | --- | --- |
| CI plan 和运行输出 | 预览或执行质量流水线。 | `python3 -m vibebench ci --dry-run --json` / `python3 -m vibebench ci` | 让检查在本地和 CI 中可复现。 |
| Artifact inventory 和 compare | 找到输出，并对比多次运行的变化。 | `python3 -m vibebench artifacts --json` / `python3 -m vibebench compare --json` | 把 AI 辅助改动变成可检查、可对比的证据。 |
| Release readiness 和 audit bundle | 记录 package、publish、checklist、release-body 和 audit 证据。 | `python3 -m vibebench release-check` / `python3 -m vibebench release-audit --zip` | 支持发布审计和人工决策，同时不发布包、不打 tag、不创建 GitHub Release。 |

## 现在会检查什么？

当前 VibeBench 已经支持：

- 通过 `.vibebench/config.yaml` 初始化项目配置
- 运行配置中的 test 和 lint 命令
- 计算 VibeScore 和风险等级
- 分析未提交改动的 Git diff 风险
- 生成适合本地 review 和截图的静态 HTML 报告
- 生成可粘贴到 PR / issue / code review 的 Markdown 摘要
- 生成兼容 Shields.io 的 badge artifact，适合 README、CI 和状态集成
- 生成面向 dashboard 和外部工具的机器可读 JSON / Markdown export
- 生成 GitHub Actions annotations 和 step summary，不需要 GitHub API

Git diff 风险分析会标记：

- 删除测试文件
- 修改或新增 `.env`、`.env.*` 或敏感本地路径
- 路径中包含 `credential`、`private_key`、`apikey` 等疑似凭据关键词
- 修改 `package-lock.json`、`poetry.lock`、`uv.lock` 等 lockfile
- patch 行数超过配置阈值
- 一次改动超过配置的文件数量阈值

这些 Git diff 规则可以在 `.vibebench/config.yaml` 的 `risk` 区域配置。

## 快速开始

```bash
python -m pip install -e ".[dev]"
python -m vibebench init
python -m vibebench config
python -m vibebench doctor
python -m vibebench release-check
python -m vibebench release-checklist
python -m vibebench release-checklist --write-json release-checklist.json
python -m vibebench release-checklist --write-summary release-checklist.md
python3 -m vibebench release-body --version v0.3.0 --check
python3 -m vibebench release-body --version v0.3.0 --output release-body.md
python -m vibebench release-audit
python3 -m vibebench release-audit --zip
python3 -m vibebench release-audit --zip-output release-audit.zip
python3 -m vibebench release-audit --verify release-audit.zip
python3 -m json.tool release-audit-manifest.json
python -m vibebench release-audit --output-dir .vibebench/release-audits/manual
python -m vibebench release-audit --version v0.3.0 --json
python -m vibebench package-check
python -m vibebench publish-check
python -m vibebench history
python -m vibebench latest
python -m vibebench latest --all-paths
python -m vibebench latest --artifact report --path-only
python -m vibebench trend
python -m vibebench baseline --set latest
python -m vibebench clean
python -m vibebench check
python -m vibebench gate
python -m vibebench ci
python -m vibebench report
python -m vibebench pr-comment
python -m vibebench explain
python -m vibebench bundle
python -m vibebench export
python -m vibebench badge
python -m vibebench badge --format markdown
python -m vibebench badge --format url
python -m vibebench status-block
python -m vibebench manifest
python -m vibebench run-index
python -m vibebench artifacts
python -m vibebench annotate
python -m vibebench gh-summary
python -m vibebench compare
```

`vibebench init` 会创建 `.vibebench/config.yaml` 和 `.github/workflows/vibebench.yml`。已有文件默认会跳过，只有传入 `--force` 才会覆盖；`--no-workflow` 和 `--workflow-only` 可用于只生成其中一部分。

如果要检查安装与打包准备情况，可以使用 editable install 和本地 metadata 检查：

```bash
python -m pip install -e .
python -m vibebench --help
python -m vibebench package-check
python -m vibebench package-check --json
python -m vibebench package-check --build
python -m vibebench publish-check
python -m vibebench publish-check --write-json publish-check.json
python -m vibebench publish-check --write-summary publish-check.md
```

`package-check` 会检查本地 package metadata、import、console script 入口和关键文档文件；它不会访问网络、不会发布到 PyPI，也不会调用 GitHub API。加上 `--build` 可在发布到 PyPI 或 GitHub Packages 前选择执行本地 package build readiness 检查；它默认写入临时目录并清理输出，不会上传或发布任何内容。`publish-check` 是发布 package 前的本地 dry-run readiness 检查，会检查 metadata、release notes、tag、package-check、package-check --build 和 release-check，但不会上传 package、创建 tag、创建 release 或 bump version。使用 `publish-check --write-json PATH` 或 `publish-check --write-summary PATH` 可保存本地 audit record，且不会发布或上传。加上 `package-check --write-json PATH` 或 `package-check --write-summary PATH` 可持久化 `package-check.json` 和 `package-check.md`，方便 CI 和发布检查复用。

`vibebench config` 会输出最终生效的 project、checks、gate 和 risk 配置。`--json` 可输出机器可读 JSON，`--validate` 只做校验，`--check` 会执行一致性诊断，`--check --advice` 会给出修复建议，`--show-source` 会显示主要配置区域来自配置文件还是内置默认值。 使用 `python3 -m vibebench config --init --dry-run` 可预览配置初始化；加上 `--json` 可输出机器可读 dry-run JSON。使用 `python3 -m vibebench config --init` 可以从 starter config 创建 `.vibebench/config.yaml`；默认拒绝覆盖。只有明确想让真实 init 覆盖已有配置时，才使用 `--force`。使用 `python3 -m vibebench config --example` 可以查看 starter config，使用 `python3 -m vibebench config --write-example .vibebench/config.example.yaml` 可以写入示例副本；starter 包含 `compare.fail_on_regression`。使用 `python3 -m vibebench config --path` 可在 `--init` 前后查看预期配置路径；加上 `--json` 会输出 `project_root`、`config_path` 和 `exists`。

简化配置示例：

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
    - sensitive/
  warn_if_tests_deleted: true
  warn_if_lockfiles_changed: true
  large_patch_lines: 500

risk:
  max_changed_files: 20
  max_patch_lines: 500
  forbidden_paths:
    - .env
    - .env.*
    - sensitive/
  credential_like_paths:
    - "*credential*"
    - "*credentials*"
    - "*private_key*"
    - "*apikey*"
    - "*passwd*"
  lockfiles:
    - package-lock.json
    - pnpm-lock.yaml
    - yarn.lock
    - poetry.lock
    - uv.lock
    - Pipfile.lock
    - requirements.lock
  test_path_patterns:
    - tests/
    - test_*.py
    - "*_test.py"
    - __tests__/
    - "*.test.ts"
    - "*.test.tsx"
    - "*.spec.ts"
    - "*.spec.tsx"

gate:
  min_score: 80
  max_risk: medium
  allow_findings: 0
  require_status_passed: true

regression:
  enabled: true
  baseline_label: stable
  require_baseline: true
  max_score_drop: 0.0
  max_risk_increase: 0.0
```

## 示例流程

```bash
# 第一次使用时创建配置
python -m vibebench init

# 查看并验证最终生效的配置
python -m vibebench config --show-source

# 检查当前项目是否已经准备好运行 VibeBench
python -m vibebench doctor

# 查看最近的 VibeBench 运行记录和质量趋势
python -m vibebench history
python -m vibebench trend
python -m vibebench trend --json
python -m vibebench trend --limit 3
python -m vibebench trend --write-summary

# 将最新运行标记为旧版 compare/gate baseline
python -m vibebench baseline --set latest

# 安全地将最新运行提升为稳定 regression-check baseline
python -m vibebench ci --json
python -m vibebench baseline --promote-latest --label stable --dry-run --json
python -m vibebench baseline --promote-latest --label stable
python -m vibebench baseline --show --label stable --json
python -m vibebench baseline --verify --label stable --require-portable --json
python -m vibebench baseline --export --label stable --output /tmp/vibebench-stable-baseline.json
python -m vibebench baseline --verify --input /tmp/vibebench-stable-baseline.json --json
python -m vibebench baseline --import /tmp/vibebench-stable-baseline.json --label stable
# 然后设置 regression.enabled=true 和 regression.baseline_label=stable
python -m vibebench ci --json
python -m vibebench ci --regression-check --baseline-label experimental --json

# 预览清理旧的本地运行记录
python -m vibebench clean

# 提交前运行本地质量门禁
python -m vibebench check

# 执行明确的通过/失败门禁阈值
python -m vibebench gate

# 运行完整本地 / CI 流水线
python -m vibebench ci

# 生成静态 HTML 报告
python -m vibebench report

# 生成可粘贴到 PR 或 review 里的 Markdown 摘要
python -m vibebench pr-comment

# 生成一份解释本次运行结果的 Markdown
python -m vibebench explain

# 将某次运行的产物打包成 zip
python -m vibebench bundle

# 导出给 dashboard 或外部工具使用的 JSON，也可导出 Markdown
python -m vibebench export
python -m vibebench export --format markdown

# 生成兼容 Shields.io 的 badge artifact
python -m vibebench badge
python -m vibebench badge --format markdown
python -m vibebench badge --format url
python -m vibebench badge --format markdown --label "VibeScore"

# 生成或更新 README 状态块
python -m vibebench status-block
python -m vibebench status-block --title "Project Quality"
python -m vibebench status-block --no-include-artifacts
python -m vibebench status-block --output README-status.md
python -m vibebench status-block --readme README.md --write-readme
python -m vibebench status-block --readme README.md --check-readme

# 索引最近运行，并查看一次运行生成了哪些 artifact
python -m vibebench run-index
python -m vibebench run-index --json
python -m vibebench compare
python -m vibebench compare --json
python -m vibebench artifacts
python -m vibebench artifacts --json
python -m vibebench artifacts --run-dir .vibebench/runs/<run-id>
python -m vibebench artifacts --only-available

# 为风险发现和命令失败输出 GitHub Actions annotations
python -m vibebench annotate

# 写入 GitHub Actions step summary，或生成本地 summary 文件
python -m vibebench gh-summary

# 对比最新一次和上一次 VibeBench 运行
python -m vibebench compare
```

`vibebench config --show` 会校验并汇总当前 `.vibebench/config.yaml`，包括项目名、配置的命令、gate 策略和 risk 策略。 使用 `python3 -m vibebench config --init --dry-run` 可预览配置初始化；加上 `--json` 可输出机器可读 dry-run JSON。使用 `python3 -m vibebench config --init` 可以从 starter config 创建 `.vibebench/config.yaml`；默认拒绝覆盖。只有明确想让真实 init 覆盖已有配置时，才使用 `--force`。使用 `python3 -m vibebench config --example` 可以查看 starter config，使用 `python3 -m vibebench config --write-example .vibebench/config.example.yaml` 可以写入示例副本；starter 包含 `compare.fail_on_regression`。使用 `python3 -m vibebench config --path` 可在 `--init` 前后查看预期配置路径；加上 `--json` 会输出 `project_root`、`config_path` 和 `exists`。`python -m vibebench config --show --json` 可输出机器可读配置摘要。`python -m vibebench config --check`、`python -m vibebench config --check --advice` 或 `python -m vibebench config --check --json --advice` 可在完整流水线前执行配置一致性诊断并按需显示修复建议。加上 `--write-json PATH` 或 `--write-summary PATH` 可持久化 `config-check.json` 或 `config-check.md` artifact。

`vibebench doctor` 是轻量环境检查，会检查 Python、Git、配置有效性、配置命令是否可找到，以及 `.vibebench/runs/` 是否可写。它不会真正运行配置里的 test/lint 命令。`python -m vibebench doctor --strict` 会执行更强的发布/CI 预检，额外要求最近运行具备 manifest、bundle 和 report 等产物。加上 `--advice` 会显示简短修复建议但不会修改文件，例如 `python -m vibebench doctor --strict --advice`。可用 `python -m vibebench doctor --json`、`python -m vibebench doctor --json --strict` 或 `python -m vibebench doctor --json --strict --advice` 输出机器可读诊断结果。`vibebench release-check` 会把配置一致性、package readiness、strict doctor、最新运行、manifest 一致性、artifact inventory、CI plan 生成和 `git diff --check` 汇总成一个只读的发布前检查；`--json` 适合自动化，`--write-json PATH` 和 `--write-summary PATH` 可持久化 `release-check.json` 与 `release-check.md`。`vibebench release-checklist` 会输出指定版本的只读发布 checklist，可用于打 tag 前后检查，并且不会创建 tag、release、发布/上传 package 或 bump version；加上 `--write-json PATH` 或 `--write-summary PATH` 可保存本地 release audit record。`vibebench release-body` 会从 `RELEASE_NOTES_vX.Y.Z.md` 准备可复制到 GitHub Release 的正文；`--check` 会检查残留的 release-candidate 文案。它只在本地运行，绝不会创建 tag、GitHub Release、上传、发布、bump version 或安装依赖。`vibebench release-audit` 会创建本地 audit 文件夹，包含 package-check、publish-check、release-checklist、release-body、汇总 audit artifacts 和 `release-audit-manifest.json` checksum；bundle 会包含 `release-body.md` 和 `release-body.json`，便于本地 release handoff/audit 使用。可按需使用 `--output-dir PATH`、`--version VERSION` 或 `--json`。加上 `python3 -m vibebench release-audit --zip` 可创建本地 `release-audit.zip`，或用 `python3 -m vibebench release-audit --zip-output PATH` 指定 archive 路径。使用 `python3 -m vibebench release-audit --verify PATH` 可只读校验 release audit 文件夹或 zip；如果 manifest 存在，也会校验 checksum。它只在本地运行，不会创建 tag、GitHub Release、调用 GitHub API、发布/上传 package、bump version 或安装依赖。

`vibebench history` 会显示 `.vibebench/runs/` 下最近的运行记录，包括分数、风险等级、diff 规模、风险发现数量和产物生成状态。

`vibebench latest` 会定位最新的有效运行及其已知产物。`--json` 适合自动化，`--all-paths` 可一次输出所有可用产物路径，方便脚本、本地排查和查看下载后的 CI artifacts；`--artifact NAME` 可查看单个产物，`--path-only` 配合 `--artifact` 可只输出一个可用产物路径。

`vibebench trend` 会按最新优先汇总最近多次运行，并判断选定窗口内的质量趋势是 `improved`、`stable` 还是 `regressed`。它会比较最新与最旧运行的分数、风险等级和风险发现数量。`--json`、`--limit N` 和 `--runs-dir PATH` 适合自动化和分析归档运行；`--write-summary` 会把面向阅读的 Markdown 摘要写入 `.vibebench/runs/<timestamp>/trend.md`，`--write-json` 会写入机器可读的 `trend.json`；`--output PATH` 和 `--json-output PATH` 可分别指定 Markdown 和 JSON 输出位置。

`vibebench run-index` 会生成最近运行目录的宽容索引：有效运行、半成品目录和损坏 metrics 都会被清楚标记，而不是让命令崩溃。`--json` 适合自动化，`--limit N` 和 `--runs-dir PATH` 可选择索引范围，`--write-json PATH` / `--write-summary PATH` 可持久化 `run-index.json` 和 `run-index.md`。`vibebench ci` 默认会生成这两个文件，除非使用 `--skip-run-index`。

`vibebench compare` 会把最新有效运行和上一个有效运行进行比较，并在 head 运行目录写入 `compare.json` 和 `compare.md`。默认它只是报告命令，即使 verdict 是 `regressed` 或 `insufficient-data` 也会成功退出。需要让自动化阻止退化时，加上 `--fail-on-regression`；只有 `regressed` 会非零退出，`insufficient-data`、`improved`、`stable` 和 `mixed` 仍会通过。`--json` 输出纯 JSON，`--write-json PATH` / `--write-summary PATH` 可指定输出位置，`--runs-dir PATH` 可指定运行目录，也可用 `--base-run-dir PATH` 和 `--head-run-dir PATH`，或 `--base RUN_ID` 和 `--head RUN_ID` 精确选择。

对 `vibebench ci` 来说，compare 退化失败是显式开启的策略。默认 CI 只报告 compare 结果。严格模式可以使用 `python -m vibebench ci --fail-on-regression`，也可以在 `.vibebench/config.yaml` 中持久配置：

```yaml
compare:
  fail_on_regression: true
```

需要临时关闭配置中的 guard 时，使用 `python -m vibebench ci --no-fail-on-regression`。`--skip-compare` 会完全跳过 compare，因此也会关闭 compare 退化失败。

`vibebench baseline --set latest` 会把某次运行保存为 `.vibebench/baseline.json` 中的旧版 compare/gate baseline。用于 regression-check 时，`vibebench baseline --set-latest --label stable` 会直接写入本地固定 baseline；`vibebench baseline --promote-latest --label stable` 会先检查 candidate run、metrics、已有 manifest，以及相对当前 label 的 regression-check，再写入 `.vibebench/baselines/stable.json`。带 `regression.enabled: true` 的配置化 `vibebench ci --json` 会使用它，再考虑自动上一个 run 推断。`--baseline-label`、`--max-score-drop` 和 `--require-baseline` 等 CLI flag 会覆盖配置。promote 后的 pinned baseline 会包含精简 metrics snapshot；`baseline --verify --label stable` 会检查 pinned baseline 是否可用于回归门禁，`baseline --verify --input PATH` 会在不写入生成状态的情况下检查导出的文件，`--require-portable` 要求 snapshot fallback，`--require-live-metrics` 要求原始 run metrics 仍可用。`baseline --export --label stable --output PATH` 默认不写入本机绝对路径，`baseline --import PATH --label stable` 可让清理后的 workspace 或类 CI checkout 在原 run 目录缺失时继续使用该 baseline。verify 不会提交或发布生成的 baseline 状态。

`vibebench clean` 会安全预览旧运行记录的清理计划。默认只是 dry-run，只有显式传入 `--yes` 才会删除。

`vibebench gate` 会把已有运行结果转换成明确的通过/失败决策，适合本地或 CI 使用。门禁阈值可以写在 `.vibebench/config.yaml` 里；`--min-score`、`--max-risk` 等 CLI 参数会覆盖配置，只影响本次运行。加上 `--baseline` 后，还会阻止相对 baseline 的退化。

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

`vibebench explain` 会写入：

```text
.vibebench/runs/<timestamp>/explain.md
```

它会解释命令失败、Git diff 风险信号、风险发现，以及下一步建议。可以配合 `--run-dir`、`--output` 或 `--no-write` 做本地审阅。

`vibebench manifest` 会写入 `.vibebench/runs/<timestamp>/manifest.json`，这是面向自动化和 CI 消费者的机器可读运行索引，包含状态、分数、风险、diff 规模、风险发现数量和已知产物可用性。`vibebench manifest --check` 可验证已有 manifest 是否仍和运行目录一致。`vibebench ci` 默认会生成并校验它，除非使用 `--skip-manifest`。

`vibebench bundle` 会写入：

```text
.vibebench/runs/<timestamp>/vibebench-bundle.zip
```

它会把一次运行的标准产物打包，方便分享、下载或在 CI artifact 中查看。`--run-dir` 可指定运行目录，`--output` 可指定 zip 路径，`--include-report-assets` 会递归包含完整 report 目录，`--strict` 会在任何标准产物缺失时失败。

`vibebench export` 默认输出稳定的机器可读 JSON，适合 dashboard、badge 和外部工具读取。`--pretty` 可以输出缩进 JSON，`--format markdown` 可生成轻量 Markdown，`--output` 可写入文件。`vibebench ci` 默认会写入 `.vibebench/runs/<timestamp>/export.json`。

`vibebench badge` 默认写入兼容 Shields.io endpoint 的 `.vibebench/runs/<timestamp>/badge.json`。`--format markdown` 会写入可直接复制到 README 的 `badge.md`，`--format url` 会写入静态 Shields URL 到 `badge-url.txt`。`--label` 会作用于所有格式，`--output` 可指定当前格式的输出位置。`vibebench ci` 默认会生成 `badge.json` 和 `badge.md`。

`vibebench status-block` 会写入 `.vibebench/runs/<timestamp>/status-block.md`，内容是可直接复制到 README 的状态区块，包含状态、分数、风险等级、diff 规模、风险发现、badge 和已生成产物。可用 `--title`、`--no-include-badge`、`--no-include-artifacts` 或 `--output` 自定义。也可以在 README 中加入 `<!-- VIBEBENCH_STATUS_START -->` 和 `<!-- VIBEBENCH_STATUS_END -->` 标记，然后运行 `python -m vibebench status-block --readme README.md --write-readme` 只更新标记之间的内容；在只读校验场景中可用 `--check-readme` 检查状态块是否过期。

`vibebench artifacts` 会列出最新运行的已知文件，包括 metrics、日志、报告、config check、package-check、release-check、summary、trend summary、run-index、compare、badge、status block、bundle 和 compare。`--json` 适合自动化，`--run-dir .vibebench/runs/<run-id>` 可指定运行，`--only-available` 只显示已存在文件，`--strict` 则会在任何已知 artifact 缺失时失败。

`vibebench annotate` 会根据最新运行中的命令失败和风险发现输出 GitHub Actions annotations。使用 `--no-github-actions` 可以输出普通文本。它只负责展示，不决定通过/失败；真正的门禁仍由 `vibebench gate` 负责。

`vibebench compare` 会写入：

```text
.vibebench/runs/<latest-timestamp>/compare.json
.vibebench/runs/<latest-timestamp>/compare.md

`vibebench latest --artifact compare-json --path-only` 和 `vibebench latest --artifact compare-md --path-only` 可以定位最新运行的 compare artifact。

```

它会对比最新一次和上一次运行，包括分数、风险等级、命令数量、diff 规模和风险发现数量。加上 `--fail-on-regression` 后，它会从报告命令变成可选的自动化门禁。

## 一键 CI 流水线

`vibebench ci` 是推荐的 CI 入口。它会按顺序运行 check、gate、config check artifact、package-check artifacts、report、PR comment、explain、export、badge、status block、trend summaries、run-index artifacts、compare artifacts、evidence-room、manifest 检查、release-check artifacts、GitHub annotations、bundle 和 GitHub summary。默认最终通过/失败由 check 和 gate 决定；即使门禁失败，后续产物步骤也会尽量继续生成，方便排查。团队希望 CI 阻止 compare verdict 为 `regressed` 的情况时，可以加 `--fail-on-regression`，或在配置中设置 `compare.fail_on_regression: true`；`--no-fail-on-regression` 可临时关闭配置策略，`--skip-compare` 会跳过 compare step，因此也会覆盖这个 guard。`--skip-evidence-room` 只跳过本地 evidence-room artifact。默认仍输出适合人看的 Rich 表格；`--json` 适合自动化，`--json-output PATH` 可把同一份机器可读流水线结果写入文件。使用 `--dry-run` 或 `--plan` 可以只查看流水线顺序和 skip flag 效果，不运行检查也不写产物。加上 `--write-plan` 会把 `ci-plan.json` 和 `ci-plan.md` 写入类似运行目录的 `.vibebench/runs/<timestamp>_plan/`，也可以用 `--plan-json-output PATH` 和 `--plan-summary-output PATH` 指定输出位置。

常用选项包括 `--dry-run`、`--plan`、`--write-plan`、`--plan-json-output PATH`、`--plan-summary-output PATH`、`--json`、`--json-output PATH`、`--fail-on-regression`、`--no-fail-on-regression`、`--skip-report`、`--skip-pr-comment`、`--skip-explain`、`--skip-export`、`--skip-badge`、`--skip-status-block`、`--skip-trend`、`--skip-run-index`、`--skip-compare`、`--skip-config-check`、`--skip-package-check`、`--skip-release-check`、`--skip-bundle`、`--skip-annotate`、`--skip-gh-summary`、`--bundle-include-report-assets` 和 `--bundle-strict`。`--min-score`、`--max-risk`、`--allow-findings`、`--no-require-status-passed` 会传递给 gate。使用 `--run-dir .vibebench/runs/<run-id>` 可以针对已有运行生成产物并执行门禁，不再创建新的 check run。

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

GitHub PR comment 发布已经接入 GitHub Actions workflow，并且只在 `pull_request` 事件中运行。可以先用 `python -m vibebench pr-comment --post --dry-run` 本地预览。CI 中会用隐藏 marker 更新同一条评论，默认使用 GitHub Actions 内置凭据，并通过 `--no-fail-on-error` 避免 fork PR 权限受限时影响核心 VibeBench 门禁。

## 运行解释

`vibebench explain` 会为最新运行生成一份适合人读的 Markdown 解释：哪些命令通过或失败，Git diff 有哪些风险信号，发现意味着什么，以及下一步该怎么处理。

## GitHub Actions

`vibebench annotate` 会把可见的风险发现和命令失败输出成 GitHub Actions annotations。`vibebench gh-summary` 会在 `GITHUB_STEP_SUMMARY` 存在时写入 GitHub Actions step summary。workflow 只会在 `pull_request` 事件中发布或更新 VibeBench PR comment。

这个仓库已经在自己的 CI 里 dogfood VibeBench：直接运行 Ruff 和 pytest 后，CI 会继续运行 `vibebench ci`，按 `.vibebench/config.yaml` 中的策略执行明确门禁，并生成 config-check/report/comment/explanation/export/badge/status-block/trend/run-index/compare/evidence-room，包含 `config-check.json`、`config-check.md`、`trend.md`、`trend.json`、`run-index.json`、`run-index.md`、`compare.json`、`compare.md` 和 `evidence-room/evidence-room.html`，输出 annotations，打包运行产物，写入 summary，把选定的 `.vibebench/runs` 输出上传为 `vibebench-run-artifacts` artifact，显示 proof packet summary card，上传包含 `proof.html`、`proof.json`、`proof.md`、`proof-manifest.json` 和 `proof.zip` 的 `vibebench-proof-packet` artifact，运行 `python3 -m vibebench site-preview --output-dir .vibebench/site-preview --zip` 并上传 `vibebench-site-preview`，运行 `python3 -m vibebench evidence-room --output-dir .vibebench/evidence-room --zip` 并上传 `vibebench-evidence-room`。`vibebench init` 可以生成 `.github/workflows/vibebench.yml` starter workflow；可参考 [docs/examples/github-actions/vibebench.yml](docs/examples/github-actions/vibebench.yml)，更多说明见 [docs/github-actions.md](docs/github-actions.md)。

## 发布就绪与 CI Artifacts

v0.2.0 的发布说明见 [RELEASE_NOTES_v0.2.0.md](RELEASE_NOTES_v0.2.0.md)。后续准备新的 tag 或发布前，建议先运行 `python -m vibebench ci`、`python -m vibebench release-check` 和 `python -m vibebench doctor --strict`。如果只想查看流水线计划，可以先用 `python -m vibebench ci --dry-run` 或 `python -m vibebench ci --dry-run --write-plan`。

GitHub Actions 会上传名为 `vibebench-run-artifacts` 的可下载 artifact。里面可能包含 run manifest、bundle zip、HTML report、GitHub summary、config-check artifacts、package-check artifacts、trend artifacts、run-index artifacts、compare artifacts，以及用于发布前检查的 `release-check.json` 和 `release-check.md`。

## 试运行风险检测 Demo

一个干净的 100/100 报告很适合展示基础能力，但 VibeBench 的核心价值还包括：在 AI 生成代码进入交付前，发现那些看起来危险的改动。这个 demo 会创建一个临时仓库，先提交干净基线，然后故意制造几类未提交风险改动，让 VibeBench 去检测。

```bash
python examples/risk-demo/create_risky_repo.py
cd /tmp/vibebench-risk-demo
python -m vibebench check
python -m vibebench gate
python -m vibebench ci
python -m vibebench report
python -m vibebench pr-comment
python -m vibebench explain
python -m vibebench bundle
```

这个 demo 会故意制造 `.env.local`、敏感本地目录、删除测试、修改 lockfile、大 patch 等改动，用来证明 VibeBench 不只是跑测试，还能发现 AI 生成代码中的交付风险。因为包含 critical finding，`vibebench check` 预期会失败。

![VibeBench risk demo preview](docs/assets/risk-demo-preview.svg)

更多细节见 [examples/risk-demo/README.md](examples/risk-demo/README.md)。

## 文档

- [Quickstart](docs/quickstart.md)
- [Risk rules](docs/risk-rules.md)
- [Architecture](docs/architecture.md)
- [Product strategy](docs/product-strategy.md)
- [Public roadmap](docs/roadmap-public.md)
- [Commercial potential](docs/commercial-potential.md)
- [GitHub Actions](docs/github-actions.md)
- [Contributing](CONTRIBUTING.md)
- [Security](SECURITY.md)
- [Changelog](CHANGELOG.md)
- [v0.2.0 发布说明](RELEASE_NOTES_v0.2.0.md)
- [Roadmap](ROADMAP.md)
- [GitHub PR comment 设计](docs/pr-comments.md)

## Roadmap

v0.3.0 的路线图会把重点从本地/CI 验证推进到更协作化的 GitHub 原生 review 流程。优先方向包括安装与打包准备、初始化模板打磨、artifact/report 体验，以及 policy presets。完整计划见 [ROADMAP.md](ROADMAP.md)，GitHub PR comment 行为见 [docs/pr-comments.md](docs/pr-comments.md)。

## Built With A Codex-First Workflow

VibeBench Arena 围绕一个简单原则构建：

> Codex 负责写代码，VibeBench 负责验收。

这意味着小步迭代、测试清晰、实现可读，并把本地验证自然接入 AI 辅助开发流程。VibeBench 不替代人工 review，它让 review 有一个更可靠的起点。
