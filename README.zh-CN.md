# VibeBench Arena

**AI 生成代码提交前的本地质量门禁。**

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

VibeBench Arena 是一个面向 Codex-first 和 AI 辅助开发流程的本地验证工具。AI coding agent 可以很快生成代码，但开发者仍然需要一个清晰的本地质量门禁，判断这些改动是否适合进入 review、commit 和交付流程。

当前项目仍然坚持本地优先和小步迭代。v0.2.0 在原有本地质量门禁基础上，补充了更完整的 CI 编排、发布就绪检查、机器可读 artifacts，以及 GitHub Actions 可下载产物。

## 为什么需要 VibeBench？

AI 生成代码提升了速度，也增加了审查压力。VibeBench 的目标是在“代码生成”和“准备提交”之间增加一个本地验收步骤，让开发者更快看见明显风险。

它的设计取向是：

- 本地优先，可以直接在现有仓库里运行
- 输出清晰，对 Python 工具链新手也友好
- 适合 Codex-first 工作流，但不替代人工 review
- 小步迭代，每个里程碑只增加一个明确能力

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
- 修改或新增 `.env`、`.env.*`、`secrets/` 路径
- 路径中包含 `token`、`api_key`、`password` 等疑似密钥关键词
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
python -m vibebench package-check
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
```

`package-check` 会检查本地 package metadata、import、console script 入口和关键文档文件；它不会访问网络、不会发布到 PyPI，也不会调用 GitHub API。加上 `--write-json PATH` 或 `--write-summary PATH` 可持久化 `package-check.json` 和 `package-check.md`，方便 CI 和发布检查复用。

`vibebench config` 会输出最终生效的 project、checks、gate 和 risk 配置。`--json` 可输出机器可读 JSON，`--validate` 只做校验，`--check` 会执行一致性诊断，`--check --advice` 会给出修复建议，`--show-source` 会显示主要配置区域来自配置文件还是内置默认值。

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

risk:
  max_changed_files: 20
  max_patch_lines: 500
  forbidden_paths:
    - .env
    - .env.*
    - secrets/
  secret_like_paths:
    - "*secret*"
    - "*token*"
    - "*credential*"
    - "*credentials*"
    - "*private_key*"
    - "*api_key*"
    - "*apikey*"
    - "*password*"
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

# 将最新运行标记为项目 baseline
python -m vibebench baseline --set latest

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

`vibebench config --show` 会校验并汇总当前 `.vibebench/config.yaml`，包括项目名、配置的命令、gate 策略和 risk 策略。`python -m vibebench config --show --json` 可输出机器可读配置摘要。`python -m vibebench config --check`、`python -m vibebench config --check --advice` 或 `python -m vibebench config --check --json --advice` 可在完整流水线前执行配置一致性诊断并按需显示修复建议。加上 `--write-json PATH` 或 `--write-summary PATH` 可持久化 `config-check.json` 或 `config-check.md` artifact。

`vibebench doctor` 是轻量环境检查，会检查 Python、Git、配置有效性、配置命令是否可找到，以及 `.vibebench/runs/` 是否可写。它不会真正运行配置里的 test/lint 命令。`python -m vibebench doctor --strict` 会执行更强的发布/CI 预检，额外要求最近运行具备 manifest、bundle 和 report 等产物。加上 `--advice` 会显示简短修复建议但不会修改文件，例如 `python -m vibebench doctor --strict --advice`。可用 `python -m vibebench doctor --json`、`python -m vibebench doctor --json --strict` 或 `python -m vibebench doctor --json --strict --advice` 输出机器可读诊断结果。`vibebench release-check` 会把配置一致性、package readiness、strict doctor、最新运行、manifest 一致性、artifact inventory、CI plan 生成和 `git diff --check` 汇总成一个只读的发布前检查；`--json` 适合自动化，`--write-json PATH` 和 `--write-summary PATH` 可持久化 `release-check.json` 与 `release-check.md`。

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

`vibebench baseline --set latest` 会把某次运行保存为 `.vibebench/baseline.json` 中的 baseline。`vibebench compare --baseline` 会用这个 baseline 和最新运行对比。

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

`vibebench ci` 是推荐的 CI 入口。它会按顺序运行 check、gate、config check artifact、package-check artifacts、report、PR comment、explain、export、badge、status block、trend summaries、run-index artifacts、compare artifacts、manifest 检查、release-check artifacts、GitHub annotations、bundle 和 GitHub summary。默认最终通过/失败由 check 和 gate 决定；即使门禁失败，后续产物步骤也会尽量继续生成，方便排查。团队希望 CI 阻止 compare verdict 为 `regressed` 的情况时，可以加 `--fail-on-regression`，或在配置中设置 `compare.fail_on_regression: true`；`--no-fail-on-regression` 可临时关闭配置策略，`--skip-compare` 会跳过 compare step，因此也会覆盖这个 guard。默认仍输出适合人看的 Rich 表格；`--json` 适合自动化，`--json-output PATH` 可把同一份机器可读流水线结果写入文件。使用 `--dry-run` 或 `--plan` 可以只查看流水线顺序和 skip flag 效果，不运行检查也不写产物。加上 `--write-plan` 会把 `ci-plan.json` 和 `ci-plan.md` 写入类似运行目录的 `.vibebench/runs/<timestamp>_plan/`，也可以用 `--plan-json-output PATH` 和 `--plan-summary-output PATH` 指定输出位置。

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

GitHub PR comment 发布已经接入 GitHub Actions workflow，并且只在 `pull_request` 事件中运行。可以先用 `python -m vibebench pr-comment --post --dry-run` 本地预览。CI 中会用隐藏 marker 更新同一条评论，默认使用内置 `GITHUB_TOKEN`，并通过 `--no-fail-on-error` 避免 fork PR 权限受限时影响核心 VibeBench 门禁。

## 运行解释

`vibebench explain` 会为最新运行生成一份适合人读的 Markdown 解释：哪些命令通过或失败，Git diff 有哪些风险信号，发现意味着什么，以及下一步该怎么处理。

## GitHub Actions

`vibebench annotate` 会把可见的风险发现和命令失败输出成 GitHub Actions annotations。`vibebench gh-summary` 会在 `GITHUB_STEP_SUMMARY` 存在时写入 GitHub Actions step summary。workflow 只会在 `pull_request` 事件中发布或更新 VibeBench PR comment。

这个仓库已经在自己的 CI 里 dogfood VibeBench：直接运行 Ruff 和 pytest 后，CI 会继续运行 `vibebench ci`，按 `.vibebench/config.yaml` 中的策略执行明确门禁，并生成 config-check/report/comment/explanation/export/badge/status-block/trend/run-index/compare，包含 `config-check.json`、`config-check.md`、`trend.md`、`trend.json`、`run-index.json`、`run-index.md`、`compare.json` 和 `compare.md`，输出 annotations，打包运行产物，写入 summary，并把选定的 `.vibebench/runs` 输出上传为 `vibebench-run-artifacts` artifact。`vibebench init` 可以生成 `.github/workflows/vibebench.yml` starter workflow；可参考 [docs/examples/github-actions/vibebench.yml](docs/examples/github-actions/vibebench.yml)，更多说明见 [docs/github-actions.md](docs/github-actions.md)。

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

这个 demo 会故意制造 `.env.local`、`secrets/`、删除测试、修改 lockfile、大 patch 等改动，用来证明 VibeBench 不只是跑测试，还能发现 AI 生成代码中的交付风险。因为包含 critical finding，`vibebench check` 预期会失败。

![VibeBench risk demo preview](docs/assets/risk-demo-preview.svg)

更多细节见 [examples/risk-demo/README.md](examples/risk-demo/README.md)。

## 文档

- [Quickstart](docs/quickstart.md)
- [Risk rules](docs/risk-rules.md)
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
