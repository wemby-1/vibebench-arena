"""Static HTML report generation for VibeBench runs."""

from __future__ import annotations

import json
from html import escape
from pathlib import Path
from typing import Any

from vibebench.paths import config_dir


class ReportError(Exception):
    """User-readable report generation error."""


def find_latest_run(project_root: Path) -> Path:
    """Return the latest VibeBench run directory."""
    runs_dir = config_dir(project_root) / "runs"
    if not runs_dir.exists():
        raise ReportError("No VibeBench runs found. Run 'vibebench check' first.")

    run_dirs = sorted(path for path in runs_dir.iterdir() if path.is_dir())
    if not run_dirs:
        raise ReportError("No VibeBench runs found. Run 'vibebench check' first.")
    return run_dirs[-1]


def load_metrics(run_dir: Path) -> dict[str, Any]:
    """Load metrics.json from a run directory."""
    metrics_path = run_dir / "metrics.json"
    if not metrics_path.exists():
        raise ReportError(f"No metrics.json found in {run_dir}.")
    return json.loads(metrics_path.read_text(encoding="utf-8"))


def read_check_log(run_dir: Path) -> str | None:
    """Read check.log if it exists."""
    log_path = run_dir / "check.log"
    if not log_path.exists():
        return None
    return log_path.read_text(encoding="utf-8")


def recommendation_for(metrics: dict[str, Any]) -> str:
    """Return a short recommendation for a metrics payload."""
    score = int(metrics.get("score", 0))
    status = str(metrics.get("overall_status", "failed"))
    if score >= 85 and status == "passed":
        return "Looks safe to review and ship, assuming the behavior is correct."
    if score >= 65:
        return "Review carefully before shipping."
    if score >= 40:
        return "High risk. Investigate findings before shipping."
    return "Do not ship until failures are resolved."


def generate_report(project_root: Path, run_dir: Path | None = None) -> Path:
    """Generate report/index.html for a run and return its path."""
    selected_run_dir = (run_dir or find_latest_run(project_root)).resolve()
    metrics = load_metrics(selected_run_dir)
    check_log = read_check_log(selected_run_dir)
    report_dir = selected_run_dir / "report"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / "index.html"
    report_path.write_text(
        render_html(metrics, selected_run_dir, check_log),
        encoding="utf-8",
    )
    return report_path


def render_html(
    metrics: dict[str, Any],
    run_dir: Path,
    check_log: str | None = None,
) -> str:
    """Render a complete static HTML report."""
    project_name = text(metrics.get("project_name", "Unknown project"))
    created_at = text(metrics.get("created_at", "Unknown time"))
    status = text(metrics.get("overall_status", "unknown"))
    score = int(metrics.get("score", 0))
    risk_level = text(metrics.get("risk_level", "unknown"))
    summary = as_dict(metrics.get("summary"))
    diff = as_dict(metrics.get("diff_analysis"))
    findings = as_list(metrics.get("risk_findings"))
    commands = as_list(metrics.get("command_results"))
    recommendation = recommendation_for(metrics)

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>VibeBench Arena Report - {escape(project_name)}</title>
  <style>
{styles()}
  </style>
</head>
<body>
  <main class="page">
    <section class="hero">
      <p class="eyebrow">VibeBench Arena</p>
      <h1>Codex-first quality gate for vibe coding projects.</h1>
      <div class="hero-meta">
        <span>{escape(project_name)}</span>
        <span>{escape(created_at)}</span>
      </div>
      <div class="hero-score">
        <div>
          <span class="label">Overall Status</span>
          {badge(status)}
        </div>
        <div>
          <span class="label">VibeScore</span>
          <strong>{score}</strong>
        </div>
        <div>
          <span class="label">Risk Level</span>
          {badge(risk_level)}
        </div>
      </div>
    </section>

    <section class="grid cards">
      {summary_card("Overall", status)}
      {summary_card("Score", score)}
      {summary_card("Risk", risk_level)}
      {summary_card("Commands", summary.get("total_commands", 0))}
      {summary_card("Passed", summary.get("passed_commands", 0))}
      {summary_card("Failed", summary.get("failed_commands", 0))}
      {summary_card("Changed Files", diff.get("changed_file_count", 0))}
      {summary_card("Patch Lines", diff.get("total_patch_lines", 0))}
      {summary_card("Findings", len(findings))}
    </section>

    <section class="panel">
      <div class="section-head">
        <h2>Command Results</h2>
        <p>Configured checks from <code>.vibebench/config.yaml</code>.</p>
      </div>
      {command_table(commands)}
    </section>

    <section class="panel">
      <div class="section-head">
        <h2>Risk Findings</h2>
        <p>Signals from the current Git working-tree diff.</p>
      </div>
      {findings_section(findings)}
    </section>

    <section class="panel">
      <div class="section-head">
        <h2>Git Diff Summary</h2>
        <p>Uncommitted changes analyzed against <code>HEAD</code>.</p>
      </div>
      {diff_summary(diff)}
    </section>

    <section class="panel recommendation">
      <div class="section-head">
        <h2>Recommendation</h2>
      </div>
      <p>{escape(recommendation)}</p>
      <p class="muted">Full command output is kept in <code>{escape(str(run_dir / 'check.log'))}</code>{log_note(check_log)}</p>
    </section>

    <footer>
      <span>Generated by VibeBench Arena</span>
      <span>Codex writes code. VibeBench verifies it.</span>
    </footer>
  </main>
