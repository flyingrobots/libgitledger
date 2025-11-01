# Issue Drafts

Auto-generated from `docs/ISSUE-BREAKDOWN.md`. Each block can be pasted into a new issue using the Milestone Task template.

## [M0] Scaffold repo layout

---

title: "[M0] Scaffold repo layout"
labels: ["milestone::M0"]
assignees: []
---

## Summary

create directory tree, add boilerplate docs.

## Links / Context

- Project plan: docs/PROJECT-PLAN.md
- Breakdown entry: docs/ISSUE-BREAKDOWN.md

## Deliverables

- [ ] directory structure
- [ ] LICENSE
- [ ] README stub
- [ ] CONTRIBUTING stub

## Implementation Notes

- Add details during execution

## Tests & Verification

- [ ] N/A

## Definition of Done

- [ ] CMake build passes (debug & release, if applicable)
- [ ] Meson build passes (debug & release, if applicable)
- [ ] Tests executed or marked N/A with rationale
- [ ] CI workflows updated if required
- [ ] Follow-up issues filed for deferred work

## [M0] Dual build system bootstrap

---

title: "[M0] Dual build system bootstrap"
labels: ["milestone::M0"]
assignees: []
---

## Summary

author `CMakeLists.txt` + `meson.build` with shared flags.

## Links / Context

- Project plan: docs/PROJECT-PLAN.md
- Breakdown entry: docs/ISSUE-BREAKDOWN.md

## Deliverables

- [ ] debug/release targets for `gitledger`
- [ ] `gitledger_tests`
- [ ] `git-ledger`

## Implementation Notes

- Add details during execution

## Tests & Verification

- [ ] smoke build in both configurations

## Definition of Done

- [ ] CMake build passes (debug & release, if applicable)
- [ ] Meson build passes (debug & release, if applicable)
- [ ] Tests executed or marked N/A with rationale
- [ ] CI workflows updated if required
- [ ] Follow-up issues filed for deferred work

## [M0] Dependency placeholders

---

title: "[M0] Dependency placeholders"
labels: ["milestone::M0"]
assignees: []
---

## Summary

wire `libgit2` detection, stubs for CRoaring/BLAKE3 in both build files.

## Links / Context

- Project plan: docs/PROJECT-PLAN.md
- Breakdown entry: docs/ISSUE-BREAKDOWN.md

## Deliverables

- [ ] Document deliverables before closing

## Implementation Notes

- Add details during execution

## Tests & Verification

- [ ] configure succeeds even when optional deps missing (guarded options)

## Definition of Done

- [ ] CMake build passes (debug & release, if applicable)
- [ ] Meson build passes (debug & release, if applicable)
- [ ] Tests executed or marked N/A with rationale
- [ ] CI workflows updated if required
- [ ] Follow-up issues filed for deferred work

## [M0] CI scaffolding

---

title: "[M0] CI scaffolding"
labels: ["milestone::M0"]
assignees: []
---

## Summary

Dockerfile + GitHub Actions matrix for CMake/Meson (debug/release).

## Links / Context

- Project plan: docs/PROJECT-PLAN.md
- Breakdown entry: docs/ISSUE-BREAKDOWN.md

## Deliverables

- [ ] Document deliverables before closing

## Implementation Notes

- Add details during execution

## Tests & Verification

- [ ] workflow passes with placeholder test target

## Definition of Done

- [ ] CMake build passes (debug & release, if applicable)
- [ ] Meson build passes (debug & release, if applicable)
- [ ] Tests executed or marked N/A with rationale
- [ ] CI workflows updated if required
- [ ] Follow-up issues filed for deferred work

## [M0] Coding standards

---

title: "[M0] Coding standards"
labels: ["milestone::M0"]
assignees: []
---

## Summary

add `.clang-format`, `.clang-tidy`, `.editorconfig`.

## Links / Context

- Project plan: docs/PROJECT-PLAN.md
- Breakdown entry: docs/ISSUE-BREAKDOWN.md

## Deliverables

- [ ] Document deliverables before closing

## Implementation Notes

- Add details during execution

## Tests & Verification

- [ ] formatting lint job stubbed in CI

## Definition of Done

