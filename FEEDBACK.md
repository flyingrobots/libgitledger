## ⚠️ C Header Over-Promises `lk_comp_run_policy` Semantics

The docstring incorrectly claims `lk_comp_run_policy` “mirrors lk\_comp\_run\_core semantics.” The policy implementation only updates `s->summary.policy` and does not touch `s->cases`, ownership, or allocation, which misleads integrators about lifetime and cleanup requirements.

```c
/* Run the policy checks.
* Precondition: `s` must be non-NULL.
* On success, updates `s->summary.policy` without allocating or freeing `s->cases`.
* Returns 0 on success; -1 on error (including NULL input).
*/
```

NOTES:

- Target: `include/ledger/compliance.h` (lines 72-76). **Major Contract Refactoring.** Explicitly state that only the summary field is updated.

### Status

- [ ] Resolved
- [ ] Was Already Fixed
- [ ] Ignored

{evidence and/or rationale}

## ⚠️ C Header Over-Promises `lk_comp_run_wasm` Semantics

The docstring incorrectly claims `lk_comp_run_wasm` “Mirrors lk\_comp\_run\_core semantics.” The WASM runner only updates `s->summary.wasm` and does not handle case array allocation/ownership, creating a misleading contract for callers.

```c
/* Run the wasm checks.
* Precondition: `s` must be non-NULL.
* On success, only updates `s->summary.wasm`; it leaves `s->cases` untouched.
* Returns 0 on success; -1 on error (including NULL input).
*/
```

NOTES:

- Target: `include/ledger/compliance.h` (lines 79-83). **Major Contract Refactoring.** Explicitly state that the function only modifies `s->summary.wasm` and leaves the `s->cases` array untouched.

### Status

- [ ] Resolved
- [ ] Was Already Fixed
- [ ] Ignored

{evidence and/or rationale}

## 🚨 CI/Docs Missing Explicit Submodule Requirement (Documentation)

UPDATE README.md and CONTRIBUTING.md with explicit git clone --recursive requirement. Documentation verification confirms the critical gap: README.md and CONTRIBUTING.md contain no mention of the git submodule requirement. Developers cloning without --recursive will silently obtain an empty external/ledger-kernel/ directory.

```bash
# Required action: Add explicit instructions to README.md and CONTRIBUTING.md
git clone --recursive https://github.com/[repo].git
# or for existing clones:
git submodule update --init --recursive
```

NOTES:

- Target: `README.md` (Quick Start) and `CONTRIBUTING.md` (Developer Setup). **Critical Fix** for developer onboarding stability.

### Status

- [ ] Resolved
- [ ] Was Already Fixed
- [ ] Ignored

{evidence and/or rationale}

## 🚨 CI/CD Pipelines Skip Submodule Initialization (CI/Makefile)

CRITICAL: CI/CD pipelines silently skip submodule initialization—guaranteed failures in production. Verification confirms zero submodule handling in .github/workflows/ci.yml, docs-site.yml, compliance.yml, and Makefile.

```
# Update all git clone operations or add an explicit step:
git submodule update --init --recursive
```

NOTES:

- Target: All CI workflow files and the `Makefile`. **Critical Fix** for build stability.

### Status

- [ ] Resolved
- [ ] Was Already Fixed
- [ ] Ignored

{evidence and/or rationale}

## 🚨 CI/CD Weak Link: Non-Explicit Submodule Config in `ci.yml`

The `ci.yml` workflow relies on an implicit default (no submodule fetch), which is ambiguous and error-prone. The intent must be made explicit.

```yaml
# Mandatory fixes required for .github/workflows/ci.yml:
# EITHER:
# with:
#   submodules: false # with comment explaining why kernel is not needed
# OR:
# with:
#   submodules: true # if CI build/tests depend on external/ledger-kernel
```

NOTES:

- Target: `.github/workflows/ci.yml`. **Critical Fix.** Make the `actions/checkout@v4` step's submodule behavior explicit.

### Status

- [ ] Resolved
- [ ] Was Already Fixed
- [ ] Ignored

{evidence and/or rationale}

## 🔧 C Header: `lk_comp_run_core` Missing Precise NULL Contract

The public header is missing documentation spelling out that the argument `s` must be **non-NULL** and that the function returns `-1` when callers violate that precondition.

```c
/* Params:
* - s: suite to populate. Must not be NULL. May be zero-initialized. On
* success, `s->cases` holds an owning array; call lk_comp_suite_free() to release.
* Returns:
* - 0 on success; -1 when `s` is NULL, allocation fails, or an internal
* error occurs. On failure, `s` is left in a consistent state (no leaked ownership).
*/
```

NOTES:

- Target: `include/ledger/compliance.h`. **Major Documentation Fix** for the public C API contract.

### Status

- [ ] Resolved
- [ ] Was Already Fixed
- [ ] Ignored

