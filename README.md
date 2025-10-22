# libgitledger

Early scaffolding for a Git-native ledger library built on top of `libgit2`.

## Documentation

- `docs/SPEC.md` — full functional spec
- `docs/PROJECT-PLAN.md` — milestone roadmap and task lists
- `docs/ISSUE-BREAKDOWN.md` — human-readable task index
- `docs/ISSUE-DRAFTS.md` — prefilled issue bodies generated from the breakdown

## Contributing

- Open work items using the **Milestone Task** issue template (`.github/ISSUE_TEMPLATE/milestone_task.md`).
- Issue drafts can be copied from `docs/ISSUE-DRAFTS.md`; regenerate with `python3 tools/automation/generate_issue_drafts.py` after editing the breakdown.
- Pull requests must follow `.github/pull_request_template.md` and exercise both build systems (CMake + Meson).
- See `CONTRIBUTING.md` for detailed workflow expectations.

## License

libgitledger is released under the [MIND-UCAL License v1.0](LICENSE), aligned with the Universal Charter. See `NOTICE` for attribution details.
