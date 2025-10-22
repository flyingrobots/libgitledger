# Issue Breakdown

Anchored to `docs/PROJECT-PLAN.md`. Use this as a checklist when creating GitHub issues with the `Milestone Task` template. Suggested issue titles follow `[M#: <task>]` convention.

## Milestone M0 — Repo Scaffolding & Tooling

1. `[M0] Scaffold repo layout` — create directory tree, add boilerplate docs.
   - Deliverables: directory structure, LICENSE, README stub, CONTRIBUTING stub.
   - Tests: none (structural).
2. `[M0] Dual build system bootstrap` — author `CMakeLists.txt` + `meson.build` with shared flags.
   - Deliverables: debug/release targets for `gitledger`, `gitledger_tests`, `mg-ledger`.
   - Tests: smoke build in both configurations.
3. `[M0] Dependency placeholders` — wire `libgit2` detection, stubs for CRoaring/BLAKE3 in both build files.
   - Tests: configure succeeds even when optional deps missing (guarded options).
4. `[M0] CI scaffolding` — Dockerfile + GitHub Actions matrix for CMake/Meson (debug/release).
   - Tests: workflow passes with placeholder test target.
5. `[M0] Coding standards` — add `.clang-format`, `.clang-tidy`, `.editorconfig`.
   - Tests: formatting lint job stubbed in CI.

## Milestone M1 — Core Types, Errors, Allocator, Logger

1. `[M1] Error API` — implement `gitledger_code_t`, `gitledger_error_t`, helpers.
   - Tests: unit coverage for error formatting.
2. `[M1] Allocator hooks` — define allocator struct + default implementations.
   - Tests: fake allocator exercised in unit tests.
3. `[M1] Logger hooks` — define log levels + setter; provide stdio adapter.
   - Tests: unit verifying callback invocation.
4. `[M1] Context lifecycle` — implement init/shutdown, ensure dual-build wiring.
   - Tests: unit; build succeeds via CMake + Meson.

## Milestone M2 — Git Port + Minimal Append & Read

1. `[M2] Git repo port interface` — add headers for git port abstraction.
2. `[M2] libgit2 adapter` — implement adapter with fast-forward updates.
3. `[M2] Ledger lifecycle` — open/close operations creating refs.
4. `[M2] Append path` — minimal append with optimistic locking.
5. `[M2] Read path` — latest entry retrieval and message read.
6. `[M2] Integration tests` — temp-repo tests for append/read/conflict.

## Milestone M3 — Policy Enforcement

1. `[M3] Policy document storage` — refs/gitledger/policy/<L> read/write.
2. `[M3] Policy parser` — strict JSON parsing via yyjson (dual-build wiring).
3. `[M3] Author identity port` — capture author context from env/user input.
4. `[M3] Append enforcement` — enforce allowed_authors, payload limits.
5. `[M3] Tests` — happy/negative enforcement scenarios.

## Milestone M4 — Trust & Signatures

1. `[M4] Trust document storage` — refs/gitledger/trust/<L>.
2. `[M4] Signature port` — pluggable verification hooks.
3. `[M4] Commit signature validation` — chain mode checks.
4. `[M4] Attestation support` — note-based signature flow.
5. `[M4] Threshold enforcement` — N-of-M checks, tests.

## Milestone M5 — Notes & Tag Association

1. `[M5] Notes API` — attach/read notes per entry.
2. `[M5] Tag association` — map annotated tags to entries.
3. `[M5] CLI enhancements` — mg-ledger commands for notes/tags.
4. `[M5] Integration tests` — round-trip binary notes, tag lookups.

## Milestone M6 — Indexer & Query Cache

1. `[M6] Indexer interface` — API for encoder/indexer callbacks.
2. `[M6] CRoaring integration` — vendor + expose through both builds.
3. `[M6] Cache writer` — build/rebuild logic with serialization.
4. `[M6] Query engine` — boolean term evaluation over bitmaps.
5. `[M6] CLI query commands` — mg-ledger query UX.
6. `[M6] Tests` — unit + integration covering bitmap ops.

## Milestone M7 — Integrity & Self-Audit

1. `[M7] Deep verify` — full ledger integrity routine.
2. `[M7] BLAKE3 checksum option` — compute & validate ref checksums.
3. `[M7] Documentation/examples` — sample encoders, server hooks.
4. `[M7] End-to-end tests` — corruption detection, checksum behavior.

## Cross-Cutting

- `[Infra] Issue & PR templates` — completed by this change; reference when opening new work.
- `[Infra] CI dual-build guardrails` — ensure workflows fail if either toolchain misses sources/tests.
- `[Infra] Release packaging` — future: produce artifacts (headers, pkg-config, Meson wrap file, CMake config package).