- [ ] CMake build passes (debug & release, if applicable)
- [ ] Meson build passes (debug & release, if applicable)
- [ ] Tests executed or marked N/A with rationale
- [ ] CI workflows updated if required
- [ ] Follow-up issues filed for deferred work

## [M1] Error API

---

title: "[M1] Error API"
labels: ["milestone::M1"]
assignees: []
---

## Summary

implement `gitledger_code_t`, `gitledger_error_t`, helpers.

## Links / Context

- Project plan: docs/PROJECT-PLAN.md
- Breakdown entry: docs/ISSUE-BREAKDOWN.md

## Deliverables

- [ ] Document deliverables before closing

## Implementation Notes

- Add details during execution

## Tests & Verification

- [ ] unit coverage for error formatting

## Definition of Done

- [ ] CMake build passes (debug & release, if applicable)
- [ ] Meson build passes (debug & release, if applicable)
- [ ] Tests executed or marked N/A with rationale
- [ ] CI workflows updated if required
- [ ] Follow-up issues filed for deferred work

## [M1] Allocator hooks

## [M2] Linux CRT shim for freestanding executables + CI path

title: "[M2] Minimal Linux CRT shim (_start) and freestanding CI job"
labels: ["milestone::M2", "area::build", "type::enhancement"]
assignees: []

## Summary

Provide a minimal Linux x86_64 CRT bootstrap (_start) sufficient to run our test executables with `-nostdlib`, and add an opt-in CI job that configures CMake with `-DGITLEDGER_USE_NOSTDLIB=ON` (and Meson with `-Dexec_nostdlib=true`) to validate a clean freestanding path. Keep the main matrix untouched (option OFF by default).

## Links / Context

- Policy: library is always linked with `-nostdlib` on non‑MSVC; executables gated behind `GITLEDGER_USE_NOSTDLIB` (default OFF).
- CMake option: `GITLEDGER_USE_NOSTDLIB` (OFF by default)
- Meson option: `exec_nostdlib` (false by default)

## Deliverables

- [ ] `crt/linux/x86_64/crt0.S` (or `.S` + tiny C wrapper) providing `_start` → calls `main(int,char**)`, returns via `exit` syscall
- [ ] CMake wiring to include CRT objects only when `GITLEDGER_USE_NOSTDLIB=ON` (non‑MSVC)
- [ ] Meson wiring to include CRT objects only when `-Dexec_nostdlib=true` (non‑MSVC)
- [ ] GitHub Actions job `freestanding-linux` that:
  - checks out repo, installs deps
  - configures CMake `-DGITLEDGER_USE_NOSTDLIB=ON`
  - builds `gitledger` and test executables
  - runs a trivial smoke test (e.g., version test) under the shim
  - runs on `ubuntu-24.04`; `continue-on-error: false` once the shim is stable
- [ ] Documentation in `CONTRIBUTING.md` describing the option and how to run the freestanding job locally

## Implementation Notes

- Target Linux x86_64 first; add other arches later.
- Provide raw syscalls: `exit`, `write` (for minimal stderr prints if needed).
- Avoid any libc references; pass argc/argv/envp from stack per SysV ABI.
- Guard all CRT sources under a CMake/Meson option so default builds remain unchanged.

## Tests & Verification

- [ ] CI job configures `GITLEDGER_USE_NOSTDLIB=ON` and builds/executes at least one test binary
- [ ] Local run: `cmake -S . -B build-ffs -DGITLEDGER_USE_NOSTDLIB=ON && cmake --build build-ffs`
- [ ] Local run (Meson): `meson setup meson-ffs -Dexec_nostdlib=true && meson compile -C meson-ffs`

## Definition of Done

- [ ] CMake + Meson builds succeed with freestanding options on Ubuntu
- [ ] CI job `freestanding-linux` passes without `continue-on-error`
- [ ] Docs updated (CONTRIBUTING)

---

title: "[M1] Allocator hooks"
labels: ["milestone::M1"]
assignees: []
---

## Summary

define allocator struct + default implementations.

## Links / Context

- Project plan: docs/PROJECT-PLAN.md
- Breakdown entry: docs/ISSUE-BREAKDOWN.md

