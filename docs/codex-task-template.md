# Codex Task Template

## Purpose

Use this template to write bounded Codex tasks for VibeBench Arena. It keeps each milestone cheap, auditable, and focused by preventing context bloat, whole-repository exploration, repeated failed retries, and unnecessary command runs.

## Standard task prompt template

Copy this prompt and replace the placeholders before starting a milestone:

```markdown
Milestone name:
- <short milestone name>

Goal:
- <one concrete outcome>

Repository state:
- Start from current origin/main.
- Latest expected commit: <hash and subject, if known>.
- Working tree must be clean before editing.

Allowed files:
- <file or directory>
- <file or directory>

Forbidden files:
- <file, directory, or area that must not be touched>
- <file, directory, or area that must not be touched>

Required behavior:
- <behavior or documentation requirement>
- <behavior or documentation requirement>

Focused tests:
- <focused command>
- <focused command>

Full verification, only when needed:
- <full command, only if the change justifies it>

Stop conditions:
- Stop after two consecutive failed fix attempts and report the exact command and error.
- Stop if the required change would touch forbidden files.
- Stop if the working tree is not clean before editing and the dirty files are unrelated.

Commit and push rules:
- Commit only after verification passes.
- Commit message: <type: concise summary>
- Push only to origin/main.
- Do not create tags or releases unless this milestone explicitly requires it.

Final response requirements:
- Modified files
- Exact checks run
- Commit hash
- Push status
- Final git status
- Skipped checks and why
```

## Scope rules

- Read only the files needed for the task.
- Do not read old pasted milestone prompts.
- Do not scan the whole repository unless the milestone explicitly requires it.
- Do not modify unrelated files.
- Do not run full pytest first; start with focused checks.
- Do not keep retrying after two consecutive failed fix attempts.
- Prefer small documentation edits, focused implementation changes, and targeted verification.

## Verification ladder

- Docs-only changes: use focused grep checks, markdown sanity checks when relevant, release-check if the docs affect release readiness, and `git diff --check`.
- Focused code changes: run focused ruff and focused pytest commands first.
- Broad code changes: run full ruff and full pytest only after focused checks pass.
- Post-commit CI command: run it only when the milestone changes CI behavior or release-readiness behavior.

## Final response checklist

Codex should report:

- Modified files
- Exact checks run
- Commit hash
- Push status
- Final git status
- Any skipped checks and why

## Bad prompt vs good prompt examples

Bad prompt:

```text
continue milestone, inspect everything, fix everything
```

Good prompt:

```text
Milestone 74: Update quickstart wording for release-checklist.

Goal:
- Add one short quickstart sentence explaining when to run release-checklist.

Allowed files:
- docs/quickstart.md
- CHANGELOG.md

Forbidden files:
- vibebench/
- tests/
- .github/

Required behavior:
- Keep the docs change under one paragraph.
- Do not change CLI behavior.

Focused tests:
- grep -R "release-checklist" docs/quickstart.md CHANGELOG.md
- git diff --check

Full verification, only when needed:
- python3 -m vibebench release-check

Stop conditions:
- Stop after two consecutive failed fix attempts.
- Stop if the change requires code or tests.

Commit and push rules:
- Commit after verification passes.
- Push to origin/main.
```