{evidence and/or rationale}

## 🐛 C Build: Unresolved Portability Blocker (`gmtime_r`)

CRITICAL: Unresolved portability blocker from previous review. The compliance library includes `src/compliance/report.c` which uses POSIX `gmtime_r`, unavailable in C99 or on Windows/MSVC.

```c
// Option A (Portable C99): Replace gmtime_r with standard gmtime in src/compliance/report.c:
time_t t=time(NULL);
struct tm* gp = gmtime(&t);
if (!gp) return -1;
struct tm g = *gp;
```

NOTES:

- Target: `meson.build` and `src/compliance/report.c`. **Critical Fix** for cross-platform build success.

### Status

- [ ] Resolved
- [ ] Was Already Fixed
- [ ] Ignored

{evidence and/or rationale}

## 📝 C Docs: Missing Comment for ISO Buffer Size

The `char iso[64]` buffer in `src/compliance/report.c` lacks a comment explaining why 64 bytes (since ISO 8601 is \~20 chars).

```c
// Suggested change structure for src/compliance/report.c:
char iso[64];  // ISO 8601 "YYYY-MM-DDTHH:MM:SSZ" needs ~20 chars; 64 provides headroom
```

NOTES:

- Target: `src/compliance/report.c` (line 88). **Trivial Fix** for code clarity.

### Status

- [ ] Resolved
- [ ] Was Already Fixed
- [ ] Ignored

{evidence and/or rationale}

## 🛠️ Python Tooling: `validate_dag.py` Needs Precise Error Handling

The DAG validator catches `RuntimeError` but treats all `gh` command failures as "missing issue." It needs to be able to distinguish between **"issue not found" (404)** versus **API/rate-limit errors**.

```
# Recommended action: Parse stderr or response code from gh_json to differentiate error types.
# (No specific code snippet provided, requires logic modification in the except block)
```

NOTES:

- Target: `tools/roadmap/validate_dag.py`. **Major Fix** for diagnostic accuracy.

### Status

- [ ] Resolved
- [ ] Was Already Fixed
- [ ] Ignored

{evidence and/or rationale}

## 🧹 C Reporting: Macro-Based Error Handling Violates Practices

The `W(x)` and `WP(slit)` macros embed `goto`-based error handling and use uppercase names. This hides control flow and violates modern C best practices.

```
// Recommended action: Replace macro uses with explicit inline checks, OR
// Rename macros to lowercase descriptive names (e.g., write_or_fail).
```

NOTES:

- Target: `src/compliance/report.c` (lines 117-136). **Trivial Fix** for maintainability.

### Status

- [ ] Resolved
- [ ] Was Already Fixed
- [ ] Ignored

{evidence and/or rationale}

## ⚠️ C Runtime: `checks_core.c` Rerun Failure Leaves Stale Summary

On a rerun where `calloc` chokes, the summary field is left stuck at `LK_COMP_PARTIAL` because it was reset after the old cases were freed but *before* the new memory allocation failed.

```c
// Suggested change structure for src/compliance/checks_core.c:
if (!s) return -1;
s->summary.core = LK_COMP_NA; // Move reset BEFORE calloc attempt
// ... free old cases ...
// ... calloc attempt ...
// ... if success, set s->summary.core = LK_COMP_PARTIAL
```

NOTES:

- Target: `src/compliance/checks_core.c`. **Major Fix** for run idempotency and reporting correctness.

### Status

- [ ] Resolved
- [ ] Was Already Fixed
- [ ] Ignored

{evidence and/or rationale}

## 🧪 C Test: `compliance_suite_test.c` Fails to Verify Pristine State

The test validates that `core` is preserved on a partial run, but fails to assert that the untouched `wasm` group remains in its zero-initialized `LK_COMP_PASS` state.

```c
// Suggested assertions to add to tests/compliance_suite_test.c:
assert(s.summary.wasm == LK_COMP_PASS); // After first lk_comp_run_all
// ...
assert(s.summary.wasm == LK_COMP_PASS); // After second lk_comp_run_all
```

NOTES:

- Target: `tests/compliance_suite_test.c`. **Trivial Fix** to strengthen test invariants.

### Status

- [ ] Resolved
- [ ] Was Already Fixed
- [ ] Ignored

{evidence and/or rationale}

## 📝 Docs: Remove Duplicate Outdated Mermaid Diagram

Lines 127-237 contain an older version of the DAG that lacks the milestone subgraphs, theme configuration, node class definitions, and root-node styling present in the new diagram (lines 6-126). This is an orphaned duplicate.

```
// Delete lines 127-237 in docs/ROADMAP-DAG.md entirely.
```

NOTES:

- Target: `docs/ROADMAP-DAG.md`. **Trivial Cleanup.**

### Status

- [ ] Resolved
- [ ] Was Already Fixed
- [ ] Ignored

{evidence and/or rationale}