## Deliverables

- [ ] Document deliverables before closing

## Implementation Notes

- Add details during execution

## Tests & Verification

- [ ] fake allocator exercised in unit tests

## Definition of Done

- [ ] CMake build passes (debug & release, if applicable)
- [ ] Meson build passes (debug & release, if applicable)
- [ ] Tests executed or marked N/A with rationale
- [ ] CI workflows updated if required
- [ ] Follow-up issues filed for deferred work

## [M1] Logger hooks

---

title: "[M1] Logger hooks"
labels: ["milestone::M1"]
assignees: []
---

## Summary

define log levels + setter; provide stdio adapter.

## Links / Context

- Project plan: docs/PROJECT-PLAN.md
- Breakdown entry: docs/ISSUE-BREAKDOWN.md

## Deliverables

- [ ] Document deliverables before closing

## Implementation Notes

- Add details during execution

## Tests & Verification

- [ ] unit verifying callback invocation

## Definition of Done

- [ ] CMake build passes (debug & release, if applicable)
- [ ] Meson build passes (debug & release, if applicable)
- [ ] Tests executed or marked N/A with rationale
- [ ] CI workflows updated if required
- [ ] Follow-up issues filed for deferred work

## [M1] Context lifecycle

---

title: "[M1] Context lifecycle"
labels: ["milestone::M1"]
assignees: []
---

## Summary

implement init/shutdown, ensure dual-build wiring.

## Links / Context

- Project plan: docs/PROJECT-PLAN.md
- Breakdown entry: docs/ISSUE-BREAKDOWN.md

## Deliverables

- [ ] Document deliverables before closing

## Implementation Notes

- Add details during execution

## Tests & Verification

- [ ] unit
- [ ] build succeeds via CMake + Meson

## Definition of Done

- [ ] CMake build passes (debug & release, if applicable)
- [ ] Meson build passes (debug & release, if applicable)
- [ ] Tests executed or marked N/A with rationale
- [ ] CI workflows updated if required
- [ ] Follow-up issues filed for deferred work

## [M2] Git repo port interface

---

title: "[M2] Git repo port interface"
labels: ["milestone::M2"]
assignees: []
---

## Summary

add headers for git port abstraction.

## Links / Context

- Project plan: docs/PROJECT-PLAN.md
- Breakdown entry: docs/ISSUE-BREAKDOWN.md

## Deliverables

- [ ] Document deliverables before closing

## Implementation Notes

- Add details during execution

## Tests & Verification

- [ ] Capture verification plan in issue comments

## Definition of Done

- [ ] CMake build passes (debug & release, if applicable)
- [ ] Meson build passes (debug & release, if applicable)
- [ ] Tests executed or marked N/A with rationale
- [ ] CI workflows updated if required
- [ ] Follow-up issues filed for deferred work

## [M2] libgit2 adapter

---

title: "[M2] libgit2 adapter"
labels: ["milestone::M2"]
assignees: []
---

## Summary

implement adapter with fast-forward updates.

## Links / Context

- Project plan: docs/PROJECT-PLAN.md
- Breakdown entry: docs/ISSUE-BREAKDOWN.md

## Deliverables

- [ ] Document deliverables before closing

## Implementation Notes

- Add details during execution

## Tests & Verification

- [ ] Capture verification plan in issue comments

## Definition of Done

- [ ] CMake build passes (debug & release, if applicable)
- [ ] Meson build passes (debug & release, if applicable)
- [ ] Tests executed or marked N/A with rationale
- [ ] CI workflows updated if required
- [ ] Follow-up issues filed for deferred work

## [M2] Ledger lifecycle

---

title: "[M2] Ledger lifecycle"
labels: ["milestone::M2"]
assignees: []
---

## Summary

open/close operations creating refs.

## Links / Context

- Project plan: docs/PROJECT-PLAN.md
- Breakdown entry: docs/ISSUE-BREAKDOWN.md

## Deliverables

- [ ] Document deliverables before closing

## Implementation Notes

- Add details during execution

## Tests & Verification

- [ ] Capture verification plan in issue comments

## Definition of Done

