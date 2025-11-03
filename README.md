# libgitledger

![freestanding](https://img.shields.io/badge/freestanding-ready-005f73)
![libc: independent](https://img.shields.io/badge/libc-independent-brightgreen)

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
- Submodules: this repo uses Git submodules (e.g., `external/ledger-kernel`). Clone with submodules or
  initialise them after cloning:

  ```bash
  git clone --recursive https://github.com/flyingrobots/libgitledger.git
  # or, for an existing checkout
  git submodule update --init --recursive
  ```
  Skipping `--recursive` leaves `external/ledger-kernel/` empty and may break tools that read the spec.
- Quickstart for contributors:
  - Install repo hooks once: `make hooks-install` (pre-commit runs `make format-check` in containers like CI).
  - Temporarily bypass the format gate for a commit: `SKIP_FORMAT_CHECK=1 git commit -m "..."`.
  - Before pushing, run `make test-both` and `make lint` to mirror the matrix locally.

## Building

Running the build or tests directly against your working tree is dangerous: our
integration tests intentionally mutate Git repositories and can trash your
checkout if misused. To keep everyone safe we execute the CI matrix via Docker
by default.

```
make cmake        # containerised CMake builds (Debug + Release)
make meson        # containerised Meson builds (debugoptimized + release)
make both         # run both build systems in containers
make test-cmake   # containerised CTest runs for both build types
make test-meson   # containerised Meson test suite
make test-both    # execute every CI job just like GitHub Actions
make format-check # verify clang-format inside the matrix
make tidy         # clang-tidy inside the matrix (only on the GCC job)
make lint         # format-check + tidy inside the matrix
```

Under the hood these targets spin up per-matrix containers (GCC 14 + Clang 18)
and run the same make targets that CI executes, copying the repository into an
ephemeral workspace and stripping all Git remotes. Each container also boots a
fresh sandbox repository you can reach via the
`LIBGITLEDGER_SANDBOX_ROOT` environment variable during tests.

### Running on the host (dangerous)

If you really need to run against the host checkout, acknowledge the risk by
setting `I_KNOW_WHAT_I_AM_DOING=1`. The make targets will then delegate to the
`host-*` equivalents.

```
I_KNOW_WHAT_I_AM_DOING=1 make cmake
I_KNOW_WHAT_I_AM_DOING=1 make test-both
```

You can still invoke the underlying host targets directly (`make host-cmake`,
`make host-test-meson`, etc.), but they now abort unless you exported the
acknowledgement flag or are already inside the container environment.

### Manual build commands

Prefer the make targets above, but if you need bespoke steps the raw commands
remain available.

#### CMake (Debug and Release)

```
cmake -S . -B build-debug -DCMAKE_BUILD_TYPE=Debug
cmake --build build-debug
ctest --test-dir build-debug

cmake -S . -B build-release -DCMAKE_BUILD_TYPE=Release
cmake --build build-release
```

#### Meson (Debug and Release)

```
meson setup meson-debug --buildtype debugoptimized
meson compile -C meson-debug
meson test -C meson-debug

meson setup meson-release --buildtype release
meson compile -C meson-release
```

### Clean / format helpers

```
make clean        # remove build directories and artefacts
make format       # apply clang-format in-place (runs on the host)
make markdownlint # lint Markdown docs using markdownlint-cli
```

## Dependencies

`libgitledger` links against [`libgit2`](https://libgit2.org/). Ensure the development
headers are available before configuring either build system:

- **Debian/Ubuntu**

  ```bash
  sudo apt-get update
  sudo apt-get install libgit2-dev pkg-config
  ```

- **macOS (Homebrew)**

  ```bash
  brew install libgit2 pkg-config
  ```

- **Windows (Chocolatey)**

  ```powershell
  choco install libgit2 pkgconfiglite
  ```

Optional knobs surface in both build systems:

- CMake: `-DGITLEDGER_WITH_LIBGIT2=OFF` to configure without libgit2, (future)
  `-DGITLEDGER_VENDOR_LIBGIT2=ON` for vendoring once implemented, plus
  placeholders `-DGITLEDGER_WITH_CROARING=ON` and `-DGITLEDGER_WITH_BLAKE3=ON`.
- Meson: `-Dvendor_libgit2=true`, `-Dwith_croaring=enabled`, and `-Dwith_blake3=enabled`.

The CRoaring and BLAKE3 switches are stubs for future work and simply log that
the integration is pending.

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
