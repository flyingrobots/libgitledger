# Contributing Guide

Thanks for helping build `libgitledger`! This document complements the roadmap and templates in `.github/`.

## Workflow Overview

1. **Plan first.** Review `docs/PROJECT-PLAN.md` and `docs/ISSUE-BREAKDOWN.md` to understand milestone scope.
2. **Open an issue per task.** Use the `Milestone Task` issue template; copy/paste the matching block from `docs/ISSUE-DRAFTS.md` for a quick start.
3. **Keep drafts in sync.** When you adjust the breakdown, run `python3 tools/automation/generate_issue_drafts.py` to refresh the issue bodies.
4. **Reference issues in PRs.** Every pull request should close or update at least one tracked issue (`Closes #123`).

## Development Expectations

- Maintain both build systems. Preferred: run the containerised make targets (`make cmake`, `make meson`, `make test-both`) so you exercise the same matrix CI runs. These jobs copy the repo into isolated workspaces, prepare sandbox Git fixtures, and remove all remotes before mutating anything.
- If you must run directly on the host checkout, export `I_KNOW_WHAT_I_AM_DOING=1` before invoking host targets. The makefile will otherwise abort unless it detects the container guard. Manual command sequences for CMake/Meson live in the README if you need to craft bespoke invocations.
- Align tooling: warning flags, optional dependencies, and targets must stay consistent across CMake and Meson.
- Install prerequisites (at minimum `libgit2` and `pkg-config`) before running host builds. Examples: `sudo apt-get install libgit2-dev pkg-config` or `brew install libgit2 pkg-config`.
- When adding dependencies, update both build descriptions and mention the change in the relevant issue.
- Run `make lint` (containerised clang-format + clang-tidy) before submitting a PR. CI enforces the same suite on GCC, Clang, and MSVC.
- Need to bypass clang-tidy for a quick repro? Run `RUN_TIDY=0 make host-tidy` locally, but flip it back to 1 before shipping anything.

## Pull Requests

- Fill out `.github/pull_request_template.md` including the dual-build checklist.
- Attach logs or summaries for any failing job marked N/A.
- Flag follow-up work by filing new issues using the template and referencing them in the PR.

## Communication

- Use issue comments to capture implementation decisions, edge cases, and verification notes.
- If work diverges from the roadmap, update `docs/PROJECT-PLAN.md` and regenerate the drafts so future issues stay accurate.
