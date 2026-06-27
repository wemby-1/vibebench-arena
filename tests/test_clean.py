import json
from pathlib import Path

from typer.testing import CliRunner

from vibebench.clean import clean_runs
from vibebench.cli import app

runner = CliRunner()


def write_run(runs_dir: Path, name: str, content: str = "payload") -> Path:
    run_dir = runs_dir / name
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "metrics.json").write_text(
        json.dumps({"project_name": "demo"}),
        encoding="utf-8",
    )
    (run_dir / "check.log").write_text(content, encoding="utf-8")
    return run_dir


def test_clean_default_is_dry_run_and_deletes_nothing(tmp_path: Path) -> None:
    runs_dir = tmp_path / ".vibebench" / "runs"
    old = write_run(runs_dir, "20260627_120000")
    new = write_run(runs_dir, "20260627_130000")

    result = clean_runs(tmp_path, keep=1)

    assert result.dry_run is True
    assert [candidate.run_id for candidate in result.candidates] == [old.name]
    assert old.exists()
    assert new.exists()


def test_clean_yes_deletes_only_expected_old_runs(tmp_path: Path) -> None:
    runs_dir = tmp_path / ".vibebench" / "runs"
    old = write_run(runs_dir, "20260627_120000")
    preserved = write_run(runs_dir, "20260627_130000")
    non_run = runs_dir / "notes"
    non_run.mkdir()
    (non_run / "note.txt").write_text("keep me", encoding="utf-8")

    result = clean_runs(tmp_path, keep=1, yes=True)

    assert result.deleted_count == 1
    assert not old.exists()
    assert preserved.exists()
    assert non_run.exists()


def test_clean_cli_dry_run_mentions_yes(tmp_path: Path) -> None:
    runs_dir = tmp_path / ".vibebench" / "runs"
    old = write_run(runs_dir, "20260627_120000")
    write_run(runs_dir, "20260627_130000")

    result = runner.invoke(
        app,
        ["clean", "--project-root", str(tmp_path), "--keep", "1"],
    )

    assert result.exit_code == 0
    assert "Dry run only" in result.output
    assert old.name in result.output
    assert old.exists()


def test_clean_cli_yes_deletes_candidates(tmp_path: Path) -> None:
    runs_dir = tmp_path / ".vibebench" / "runs"
    old = write_run(runs_dir, "20260627_120000")
    write_run(runs_dir, "20260627_130000")

    result = runner.invoke(
        app,
        ["clean", "--project-root", str(tmp_path), "--keep", "1", "--yes"],
    )

    assert result.exit_code == 0
    assert "Deleted 1 run" in result.output
    assert not old.exists()


def test_clean_when_runs_do_not_exceed_keep_deletes_nothing(tmp_path: Path) -> None:
    runs_dir = tmp_path / ".vibebench" / "runs"
    run = write_run(runs_dir, "20260627_120000")

    result = clean_runs(tmp_path, keep=20, yes=True)

    assert result.candidates == []
    assert result.deleted_count == 0
    assert run.exists()


def test_clean_missing_runs_directory_is_successful(tmp_path: Path) -> None:
    result = runner.invoke(app, ["clean", "--project-root", str(tmp_path)])

    assert result.exit_code == 0
    assert "Nothing to clean" in result.output


def test_clean_rejects_negative_keep(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        ["clean", "--project-root", str(tmp_path), "--keep", "-1"],
    )

    assert result.exit_code == 1
    assert "--keep must be 0 or greater" in result.output


def test_clean_rejects_runs_path_that_is_file(tmp_path: Path) -> None:
    runs_file = tmp_path / "runs-file"
    runs_file.write_text("nope", encoding="utf-8")

    result = runner.invoke(
        app,
        ["clean", "--project-root", str(tmp_path), "--runs-dir", str(runs_file)],
    )

    assert result.exit_code == 1
    assert "Runs path is not a directory" in result.output


def test_clean_does_not_follow_symlink_runs(tmp_path: Path) -> None:
    runs_dir = tmp_path / ".vibebench" / "runs"
    write_run(runs_dir, "20260627_130000")
    target = tmp_path / "outside"
    outside_run = write_run(target, "20260627_120000")
    link = runs_dir / "20260627_120000"
    link.symlink_to(outside_run, target_is_directory=True)

    result = clean_runs(tmp_path, keep=0, yes=True)

    assert result.deleted_count == 1
    assert outside_run.exists()
    assert link.exists()