- [ ] CMake build passes (debug & release, if applicable)
- [ ] Meson build passes (debug & release, if applicable)
- [ ] Tests executed or marked N/A with rationale
- [ ] CI workflows updated if required
- [ ] Follow-up issues filed for deferred work

## [M2] Append path

---

title: "[M2] Append path"
labels: ["milestone::M2"]
assignees: []
---

## Summary

minimal append with optimistic locking.

## Links / Context

- Project plan: docs/PROJECT-PLAN.md
- Breakdown entry: docs/ISSUE-BREAKDOWN.md

## Deliverables

- [ ] Document deliverables before closing

## Implementation Notes

- Add details during execution

## Tests & Verification

- [ ] Capture verification plan in issue comments

## Definition of Done

- [ ] CMake build passes (debug & release, if applicable)
- [ ] Meson build passes (debug & release, if applicable)
- [ ] Tests executed or marked N/A with rationale
- [ ] CI workflows updated if required
- [ ] Follow-up issues filed for deferred work

## [M2] Read path

---

title: "[M2] Read path"
labels: ["milestone::M2"]
assignees: []
---

## Summary

latest entry retrieval and message read.

## Links / Context

- Project plan: docs/PROJECT-PLAN.md
- Breakdown entry: docs/ISSUE-BREAKDOWN.md

## Deliverables

- [ ] Document deliverables before closing

## Implementation Notes

- Add details during execution

## Tests & Verification

- [ ] Capture verification plan in issue comments

## Definition of Done

- [ ] CMake build passes (debug & release, if applicable)
- [ ] Meson build passes (debug & release, if applicable)
- [ ] Tests executed or marked N/A with rationale
- [ ] CI workflows updated if required
- [ ] Follow-up issues filed for deferred work

## [M2] Integration tests

---

title: "[M2] Integration tests"
labels: ["milestone::M2"]
assignees: []
---

## Summary

temp-repo tests for append/read/conflict.

## Links / Context

- Project plan: docs/PROJECT-PLAN.md
- Breakdown entry: docs/ISSUE-BREAKDOWN.md

## Deliverables

- [ ] Document deliverables before closing

## Implementation Notes

- Add details during execution

## Tests & Verification

- [ ] Capture verification plan in issue comments

## Definition of Done

- [ ] CMake build passes (debug & release, if applicable)
- [ ] Meson build passes (debug & release, if applicable)
- [ ] Tests executed or marked N/A with rationale
- [ ] CI workflows updated if required
- [ ] Follow-up issues filed for deferred work

## [M3] Policy document storage

---

title: "[M3] Policy document storage"
labels: ["milestone::M3"]
assignees: []
---

## Summary

refs/gitledger/policy/<L> read/write.

## Links / Context

- Project plan: docs/PROJECT-PLAN.md
- Breakdown entry: docs/ISSUE-BREAKDOWN.md

## Deliverables

- [ ] Document deliverables before closing

## Implementation Notes

- Add details during execution

## Tests & Verification

- [ ] Capture verification plan in issue comments

## Definition of Done

- [ ] CMake build passes (debug & release, if applicable)
- [ ] Meson build passes (debug & release, if applicable)
- [ ] Tests executed or marked N/A with rationale
- [ ] CI workflows updated if required
- [ ] Follow-up issues filed for deferred work

## [M3] Policy parser

---

title: "[M3] Policy parser"
labels: ["milestone::M3"]
assignees: []
---

## Summary

strict JSON parsing via yyjson (dual-build wiring).

## Links / Context

- Project plan: docs/PROJECT-PLAN.md
- Breakdown entry: docs/ISSUE-BREAKDOWN.md

## Deliverables

- [ ] Document deliverables before closing

## Implementation Notes

- Add details during execution

## Tests & Verification

- [ ] Capture verification plan in issue comments

## Definition of Done

- [ ] CMake build passes (debug & release, if applicable)
- [ ] Meson build passes (debug & release, if applicable)
- [ ] Tests executed or marked N/A with rationale
- [ ] CI workflows updated if required
- [ ] Follow-up issues filed for deferred work

## [M3] Author identity port

---

title: "[M3] Author identity port"
labels: ["milestone::M3"]
assignees: []
---

