# `libgitledger`

Early scaffolding for a Git-native ledger library built on top of `libgit2`.

## Documentation

- `docs/SPEC.md` — full functional spec
- `docs/PROJECT-PLAN.md` — milestone roadmap and task lists
- `docs/ISSUE-BREAKDOWN.md` — human-readable task index
- `docs/ISSUE-DRAFTS.md` — prefilled issue bodies generated from the breakdown

## Contributing

- Create work items using the **Milestone Task** issue template (`.github/ISSUE_TEMPLATE/milestone_task.md`).
- Issue drafts can be copied from `docs/ISSUE-DRAFTS.md`; regenerate with `python3 tools/automation/generate_issue_drafts.py` after editing the breakdown.
- Pull requests must follow `.github/pull_request_template.md` and exercise both build systems (CMake + Meson).
- See `CONTRIBUTING.md` for detailed workflow expectations.

## Building

Why do we have two build systems? Well... It's a long story.

### CMake (Debug and Release)

```
cmake -S . -B build-debug -G Ninja -DCMAKE_BUILD_TYPE=Debug -DCMAKE_EXPORT_COMPILE_COMMANDS=ON
cmake --build build-debug
ctest --test-dir build-debug

cmake -S . -B build-release -G Ninja -DCMAKE_BUILD_TYPE=Release
cmake --build build-release
ctest --test-dir build-release
```

### Meson (Debug and Release)

```
meson setup meson-debug --buildtype debugoptimized
meson compile -C meson-debug
meson test -C meson-debug

meson setup meson-release --buildtype release
meson compile -C meson-release
meson test -C meson-release
```

### Convenience Targets

Use the provided `Makefile` shortcuts:

#### Build

```bash
make cmake        # configure + build CMake debug and release
make meson        # configure + build Meson debug and release
make both         # run both cmake + meson builds
```

#### Test

```bash
make test-cmake   # run ctest for debug/release builds
make test-meson   # run meson test for debug/release builds
make test-both    # execute all tests
```

#### Clean

```bash
make clean        # remove build directories and artefacts
```

#### Format

```
```bash
make format       # apply clang-format in-place
make format-check # verify clang-format compliance
```

#### Lint

```bash
make tidy         # run clang-tidy with project configuration
make lint         # run both format-check and tidy
```

## Coding Standards

- `.clang-format` defines the canonical formatting rules; run `make format` to apply them and
  `make format-check` to verify compliance.
- `.clang-tidy` configures warnings-as-errors for the project; `make tidy` builds a dedicated compile
  database and executes the static analysis suite.
- `.editorconfig` captures default editor behaviour (UTF-8, LF line endings, four-space indents for C).
- GitHub Actions executes the full lint + build matrix for GCC, Clang, and MSVC. macOS is not part of the
  hosted matrix to keep CI costs manageable; if you develop on macOS, consider a local pre-push hook that
  runs `make lint`.

## License

`libgitledger` is released under the [MIND-UCAL License v1.0](LICENSE), aligned with the Universal Charter. See [`NOTICE`](NOTICE) for attribution details.
