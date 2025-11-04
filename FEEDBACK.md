## Fix Docs - Remove Duplicate Outdated Mermaid Diagram

- [ ] Resolved
- [x] Was Already Fixed
- [ ] Ignored


> 127-237: Remove the duplicate, outdated Mermaid diagram. Lines 127-237 contain an older version of the DAG that lacks the milestone subgraphs, theme configuration, node class definitions, and root-node styling present in the new diagram (lines 6-126). This orphaned duplicate will confuse readers and cause maintenance drift. Delete lines 127-237 entirely, leaving only the enhanced diagram.

NOTES:
- Rationale: Duplicate block (lines 127–237) was removed in a prior pass; only the enhanced diagram remains at the top of docs/ROADMAP-DAG.md.

---

## Fix Header - Document Public Runner Contracts

- [x] Resolved
- [ ] Was Already Fixed
- [ ] Ignored

> 45-47: Document the public runner contracts. These APIs are still naked—no parameter requirements, no return-value semantics, nothing. For a public surface, that’s unacceptable. Add Doxygen-style docs explaining expected inputs (NULL handling, suite ownership), side effects, and exact success/error codes so callers know how to use them.

NOTES:
- Rationale: Added Doxygen-style docs to lk_comp_run_core/policy/wasm describing preconditions (non-NULL), semantics, and return codes in include/ledger/compliance.h.

---

## Critical Docs Fix: Add Submodule Instructions to README/CONTRIBUTING

- [ ] Resolved
- [x] Was Already Fixed
- [ ] Ignored

> UPDATE README.md and CONTRIBUTING.md with explicit git clone --recursive requirement. Documentation verification confirms the critical gap: README.md and CONTRIBUTING.md contain no mention of the git submodule requirement. Developers cloning without --recursive will silently obtain an empty external/ledger-kernel/ directory, causing downstream build or runtime failures.

NOTES:
- Rationale: README.md + CONTRIBUTING.md now include explicit recursive clone/update commands and a Makefile `bootstrap` target.

---

## Critical CI Fix: Enforce Submodule Initialization in All Workflows/Makefile

- [x] Resolved
- [ ] Was Already Fixed
- [ ] Ignored

> CRITICAL: CI/CD pipelines silently skip submodule initialization—guaranteed failures in production. Verification confirms zero submodule handling in any workflow: `.github/workflows/ci.yml`, `docs-site.yml`, `compliance.yml`, and `Makefile`. Add `--recursive` to all `git clone` operations or add explicit `git submodule update --init --recursive` after clone in each workflow/Makefile target.

NOTES:
- Rationale: compliance.yml uses `submodules: true`; ci.yml and docs-site.yml set `submodules: false`; Makefile adds `bootstrap` target for local clones.

---

## Critical CI Fix: Explicitly Set Submodule Configuration in `ci.yml`

- [ ] Resolved
- [x] Was Already Fixed
- [ ] Ignored

> CRITICAL: CI/CD wiring and documentation incomplete—add explicit submodule handling and setup docs. Update `.github/workflows/ci.yml` to explicitly set `submodules: true` (if required by tests) or `submodules: false` (if not required) and add a comment explaining the decision.

NOTES:
- Rationale: All jobs in ci.yml now explicitly set `submodules: false` (with comments); compliance.yml remains `true` as required.

---

## Critical Header Fix: Add `extern "C"` Guard

- [x] Resolved
- [ ] Was Already Fixed
- [ ] Ignored

> Add the extern "C" guard yesterday. Public C headers without an extern "C" wrapper are amateur hour. Any C++ consumer will see mangled names and fail to link against the C objects immediately. Fix the linkage contract.

```c
// Suggested change structure for include/ledger/compliance.h:
#ifdef __cplusplus
extern "C" {
#endif
// ... all declarations ...
#ifdef __cplusplus
}
#endif
```

---

## Fix C - Reset `summary.core` Before Allocation Attempt

- [x] Resolved
- [ ] Was Already Fixed
- [ ] Ignored

> In src/compliance/checks\_core.c around lines 6 to 43, reset s-\>summary.core to LK\_COMP\_NA before you free/reset s-\>cases and attempt the calloc so that if allocation fails the suite summary is not left as LK\_COMP\_PARTIAL; then after successfully allocating and filling the new cases set s-\>summary.core back to LK\_COMP\_PARTIAL. Ensure the failure path (when calloc returns NULL) leaves summary.core as LK\_COMP\_NA.

NOTES:
- Prevents a "partial success" report if a subsequent memory allocation failure occurs.

---

## Fix C - Refactor Macro-Based Error Handling in `report.c`

- [x] Resolved
- [ ] Was Already Fixed
- [ ] Ignored

> In src/compliance/report.c around lines 117-136 the W(x) and WP(slit) macros embed goto-based error handling and use uppercase names that look like constants; change them to a clearer pattern: either replace macro uses with explicit inline error checks that set ok=0 and jump to cleanup or rename and rework the macros to lowercase, descriptive names (e.g., `write_or_fail` and `write_str_or_fail`) so their control-flow behavior is obvious.

NOTES:
- Trivial/opinionated fix to improve readability and adherence to modern C practices.

---

## Fix Header - Document `NULL` Contract Precisely

- [x] Resolved
- [ ] Was Already Fixed
- [ ] Ignored

> 52-57: Document the NULL contract precisely. `lk_comp_run_core(NULL)` currently returns -1, yet the doc blithely talks about allocation/internal errors. Spell out that the argument must be non-NULL and that the function returns -1 when callers violate that precondition.

NOTES:
- Update the Doxygen documentation for `lk_comp_run_core` to explicitly state the requirement for a non-`NULL` argument and clarify the `-1` return code meaning.

---

## Trivial Test Fix: Verify Untouched Groups Remain Pristine

- [x] Resolved
- [ ] Was Already Fixed
- [ ] Ignored

> In tests/compliance\_suite\_test.c around lines 4 to 22, the test fails to assert that untouched groups remain at their zero-initialized PASS state; after running policy-only (the second lk\_comp\_run\_all call) add an assertion that s.summary.wasm == LK\_COMP\_PASS to ensure the wasm group was not modified (keep existing checks for core and policy), e.g., insert a check immediately after the policy assertions to validate wasm remains LK\_COMP\_PASS.

NOTES:
- Ensures the `wasm` summary is not unintentionally modified during partial runs.

---

## Minor Fix: Tighten Assertion in `compliance_suite_test.c`

- [x] Resolved
- [ ] Was Already Fixed
- [ ] Ignored

> In tests/compliance\_suite\_test.c around line 18, the assertion allowing LK\_COMP\_NA is overly permissive given checks\_policy.c sets s-\>summary.policy = LK\_COMP\_PARTIAL on success and the test already asserts rc == 0; change the assertion to require exactly LK\_COMP\_PARTIAL (remove LK\_COMP\_NA) so the test enforces the intended contract and will catch regressions.

---

## Minor Fix: Remove Duplicate Doc-Comment Block for `lk_comp_suite`

- [x] Resolved
- [ ] Was Already Fixed
- [ ] Ignored

> In include/ledger/compliance.h around lines 29 to 40, there are two consecutive doc-comment blocks describing the same `lk_comp_suite` struct; remove the first (earlier) comment block so only the second, more comprehensive documentation remains, ensuring spacing and comment formatting remain consistent after deletion.