</body>
</html>
"""


def styles() -> str:
    """Return the embedded report CSS."""
    return r"""
:root {
  color-scheme: light;
  --bg: #f6f7f9;
  --ink: #17202a;
  --muted: #667085;
  --panel: #ffffff;
  --line: #d9dee7;
  --green: #127c56;
  --red: #b42318;
  --yellow: #a15c07;
  --magenta: #9f1f63;
  --blue: #245db8;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  background: var(--bg);
  color: var(--ink);
  font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  line-height: 1.5;
}
.page { width: min(1180px, calc(100% - 48px)); margin: 0 auto; padding: 32px 0; }
.hero {
  background: #101828;
  color: white;
  border-radius: 8px;
  padding: 34px;
  box-shadow: 0 18px 55px rgba(16, 24, 40, 0.18);
}
.eyebrow { margin: 0 0 10px; color: #b9c5d8; font-weight: 700; text-transform: uppercase; font-size: 12px; letter-spacing: 0; }
h1 { margin: 0; font-size: 36px; line-height: 1.1; letter-spacing: 0; }
.hero-meta { display: flex; gap: 18px; flex-wrap: wrap; margin-top: 18px; color: #d7deeb; }
.hero-score { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 14px; margin-top: 28px; }
.hero-score > div, .card, .panel { background: var(--panel); border: 1px solid var(--line); border-radius: 8px; }
.hero-score > div { color: var(--ink); padding: 18px; }
.label { display: block; color: var(--muted); font-size: 13px; font-weight: 650; margin-bottom: 8px; }
.hero-score strong { font-size: 34px; line-height: 1; }
.grid { display: grid; gap: 12px; }
.cards { grid-template-columns: repeat(9, minmax(0, 1fr)); margin-top: 16px; }
.card { padding: 16px; min-height: 92px; }
.card strong { display: block; font-size: 24px; margin-top: 6px; overflow-wrap: anywhere; }
.panel { margin-top: 16px; padding: 24px; }
.section-head { display: flex; justify-content: space-between; gap: 18px; align-items: end; margin-bottom: 16px; }
h2 { margin: 0; font-size: 22px; }
p { margin: 0; }
.muted, .section-head p { color: var(--muted); }
code { background: #eef2f7; border: 1px solid #d7deea; border-radius: 4px; padding: 1px 5px; }
table { width: 100%; border-collapse: collapse; }
th, td { text-align: left; border-bottom: 1px solid var(--line); padding: 12px 10px; vertical-align: top; }
th { color: var(--muted); font-size: 12px; text-transform: uppercase; letter-spacing: 0; }
.badge { display: inline-flex; align-items: center; border-radius: 999px; padding: 4px 10px; font-weight: 750; font-size: 13px; }
.badge.passed, .badge.low { background: #dcfae6; color: var(--green); }
.badge.failed, .badge.critical { background: #fee4e2; color: var(--red); }
.badge.medium, .badge.warning { background: #fef0c7; color: var(--yellow); }
.badge.high { background: #fce7f3; color: var(--magenta); }
.findings { display: grid; gap: 12px; }
.finding { border: 1px solid var(--line); border-left: 5px solid var(--blue); border-radius: 8px; padding: 14px; }
.finding.critical { border-left-color: var(--red); }
.finding.high { border-left-color: var(--magenta); }
.finding.warning { border-left-color: var(--yellow); }
.finding.info { border-left-color: var(--blue); }
.finding-head { display: flex; gap: 10px; flex-wrap: wrap; align-items: center; margin-bottom: 8px; }
.path-list { margin: 8px 0 0; padding-left: 20px; color: var(--muted); }
.diff-grid { display: grid; grid-template-columns: 280px 1fr; gap: 16px; }
.metric-list { display: grid; gap: 8px; }
.metric-row { display: flex; justify-content: space-between; gap: 12px; border-bottom: 1px solid var(--line); padding-bottom: 8px; }
.file-groups { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px; }
.file-group h3 { margin: 0 0 8px; font-size: 15px; }
.file-group ul { margin: 0; padding-left: 20px; color: var(--muted); }
.recommendation { border-left: 5px solid var(--blue); }
footer { display: flex; justify-content: space-between; gap: 18px; flex-wrap: wrap; color: var(--muted); padding: 24px 4px 0; }
@media (max-width: 900px) {
  .page { width: min(100% - 24px, 1180px); padding: 16px 0; }
  h1 { font-size: 30px; }
  .hero-score, .cards, .diff-grid, .file-groups { grid-template-columns: 1fr; }
  .section-head { display: block; }
  table { display: block; overflow-x: auto; white-space: nowrap; }
}
"""


def summary_card(label: str, value: object) -> str:
    """Render a summary card."""
    return (
        f'<div class="card"><span class="label">{escape(label)}</span>'
        f"<strong>{escape(text(value))}</strong></div>"
    )


def command_table(commands: list[Any]) -> str:
    """Render command results table."""
    rows = []
    for command in commands:
        item = as_dict(command)
        rows.append(
            "<tr>"
            f"<td>{escape(text(item.get('group', '')))}</td>"
            f"<td><code>{escape(text(item.get('command', '')))}</code></td>"
            f"<td>{badge(text(item.get('status', 'unknown')))}</td>"
            f"<td>{escape(text(item.get('exit_code', '')))}</td>"
            f"<td>{escape(format_duration(item.get('duration_seconds', 0)))}</td>"
            "</tr>"
        )
    body = "".join(rows) or '<tr><td colspan="5">No commands were configured.</td></tr>'
    return (
        "<table><thead><tr><th>Group</th><th>Command</th><th>Status</th>"
        "<th>Exit Code</th><th>Duration</th></tr></thead><tbody>"
        f"{body}</tbody></table>"
    )


def findings_section(findings: list[Any]) -> str:
    """Render risk findings."""
    if not findings:
        return '<p class="muted">No risk findings detected.</p>'

    rendered = []
    for finding in findings:
        item = as_dict(finding)
        severity = text(item.get("severity", "info"))
        paths = as_list(item.get("paths"))
        path_html = ""
        if paths:
            path_html = "<ul class=\"path-list\">" + "".join(
                f"<li>{escape(text(path))}</li>" for path in paths
            ) + "</ul>"
        rendered.append(
            f'<article class="finding {escape(severity)}">'
            '<div class="finding-head">'
            f"{badge(severity)}"
            f"<strong>{escape(text(item.get('code', 'unknown')))}</strong>"
            "</div>"
            f"<p>{escape(text(item.get('message', '')))}</p>"
            f"{path_html}"
            "</article>"
        )
    return '<div class="findings">' + "".join(rendered) + "</div>"


def diff_summary(diff: dict[str, Any]) -> str:
    """Render git diff summary."""
    metrics = [
        ("Git available", diff.get("git_available", False)),
        ("Changed files", diff.get("changed_file_count", 0)),
        ("Added lines", diff.get("total_added_lines", 0)),
        ("Deleted lines", diff.get("total_deleted_lines", 0)),
        ("Patch lines", diff.get("total_patch_lines", 0)),
    ]
    metric_html = "".join(
        '<div class="metric-row">'
        f"<span>{escape(label)}</span><strong>{escape(text(value))}</strong>"
        "</div>"
        for label, value in metrics
    )
    groups = [
        ("Changed files", diff.get("changed_files", [])),
        ("Test files changed", diff.get("test_files_changed", [])),
        ("Tests deleted", diff.get("tests_deleted", [])),
        ("Forbidden paths touched", diff.get("forbidden_paths_touched", [])),
        ("Secret-like files touched", diff.get("secret_like_files_touched", [])),
        ("Lockfiles changed", diff.get("lockfiles_changed", [])),
    ]
    groups_html = "".join(file_group(title, as_list(paths)) for title, paths in groups)
    return (
        '<div class="diff-grid">'
        f'<div class="metric-list">{metric_html}</div>'
        f'<div class="file-groups">{groups_html}</div>'
        "</div>"
    )


def file_group(title: str, paths: list[Any]) -> str:
    """Render a path group in the diff summary."""
    if paths:
        items = "".join(f"<li>{escape(text(path))}</li>" for path in paths)
    else:
        items = '<li class="muted">None</li>'
    return f'<div class="file-group"><h3>{escape(title)}</h3><ul>{items}</ul></div>'


def badge(value: str) -> str:
    """Render a status/risk badge."""
    normalized = value.lower().replace("_", "-")
    label = escape(value)
    return f'<span class="badge {escape(normalized)}">{label}</span>'


def format_duration(value: object) -> str:
    """Format seconds for display."""
    try:
        return f"{float(value):.3f}s"
    except (TypeError, ValueError):
        return text(value)


def log_note(check_log: str | None) -> str:
    """Return a note when check.log was unavailable."""
    if check_log is None:
        return " when available."
    return "."


def as_dict(value: object) -> dict[str, Any]:
    """Return value as a dict if possible."""
    return value if isinstance(value, dict) else {}


def as_list(value: object) -> list[Any]:
    """Return value as a list if possible."""
    return value if isinstance(value, list) else []


def text(value: object) -> str:
    """Convert dynamic values to text for escaping."""
    if value is None:
        return ""
    return str(value)
