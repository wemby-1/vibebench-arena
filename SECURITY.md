# Security Policy

## Supported Versions

VibeBench Arena has not published a stable release yet. Once v0.1.0 is released, the supported line will be v0.1.x.

## Reporting Security Issues

For non-sensitive security concerns, open a GitHub issue with a minimized reproduction.

For sensitive reports, do not paste real secrets, private repository contents, or confidential logs into a public issue. If GitHub private vulnerability reporting is enabled for this repository, use that channel. If it is not enabled, open a minimal public issue that describes the class of problem without exposing sensitive data.

## Security-Sensitive Areas

Examples of security-sensitive reports include:

- secret detection false negatives
- unsafe command execution behavior
- path handling issues that read or write unexpected files
- reports or PR comments leaking local file contents unexpectedly
- confusing output that could encourage users to paste real secrets publicly

## Local Command Execution

VibeBench runs commands from `.vibebench/config.yaml`. These are user-configured local commands, and they may execute arbitrary tooling in the target repository. Review the config before running VibeBench on an unfamiliar project.
