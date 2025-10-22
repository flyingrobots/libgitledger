# Contributing Guide

Thanks for helping build `libgitledger`! This document complements the roadmap and templates in `.github/`.

## Workflow Overview

1. **Plan first.** Review `docs/PROJECT-PLAN.md` and `docs/ISSUE-BREAKDOWN.md` to understand milestone scope.
2. **Open an issue per task.** Use the `Milestone Task` issue template; copy/paste the matching block from `docs/ISSUE-DRAFTS.md` for a quick start.
3. **Keep drafts in sync.** When you adjust the breakdown, run `python3 tools/automation/generate_issue_drafts.py` to refresh the issue bodies.
4. **Reference issues in PRs.** Every pull request should close or update at least one tracked issue (`Closes #123`).

## Development Expectations

- Maintain both build systems. Always ensure changes compile and test cleanly via CMake (`cmake --build`, `ctest`) and Meson (`meson compile`, `meson test`).
- Align tooling: warning flags, optional dependencies, and targets must stay consistent across CMake and Meson.
- When adding dependencies, update both build descriptions and mention the change in the relevant issue.

## Pull Requests

- Fill out `.github/pull_request_template.md` including the dual-build checklist.
- Attach logs or summaries for any failing job marked N/A.
- Flag follow-up work by filing new issues using the template and referencing them in the PR.

## Communication

- Use issue comments to capture implementation decisions, edge cases, and verification notes.
- If work diverges from the roadmap, update `docs/PROJECT-PLAN.md` and regenerate the drafts so future issues stay accurate.
