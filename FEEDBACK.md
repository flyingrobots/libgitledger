## Critical Docs Fix: Add Submodule Instructions to README/CONTRIBUTING

- [ ] Resolved
- [ ] Was Already Fixed
- [ ] Ignored

> In README.md (Quick Start section) and CONTRIBUTING.md (Developer Setup section) — add explicit instructions that the repo contains git submodules and must be cloned with submodules; include the two commands shown in the review: "git clone --recursive https://github.com/[repo].git" and the alternative for existing clones "git submodule update --init --recursive", place them prominently in those sections (near existing clone/setup steps), and briefly note that failing to use --recursive will leave external/ledger-kernel empty and break builds.

NOTES:
- This is a critical fix to prevent developer setup failures due to empty submodules.

---

## Critical CI Fix: Enforce Submodule Initialization in All Workflows and Makefile

- [ ] Resolved
- [ ] Was Already Fixed
- [ ] Ignored

> In external/ledger-kernel around lines 1 to 1: CI and repo docs never initialize Git submodules so external/ledger-kernel remains empty in fresh clones and CI jobs; update every git clone in .github/workflows/ci.yml, docs-site.yml, and compliance.yml to include --recursive (or add a post-clone step running git submodule update --init --recursive), add an explicit recursive clone or submodule init target in the Makefile (e.g., clone or bootstrap target that runs git clone --recursive or git submodule update --init --recursive), and add a prominent note in README.md describing the required submodule init/recursive clone command and any Makefile target to run in local developer setup.

NOTES:
- This ensures CI pipelines fetch the `external/ledger-kernel` submodule correctly.

---

## Fix CI: Explicitly Set Submodule Configuration in `ci.yml`

- [ ] Resolved
- [ ] Was Already Fixed
- [ ] Ignored

> external/ledger-kernel (context at lines 1-1): CI and docs lack explicit submodule handling; update .github/workflows/ci.yml to explicitly set submodules: true if the CI build/tests require external/ledger-kernel (or set submodules: false with a comment explaining why the kernel is not needed), update README.md Getting Started to show cloning with submodules (git clone --recursive ... or git submodule update --init --recursive) and clarify what directories are populated, and add a short section in CONTRIBUTING.md (or equivalent onboarding doc) that states whether the submodule is required, when to initialize it, and the exact commands to do so.

NOTES:
- The CI workflow (`ci.yml`) is the weak link; make its intent explicit (`submodules: true` or `false`) and document the rationale in the workflow file.

---

## Major Fix: Reset `summary.core` Before `calloc` in `checks_core.c`

- [ ] Resolved
- [ ] Was Already Fixed
- [ ] Ignored

> In src/compliance/checks_core.c around lines 6 to 43, reset s->summary.core to LK_COMP_NA before you free/reset s->cases and attempt the calloc so that if allocation fails the suite summary is not left as LK_COMP_PARTIAL; then after successfully allocating and filling the new cases set s->summary.core back to LK_COMP_PARTIAL. Ensure the failure path (when calloc returns NULL) leaves summary.core as LK_COMP_NA.

NOTES:
- This prevents a partial success summary if memory allocation fails during a rerun.

---

## Major Fix: Paginate GitHub Comments in `sweep_issues.py`

- [ ] Resolved
- [ ] Was Already Fixed
- [ ] Ignored

> Stop gagging on page-one tunnel vision. You still hit only the first 30 REST comments, so the moment the auto-generated note slips past page one you forget it exists and splatter a brand-new comment. Run this weekly and every busy issue becomes a landfill of duplicates. Paginate the comment fetch before deciding whether to PATCH or POST.

```python
# Suggested change structure for tools/roadmap/sweep_issues.py:
comments: list[dict] = []
page = 1
while True:
  try:
      chunk = json.loads(run([
          "gh",
          "api",
          f"repos/{owner}/{repo}/issues/{number}/comments",
          "-f", "per_page=100",
          "-f", f"page={page}",
      ]))
  except RuntimeError:
      comments = []
      break
  if not isinstance(chunk, list) or not chunk:
      break
  comments.extend(chunk)
  if len(chunk) < 100:
      break
  page += 1
````

---

## Minor Fix: Remove Duplicate Doc-Comment Block for `lk_comp_suite`

- [ ] Resolved
- [ ] Was Already Fixed
- [ ] Ignored

> In include/ledger/compliance.h around lines 29 to 40, there are two consecutive doc-comment blocks describing the same lk\_comp\_suite struct; remove the first (earlier) comment block so only the second, more comprehensive documentation remains, ensuring spacing and comment formatting remain consistent after deletion.

NOTES:
- Trivial cleanup for documentation consistency in `include/ledger/compliance.h`.

---

## Minor Test Fix: Tighten Assertion in `compliance_suite_test.c`

- [ ] Resolved
- [ ] Was Already Fixed
- [ ] Ignored

> In tests/compliance\_suite\_test.c around line 18, the assertion allowing LK\_COMP\_NA is overly permissive given checks\_policy.c sets s-\>summary.policy = LK\_COMP\_PARTIAL on success and the test already asserts rc == 0; change the assertion to require exactly LK\_COMP\_PARTIAL (remove LK\_COMP\_NA) so the test enforces the intended contract and will catch regressions.

```c
// Suggested change structure for tests/compliance_suite_test.c:
assert(s.summary.policy == LK_COMP_PARTIAL);
```

---

## Trivial Test Fix: Verify Untouched Groups Remain Pristine

- [ ] Resolved
- [ ] Was Already Fixed
- [ ] Ignored

> In tests/compliance\_suite\_test.c around lines 4 to 22, the test fails to assert that untouched groups remain at their zero-initialized PASS state; after running policy-only (the second lk\_comp\_run\_all call) add an assertion that s.summary.wasm == LK\_COMP\_PASS to ensure the wasm group was not modified (keep existing checks for core and policy), e.g., insert a check immediately after the policy assertions to validate wasm remains LK\_COMP\_PASS.

NOTES:
- Ensures the `wasm` field is not unintentionally reset by the second `lk_comp_run_all` call.
