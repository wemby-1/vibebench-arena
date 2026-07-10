# GitHub Actions

This fixture demonstrates the preview VibeBench composite action. The workflow
uses `uses: ./` because repository CI checks the local action checkout.

External repositories can start with `wemby-1/vibebench-arena@main` during
preview/development, then pin a future stable tag or reviewed commit SHA for
production use.