## Summary

capture author context from env/user input.

## Links / Context

- Project plan: docs/PROJECT-PLAN.md
- Breakdown entry: docs/ISSUE-BREAKDOWN.md

## Deliverables

- [ ] Document deliverables before closing

## Implementation Notes

- Add details during execution

## Tests & Verification

- [ ] Capture verification plan in issue comments

## Definition of Done

- [ ] CMake build passes (debug & release, if applicable)
- [ ] Meson build passes (debug & release, if applicable)
- [ ] Tests executed or marked N/A with rationale
- [ ] CI workflows updated if required
- [ ] Follow-up issues filed for deferred work

## [M3] Append enforcement

---

title: "[M3] Append enforcement"
labels: ["milestone::M3"]
assignees: []
---

## Summary

enforce allowed_authors, payload limits.

## Links / Context

- Project plan: docs/PROJECT-PLAN.md
- Breakdown entry: docs/ISSUE-BREAKDOWN.md

## Deliverables

- [ ] Document deliverables before closing

## Implementation Notes

- Add details during execution

## Tests & Verification

- [ ] Capture verification plan in issue comments

## Definition of Done

- [ ] CMake build passes (debug & release, if applicable)
- [ ] Meson build passes (debug & release, if applicable)
- [ ] Tests executed or marked N/A with rationale
- [ ] CI workflows updated if required
- [ ] Follow-up issues filed for deferred work

## [M3] Tests

---

title: "[M3] Tests"
labels: ["milestone::M3"]
assignees: []
---

## Summary

happy/negative enforcement scenarios.

## Links / Context

- Project plan: docs/PROJECT-PLAN.md
- Breakdown entry: docs/ISSUE-BREAKDOWN.md

## Deliverables

- [ ] Document deliverables before closing

## Implementation Notes

- Add details during execution

## Tests & Verification

- [ ] Capture verification plan in issue comments

## Definition of Done

- [ ] CMake build passes (debug & release, if applicable)
- [ ] Meson build passes (debug & release, if applicable)
- [ ] Tests executed or marked N/A with rationale
- [ ] CI workflows updated if required
- [ ] Follow-up issues filed for deferred work

## [M4] Trust document storage

---

title: "[M4] Trust document storage"
labels: ["milestone::M4"]
assignees: []
---

## Summary

refs/gitledger/trust/<L>.

## Links / Context

- Project plan: docs/PROJECT-PLAN.md
- Breakdown entry: docs/ISSUE-BREAKDOWN.md

## Deliverables

- [ ] Document deliverables before closing

## Implementation Notes

- Add details during execution

## Tests & Verification

- [ ] Capture verification plan in issue comments

## Definition of Done

- [ ] CMake build passes (debug & release, if applicable)
- [ ] Meson build passes (debug & release, if applicable)
- [ ] Tests executed or marked N/A with rationale
- [ ] CI workflows updated if required
- [ ] Follow-up issues filed for deferred work

## [M4] Signature port

---

title: "[M4] Signature port"
labels: ["milestone::M4"]
assignees: []
---

## Summary

pluggable verification hooks.

## Links / Context

- Project plan: docs/PROJECT-PLAN.md
- Breakdown entry: docs/ISSUE-BREAKDOWN.md

## Deliverables

- [ ] Document deliverables before closing

## Implementation Notes

- Add details during execution

## Tests & Verification

- [ ] Capture verification plan in issue comments

## Definition of Done

- [ ] CMake build passes (debug & release, if applicable)
- [ ] Meson build passes (debug & release, if applicable)
- [ ] Tests executed or marked N/A with rationale
- [ ] CI workflows updated if required
- [ ] Follow-up issues filed for deferred work

## [M4] Commit signature validation

---

title: "[M4] Commit signature validation"
labels: ["milestone::M4"]
assignees: []
---

## Summary

chain mode checks.

## Links / Context

- Project plan: docs/PROJECT-PLAN.md
- Breakdown entry: docs/ISSUE-BREAKDOWN.md

## Deliverables

- [ ] Document deliverables before closing

## Implementation Notes

- Add details during execution

## Tests & Verification

- [ ] Capture verification plan in issue comments

