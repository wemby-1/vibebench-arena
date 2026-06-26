# Documentation Assets

`docs/assets/report-preview.svg` is a static README preview asset. It is
intended to show the shape of a clean VibeBench HTML report on GitHub.

`docs/assets/risk-demo-preview.svg` is a static README preview asset for the
risk demo. It illustrates VibeBench catching dangerous generated-code changes.

Real reports are generated locally by running:

```bash
python -m vibebench check
python -m vibebench report
```

Generated reports live under:

```text
.vibebench/runs/<timestamp>/report/index.html
```

Those run artifacts are local outputs and should not be committed.
