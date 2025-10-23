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

## Building

### CMake (Debug and Release)

```
cmake -S . -B build-debug -DCMAKE_BUILD_TYPE=Debug
cmake --build build-debug
ctest --test-dir build-debug

cmake -S . -B build-release -DCMAKE_BUILD_TYPE=Release
cmake --build build-release
```

### Meson (Debug and Release)

```
meson setup meson-debug --buildtype debugoptimized
meson compile -C meson-debug
meson test -C meson-debug

meson setup meson-release --buildtype release
meson compile -C meson-release
```

### Convenience Targets

You can also rely on the provided `Makefile` shortcuts:

```
make cmake        # configure + build CMake debug and release
make meson        # configure + build Meson debug and release
make both         # run both cmake + meson builds
make test-cmake   # run ctest for debug/release builds
make test-meson   # run meson test for debug/release builds
make test-both    # execute all tests
make clean        # remove build directories and artefacts
```

## License

libgitledger is released under the [MIND-UCAL License v1.0](LICENSE), aligned with the Universal Charter. See `NOTICE` for attribution details.