## Definition of Done

- [ ] CMake build passes (debug & release, if applicable)
- [ ] Meson build passes (debug & release, if applicable)
- [ ] Tests executed or marked N/A with rationale
- [ ] CI workflows updated if required
- [ ] Follow-up issues filed for deferred work

## [M4] Attestation support

---

title: "[M4] Attestation support"
labels: ["milestone::M4"]
assignees: []
---

## Summary

note-based signature flow.

## Links / Context

- Project plan: docs/PROJECT-PLAN.md
- Breakdown entry: docs/ISSUE-BREAKDOWN.md

## Deliverables

- [ ] Document deliverables before closing

## Implementation Notes

- Add details during execution

## Tests & Verification

- [ ] Capture verification plan in issue comments

## Definition of Done

- [ ] CMake build passes (debug & release, if applicable)
- [ ] Meson build passes (debug & release, if applicable)
- [ ] Tests executed or marked N/A with rationale
- [ ] CI workflows updated if required
- [ ] Follow-up issues filed for deferred work

## [M4] Threshold enforcement

---

title: "[M4] Threshold enforcement"
labels: ["milestone::M4"]
assignees: []
---

## Summary

N-of-M checks, tests.

## Links / Context

- Project plan: docs/PROJECT-PLAN.md
- Breakdown entry: docs/ISSUE-BREAKDOWN.md

## Deliverables

- [ ] Document deliverables before closing

## Implementation Notes

- Add details during execution

## Tests & Verification

- [ ] Capture verification plan in issue comments

## Definition of Done

- [ ] CMake build passes (debug & release, if applicable)
- [ ] Meson build passes (debug & release, if applicable)
- [ ] Tests executed or marked N/A with rationale
- [ ] CI workflows updated if required
- [ ] Follow-up issues filed for deferred work

## [M5] Notes API

---

title: "[M5] Notes API"
labels: ["milestone::M5"]
assignees: []
---

## Summary

attach/read notes per entry.

## Links / Context

- Project plan: docs/PROJECT-PLAN.md
- Breakdown entry: docs/ISSUE-BREAKDOWN.md

## Deliverables

- [ ] Document deliverables before closing

## Implementation Notes

- Add details during execution

## Tests & Verification

- [ ] Capture verification plan in issue comments

## Definition of Done

- [ ] CMake build passes (debug & release, if applicable)
- [ ] Meson build passes (debug & release, if applicable)
- [ ] Tests executed or marked N/A with rationale
- [ ] CI workflows updated if required
- [ ] Follow-up issues filed for deferred work

## [M5] Tag association

---

title: "[M5] Tag association"
labels: ["milestone::M5"]
assignees: []
---

## Summary

map annotated tags to entries.

## Links / Context

- Project plan: docs/PROJECT-PLAN.md
- Breakdown entry: docs/ISSUE-BREAKDOWN.md

## Deliverables

- [ ] Document deliverables before closing

## Implementation Notes

- Add details during execution

## Tests & Verification

- [ ] Capture verification plan in issue comments

## Definition of Done

- [ ] CMake build passes (debug & release, if applicable)
- [ ] Meson build passes (debug & release, if applicable)
- [ ] Tests executed or marked N/A with rationale
- [ ] CI workflows updated if required
- [ ] Follow-up issues filed for deferred work

## [M5] CLI enhancements

---

title: "[M5] CLI enhancements"
labels: ["milestone::M5"]
assignees: []
---

## Summary

git-ledger commands for notes/tags.

## Links / Context

- Project plan: docs/PROJECT-PLAN.md
- Breakdown entry: docs/ISSUE-BREAKDOWN.md

## Deliverables

- [ ] Document deliverables before closing

## Implementation Notes

- Add details during execution

## Tests & Verification

- [ ] Capture verification plan in issue comments

## Definition of Done

- [ ] CMake build passes (debug & release, if applicable)
- [ ] Meson build passes (debug & release, if applicable)
- [ ] Tests executed or marked N/A with rationale
- [ ] CI workflows updated if required
- [ ] Follow-up issues filed for deferred work

## [M5] Integration tests

---

title: "[M5] Integration tests"
labels: ["milestone::M5"]
assignees: []
---

## Summary

round-trip binary notes, tag lookups.

## Links / Context

- Project plan: docs/PROJECT-PLAN.md
- Breakdown entry: docs/ISSUE-BREAKDOWN.md

## Deliverables

- [ ] Document deliverables before closing

## Implementation Notes

- Add details during execution

## Tests & Verification

- [ ] Capture verification plan in issue comments

## Definition of Done

- [ ] CMake build passes (debug & release, if applicable)
- [ ] Meson build passes (debug & release, if applicable)
- [ ] Tests executed or marked N/A with rationale
- [ ] CI workflows updated if required
- [ ] Follow-up issues filed for deferred work

## [M6] Indexer interface

---

title: "[M6] Indexer interface"
labels: ["milestone::M6"]
assignees: []
---

## Summary

API for encoder/indexer callbacks.

## Links / Context

- Project plan: docs/PROJECT-PLAN.md
- Breakdown entry: docs/ISSUE-BREAKDOWN.md

## Deliverables

- [ ] Document deliverables before closing

## Implementation Notes

- Add details during execution

## Tests & Verification

- [ ] Capture verification plan in issue comments

## Definition of Done

- [ ] CMake build passes (debug & release, if applicable)
- [ ] Meson build passes (debug & release, if applicable)
- [ ] Tests executed or marked N/A with rationale
- [ ] CI workflows updated if required
- [ ] Follow-up issues filed for deferred work

## [M6] CRoaring integration

---

title: "[M6] CRoaring integration"
labels: ["milestone::M6"]
assignees: []
---

## Summary

vendor + expose through both builds.

## Links / Context

- Project plan: docs/PROJECT-PLAN.md
- Breakdown entry: docs/ISSUE-BREAKDOWN.md

## Deliverables

- [ ] Document deliverables before closing

## Implementation Notes

- Add details during execution

## Tests & Verification

- [ ] Capture verification plan in issue comments

## Definition of Done

- [ ] CMake build passes (debug & release, if applicable)
- [ ] Meson build passes (debug & release, if applicable)
- [ ] Tests executed or marked N/A with rationale
- [ ] CI workflows updated if required
- [ ] Follow-up issues filed for deferred work

## [M6] Cache writer

---

title: "[M6] Cache writer"
labels: ["milestone::M6"]
assignees: []
---

## Summary

build/rebuild logic with serialization.

## Links / Context

- Project plan: docs/PROJECT-PLAN.md
- Breakdown entry: docs/ISSUE-BREAKDOWN.md

## Deliverables

- [ ] Document deliverables before closing

## Implementation Notes

- Add details during execution

## Tests & Verification

- [ ] Capture verification plan in issue comments

## Definition of Done

- [ ] CMake build passes (debug & release, if applicable)
- [ ] Meson build passes (debug & release, if applicable)
- [ ] Tests executed or marked N/A with rationale
- [ ] CI workflows updated if required
- [ ] Follow-up issues filed for deferred work

## [M6] Query engine

---

title: "[M6] Query engine"
labels: ["milestone::M6"]
assignees: []
---

## Summary

boolean term evaluation over bitmaps.

## Links / Context

- Project plan: docs/PROJECT-PLAN.md
- Breakdown entry: docs/ISSUE-BREAKDOWN.md

## Deliverables

- [ ] Document deliverables before closing

## Implementation Notes

- Add details during execution

## Tests & Verification

- [ ] Capture verification plan in issue comments

## Definition of Done

- [ ] CMake build passes (debug & release, if applicable)
- [ ] Meson build passes (debug & release, if applicable)
- [ ] Tests executed or marked N/A with rationale
- [ ] CI workflows updated if required
- [ ] Follow-up issues filed for deferred work

## [M6] CLI query commands

---

title: "[M6] CLI query commands"
labels: ["milestone::M6"]
assignees: []
---

## Summary

git-ledger query UX.

## Links / Context

- Project plan: docs/PROJECT-PLAN.md
- Breakdown entry: docs/ISSUE-BREAKDOWN.md

## Deliverables

- [ ] Document deliverables before closing

## Implementation Notes

- Add details during execution

## Tests & Verification

- [ ] Capture verification plan in issue comments

## Definition of Done

- [ ] CMake build passes (debug & release, if applicable)
- [ ] Meson build passes (debug & release, if applicable)
- [ ] Tests executed or marked N/A with rationale
- [ ] CI workflows updated if required
- [ ] Follow-up issues filed for deferred work

## [M6] Tests

---

title: "[M6] Tests"
labels: ["milestone::M6"]
assignees: []
---

## Summary

unit + integration covering bitmap ops.

## Links / Context

- Project plan: docs/PROJECT-PLAN.md
- Breakdown entry: docs/ISSUE-BREAKDOWN.md

## Deliverables

- [ ] Document deliverables before closing

## Implementation Notes

- Add details during execution

## Tests & Verification

- [ ] Capture verification plan in issue comments

## Definition of Done

- [ ] CMake build passes (debug & release, if applicable)
- [ ] Meson build passes (debug & release, if applicable)
- [ ] Tests executed or marked N/A with rationale
- [ ] CI workflows updated if required
- [ ] Follow-up issues filed for deferred work

## [M7] Deep verify

---

title: "[M7] Deep verify"
labels: ["milestone::M7"]
assignees: []
---

## Summary

full ledger integrity routine.

## Links / Context

- Project plan: docs/PROJECT-PLAN.md
- Breakdown entry: docs/ISSUE-BREAKDOWN.md

## Deliverables

- [ ] Document deliverables before closing

## Implementation Notes

- Add details during execution

## Tests & Verification

- [ ] Capture verification plan in issue comments

## Definition of Done

- [ ] CMake build passes (debug & release, if applicable)
- [ ] Meson build passes (debug & release, if applicable)
- [ ] Tests executed or marked N/A with rationale
- [ ] CI workflows updated if required
- [ ] Follow-up issues filed for deferred work

## [M7] BLAKE3 checksum option

---

title: "[M7] BLAKE3 checksum option"
labels: ["milestone::M7"]
assignees: []
---

## Summary

compute & validate ref checksums.

## Links / Context

- Project plan: docs/PROJECT-PLAN.md
- Breakdown entry: docs/ISSUE-BREAKDOWN.md

## Deliverables

- [ ] Document deliverables before closing

## Implementation Notes

- Add details during execution

## Tests & Verification

- [ ] Capture verification plan in issue comments

## Definition of Done

- [ ] CMake build passes (debug & release, if applicable)
- [ ] Meson build passes (debug & release, if applicable)
- [ ] Tests executed or marked N/A with rationale
- [ ] CI workflows updated if required
- [ ] Follow-up issues filed for deferred work

## [M7] Documentation/examples

---

title: "[M7] Documentation/examples"
labels: ["milestone::M7"]
assignees: []
---

## Summary

sample encoders, server hooks.

## Links / Context

- Project plan: docs/PROJECT-PLAN.md
- Breakdown entry: docs/ISSUE-BREAKDOWN.md

## Deliverables

- [ ] Document deliverables before closing

## Implementation Notes

- Add details during execution

## Tests & Verification

- [ ] Capture verification plan in issue comments

## Definition of Done

- [ ] CMake build passes (debug & release, if applicable)
- [ ] Meson build passes (debug & release, if applicable)
- [ ] Tests executed or marked N/A with rationale
- [ ] CI workflows updated if required
- [ ] Follow-up issues filed for deferred work

## [M7] End-to-end tests

---

title: "[M7] End-to-end tests"
labels: ["milestone::M7"]
assignees: []
---

## Summary

corruption detection, checksum behavior.

## Links / Context

- Project plan: docs/PROJECT-PLAN.md
- Breakdown entry: docs/ISSUE-BREAKDOWN.md

## Deliverables

- [ ] Document deliverables before closing

## Implementation Notes

- Add details during execution

## Tests & Verification

- [ ] Capture verification plan in issue comments

## Definition of Done

- [ ] CMake build passes (debug & release, if applicable)
- [ ] Meson build passes (debug & release, if applicable)
- [ ] Tests executed or marked N/A with rationale
- [ ] CI workflows updated if required
- [ ] Follow-up issues filed for deferred work
