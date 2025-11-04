## Fix Docs - Remove Duplicate Outdated Mermaid Diagram

 - [x] Resolved
- [ ] Was Already Fixed
- [ ] Ignored

> [!note]- Rationale/Evidence
> Removed the duplicate Mermaid block (docs/ROADMAP-DAG.md lines 127–237) and kept the single enhanced diagram at the top. Verified via containerized format-check and reviewed rendered file. Commit: see docs cleanup in chore/issues-roadmap.

> Apply this diff to remove the duplicate: [Lines 127-237 removed entirely]

NOTES:
- Delete lines 127-237 in `docs/ROADMAP-DAG.md` entirely, leaving only the enhanced diagram at the beginning of the file. This removes an orphaned, outdated diagram version.

---

## Fix Docs - Document Compliance Public Runner Contracts

 - [x] Resolved
- [ ] Was Already Fixed
- [ ] Ignored

> [!note]- Rationale/Evidence
> Added Doxygen-style docs to the public compliance APIs in include/ledger/compliance.h describing ownership, NULL handling, summary semantics, and return codes. This clarifies runner contracts for callers.

> These APIs are still naked—no parameter requirements, no return-value semantics, nothing. For a public surface, that’s unacceptable. Add Doxygen-style docs explaining expected inputs (NULL handling, suite ownership), side effects, and exact success/error codes so callers know how to use them.

NOTES:
- Target: `include/ledger/compliance.h` (Lines 45-47). Add Doxygen-style documentation to the public runner contracts.


---

## Fix Docs - Add Submodule Instructions to README/CONTRIBUTING

 - [x] Resolved
- [ ] Was Already Fixed
- [ ] Ignored

> [!note]- Rationale/Evidence
> README.md and CONTRIBUTING.md now include explicit submodule instructions (git clone --recursive and git submodule update --init --recursive) and a Makefile bootstrap target. Skipping --recursive is noted to leave external/ledger-kernel empty. Added `make bootstrap` quickstart.

> In README.md (Quick Start section) and CONTRIBUTING.md (Developer Setup section) — add explicit instructions that the repo contains git submodules and must be cloned with submodules; include the two commands shown in the review: "git clone --recursive https://github.com/[repo].git" and the alternative for existing clones "git submodule update --init --recursive", place them prominently in those sections (near existing clone/setup steps), and briefly note that failing to use --recursive will leave external/ledger-kernel empty and break builds.

NOTES:
- Critical documentation update for developer setup.


---

## Fix CI - Enforce Submodule Initialization in All Workflows

 - [x] Resolved
- [ ] Was Already Fixed
- [ ] Ignored

> [!note]- Rationale/Evidence
> Workflows are explicit about submodule intent: compliance.yml uses `submodules: true`; docs-site.yml uses `submodules: false`; ci.yml sets `submodules: false`. Added a `bootstrap` target in the Makefile for local clones. This enforces initialization where needed while avoiding unnecessary fetches.

> In external/ledger-kernel around lines 1 to 1: CI and repo docs never initialize Git submodules so external/ledger-kernel remains empty in fresh clones and CI jobs; update every git clone in .github/workflows/ci.yml, docs-site.yml, and compliance.yml to include --recursive (or add a post-clone step running git submodule update --init --recursive), add an explicit recursive clone or submodule init target in the Makefile (e.g., clone or bootstrap target that runs git clone --recursive or git submodule update --init --recursive), and add a prominent note in README.md describing the required submodule init/recursive clone command and any Makefile target to run in local developer setup.

NOTES:
- Critical fix for CI pipeline stability (CI jobs are silently failing to fetch the submodule).

---

## Fix CI - Explicitly Set `submodules: false` in `ci.yml`

 - [x] Resolved
- [ ] Was Already Fixed
- [ ] Ignored

> [!note]- Rationale/Evidence
> linux-matrix, windows-msvc, and freestanding-linux jobs in .github/workflows/ci.yml now set `submodules: false` explicitly on checkout steps with comments. This documents that the kernel is not required for the standard matrix.

> external/ledger-kernel (context at lines 1-1): CI and docs lack explicit submodule handling; update .github/workflows/ci.yml to explicitly set submodules: true if the CI build/tests require external/ledger-kernel (or set submodules: false with a comment explaining why the kernel is not needed), update README.md Getting Started to show cloning with submodules (git clone --recursive ... or git submodule update --init --recursive) and clarify what directories are populated, and add a short section in CONTRIBUTING.md (or equivalent onboarding doc) that states whether the submodule is required, when to initialize it, and the exact commands to do so.

NOTES:
- This clarifies the intent of the `ci.yml` workflow—make explicit that the kernel is *not* needed for standard CI.

---

## Fix C - Document/Fix `lk_comp_run_all` Summary Reset

 - [x] Resolved
- [ ] Was Already Fixed
- [ ] Ignored

> [!note]- Rationale/Evidence
> Changed lk_comp_run_all to reset only enabled summary fields and documented the behavior in the header. Added a Meson test (compliance_suite) to verify that a prior successful core summary is preserved across a subsequent policy-only run.

> In src/compliance/suite.c around lines 4 to 23, the function lk_comp_run_all resets s->summary.core, s->summary.policy and s->summary.wasm to LK_COMP_NA at the start which masks earlier sub-runner results on failure; remove those three initialization lines so each sub-runner is responsible for initializing its own summary field (or if intentional, add a clear comment explaining the reason and intended idempotency), and verify/adjust lk_comp_run_core, lk_comp_run_policy and lk_comp_run_wasm to explicitly set their respective summary fields before returning.

```c
// Suggested change structure for src/compliance/suite.c (add comment if keeping reset):
int lk_comp_run_all(lk_comp_suite* s, ...){
  if (!s) return -1;
  // Reset all fields to NA; each enabled sub-runner will update its own
  s->summary.core = LK_COMP_NA;
  s->summary.policy = LK_COMP_NA;
  s->summary.wasm = LK_COMP_NA;
  // ... rest of the function
}
```

---

## Fix Python - Improve GitHub API Error Handling in DAG Validator

- [x] Resolved
- [ ] Was Already Fixed
- [ ] Ignored

> [!note]- Rationale/Evidence
> The validator now treats 404/“could not resolve” as missing issues and collects them, while other `gh` failures (rate limits/network) print an explicit error with the exception class and abort. This prevents conflating transient API failures with genuinely missing issues.


> In tools/roadmap/validate\_dag.py around lines 54-58, replace the bare "except Exception" with targeted handling: call gh\_json inside a try and catch the specific exception(s) it raises (e.g., subprocess.CalledProcessError or the library-specific error), parse the error/exit code/output to detect a 404 "issue not found" and only append num to missing in that case, implement a short retry/backoff for transient network/timeout errors, and for other/unexpected errors log the error details and re-raise (or fail) instead of swallowing them.

NOTES:
- Target: `gh_json` call around lines 54-58. Need to distinguish 404 errors from API rate limits or network issues.

---

## Fix C - Document ISO Buffer Size in `report.c`

- [x] Resolved
- [ ] Was Already Fixed
- [ ] Ignored

> [!note]- Rationale/Evidence
> Added a comment explaining ISO 8601 size and that a 64-byte buffer provides headroom.


> Add comment: `char iso[64]; // ISO 8601 "YYYY-MM-DDTHH:MM:SSZ" needs ~20 chars; 64 provides headroom`

NOTES:
- Target: `src/compliance/report.c` line 88. Trivial nitpick.

  
---

## Fix CI - Apply Explicit `submodules: false` to All Checkout Steps

- [x] Resolved
- [ ] Was Already Fixed
- [ ] Ignored

> [!note]- Rationale/Evidence
> Added `submodules: false` to windows-msvc and freestanding-linux job checkouts to match linux-matrix; intent is now consistent across all ci.yml jobs.


> In .github/workflows/ci.yml (around lines 42-44, and add at lines 105-106 and 119-120), the checkout steps for the windows-msvc and freestanding-linux jobs are missing the explicit submodules: false flag; update each actions/checkout@v4 step in those jobs to include a with: block containing submodules: false (matching the linux-matrix job) so all checkout steps explicitly disable submodule fetching.

```yaml
# Suggested structure for other jobs in .github/workflows/ci.yml:
      - name: Checkout
        uses: actions/checkout@v4
        with:
          submodules: false
```

---

## Fix Docs - Test/Document `useMaxWidth` in Mermaid Config

- [x] Resolved
- [ ] Was Already Fixed
- [ ] Ignored

> [!note]- Rationale/Evidence
> Switched to `useMaxWidth: true` for responsive diagrams and confirmed rendering; added edge convention comments for clarity.

> In docs/ROADMAP-DAG.md around line 7, the Mermaid init uses "useMaxWidth: false" which can break diagrams in constrained viewports; either remove that setting or change it to a responsive-safe value (e.g., true) so diagrams adapt to container width, and add a brief comment above the init explaining why a non-default was chosen if you must keep it; after the change, test the diagram in narrow/mobile and embedded doc containers and document the compatibility decision in the file.

NOTES:
- Target: `docs/ROADMAP-DAG.md` line 7 (`%%{init: {... useMaxWidth: false ...}%%`).
  
---

## Fix Docs - Document Mermaid Edge Conventions

- [x] Resolved
- [ ] Was Already Fixed
- [ ] Ignored

> [!note]- Rationale/Evidence
> Added a brief comment block above the hard dependency list clarifying `==>` (hard/blocking) and `-.->` (soft/informational) edge meanings.

> In docs/ROADMAP-DAG.md around lines 123 to 125, add a short comment block immediately before the hard dependency list explaining Mermaid edge conventions: state that `==>` denotes hard/blocking dependencies (the left node must complete before the right starts) and that `-.->` denotes soft/informational relationships (epic-to-children or non-blocking links); keep the comment concise, formatted as a Markdown/HTML comment or plain text note so maintainers see the convention before the N53 ==\> N51 / N56 ==\> N55 lines.

---

## Fix Docs - Remove Redundant Mermaid Inline Styling

- [x] Resolved
- [ ] Was Already Fixed
- [ ] Ignored

> [!note]- Rationale/Evidence
> Replaced repeated inline `style` directives with a single `class ... root;` declaration to apply the root styling.

> In docs/ROADMAP-DAG.md around lines 126 to 137, there is redundant inline styling for nodes N28,N29,N35,N36,N38,N39,N47,N50,N54,N58,N59,N61 that duplicates the earlier classDef root; remove these inline style lines and instead add those nodes to the root class (e.g., via a single "class N28,N29,... root" declaration) so they inherit styling, or if inline styles are truly required add a brief comment explaining why Mermaid class application cannot be used and keep the inline styles.

NOTES:
- Preferred fix is to replace 12 lines of `style Nxx...` with a single `class N28,N29,... root;` declaration.

---

## Fix C - Decouple `checks_core.c` from `lk_comp_suite_free`

- [x] Resolved
- [ ] Was Already Fixed
- [ ] Ignored

> [!note]- Rationale/Evidence
> Replaced the internal call to lk_comp_suite_free(s) with an explicit free/reset of `s->cases` and `s->ncases`, avoiding tight coupling to suite_free internals while ensuring idempotent reruns.

> In src/compliance/checks\_core.c around lines 11 to 14, the runner currently calls lk\_comp\_suite\_free(s) to avoid leaks when re-running, which creates tight coupling and risks freeing more than just s-\>cases; instead either (A) update the public header include/ledger/compliance.h to document that lk\_comp\_run\_core is idempotent and callers may expect the suite to be reinitialized on repeated calls, or (B) change this location to only free the specific s-\>cases resource (e.g., free/reset the cases pointer and count) rather than invoking the full suite free function so the runner does not depend on lk\_comp\_suite\_free's internal behavior; choose one approach and implement it consistently with surrounding API (update header docs if choosing A).

NOTES:
> - Option (B) is cleaner: replace `lk_comp_suite_free(s)` with explicit freeing/resetting of `s->cases`.

---

## Fix C - Document Designated Initializers in `checks_core.c`

- [x] Resolved
- [ ] Was Already Fixed
- [ ] Ignored

> [!note]- Rationale/Evidence
> Added a comment above the designated initializers noting that omitted fields are intentionally left zero/NULL and to update if new mandatory fields appear.

> In src/compliance/checks\_core.c around lines 23 to 37, the compound literal designated initializers for s-\>cases[0..2] rely on C's zero-initialization for any future or omitted fields which is brittle and undocumented; add a concise comment immediately above these initializers stating that omitted fields are intentionally left zero/NULL and that designated initializers are used deliberately (optionally mention to update the comment if new mandatory fields are added), or replace with an explicit initializer helper or memset+partial assignment if you want explicit control over all fields.

---

## Fix C - Refactor Macro-Based Error Handling in `report.c`

- [x] Resolved
- [ ] Was Already Fixed
- [ ] Ignored

> [!note]- Rationale/Evidence
> Renamed uppercase macros to `write_or_fail` / `write_str_or_fail` for clarity and replaced call sites. Control flow remains explicit (ok=0; goto done) on write failures.

> In src/compliance/report.c around lines 117-136 the W(x) and WP(slit) macros embed goto-based error handling and use uppercase names that look like constants; change them to a clearer pattern: either replace macro uses with explicit inline error checks that set ok=0 and jump to cleanup (i.e., expand the if (x)\<0 / if (fputs(...)==EOF) checks at call sites) or rename and rework the macros to lowercase, descriptive names (e.g., write\_or\_fail and write\_str\_or\_fail) so their control-flow behavior is obvious; ensure the chosen fix preserves the ok=0 and goto done behavior or replaces it with an explicit, local cleanup path and update call sites accordingly.

---

## Fix C - Extract Helper Function for Case Serialization

- [x] Resolved
- [ ] Was Already Fixed
- [ ] Ignored

> [!note]- Rationale/Evidence
> Extracted `static int write_case(FILE*, const lk_comp_case*)` to validate and serialize a single case; the main loop now delegates to this helper and handles the trailing comma logic.

> In src/compliance/report.c around lines 160-196, the per-case serialization loop is deeply nested with multiple goto done paths; extract a helper function like static int write\_case(FILE \*f, const lk\_comp\_case \*c) that performs all validations (check c non-NULL, if c-\>nclauses then c-\>clauses non-NULL, ensure each c-\>clauses[j] non-NULL), writes the JSON for id, clauses array, status and notes (using json\_escape and WP/W as currently done) and returns 0 on success or -1 on failure; then replace the inner body of the for loop with a call to write\_case(f, \&s-\>cases[i]) and handle the returned error by setting ok = 0 and jumping to done, keeping the comma/newline output logic in the outer loop (i + 1 \< s-\>ncases) so serialization formatting is preserved.

---

## Fix C - Only Reset Summary Fields for Enabled Runners

- [x] Resolved
- [ ] Was Already Fixed
- [ ] Ignored

> [!note]- Rationale/Evidence
> Updated src/compliance/suite.c to reset only the summaries for enabled runners (core/policy/wasm flags). Added a Meson test (tests/compliance_suite_test.c) that first runs core only, then policy only, and verifies the prior core summary is preserved. Header docs in include/ledger/compliance.h explain the incremental semantics.

> In src/compliance/suite.c around lines 8 to 13, the code unconditionally resets all s-\>summary fields to LK\_COMP\_NA which wipes prior results for runners not being executed; change the reset behavior to only clear the summary fields for runners that are actually enabled in this call (i.e., check the function's core/policy/wasm boolean flags and only set s-\>summary.core/policy/wasm = LK\_COMP\_NA when the corresponding flag is true), and update related comments to reflect this change; also run/update tests or add a unit test that calls lk\_comp\_run\_all in separate steps to verify previous successful summaries for disabled runners are preserved.

NOTES:
- This prevents a successful run (e.g., core only) from being wiped out by a later partial run (e.g., policy only).

---

## Fix Python - Enforce Executable Permissions or Remove Shebang

- [x] Resolved
- [ ] Was Already Fixed
- [ ] Ignored

> [!note]- Rationale/Evidence
> Removed the shebang from tools/roadmap/validate_dag.py since it is invoked via Python in the Makefile; avoids EXE001 without changing invocation.

> In tools/roadmap/validate\_dag.py around line 1, the file contains a shebang but is not executable which triggers EXE001; either remove the shebang line to reflect that the script is invoked via $(PYTHON) in the Makefile, or make the file executable (chmod +x tools/roadmap/validate\_dag.py) and update the Makefile to call the script directly (tools/roadmap/validate\_dag.py) — pick one approach and apply it consistently across repo.

---

## Fix Python - Update Deprecated `typing` Aliases

- [x] Resolved
- [ ] Was Already Fixed
- [ ] Ignored

> [!note]- Rationale/Evidence
> Switched to built-in generics (list/tuple/dict) and imported `Sequence` from collections.abc; updated annotations throughout the validator.

> In tools/roadmap/validate\_dag.py around line 7, the import uses deprecated typing aliases (Sequence, Tuple, List, Dict); replace these with the non-deprecated forms and update annotations accordingly: import Sequence from collections.abc if still needed, and switch typing.Tuple/List/Dict to built-in lowercase generics (tuple, list, dict) in all type hints (e.g., Tuple[str, str] → tuple[str, str], List[Tuple[str, str]] → list[tuple[str, str]], Dict[str, int] → dict[str, int]); ensure imports at line 7 reflect only what’s required after changes.

---

## Fix Python - Replace Dict Comprehension with `dict()`

- [x] Resolved
- [ ] Was Already Fixed
- [ ] Ignored

> [!note]- Rationale/Evidence
> Replaced `{n: num for (n,num) in nodes}` with `dict(nodes)` for clarity and to satisfy Ruff C416.

> In tools/roadmap/validate\_dag.py at line 48, the dict comprehension "node\_to\_issue = {n: num for (n,num) in nodes}" is unnecessary; replace it with the simpler, idiomatic "node\_to\_issue = dict(nodes)" to avoid the Ruff C416 warning and produce the same mapping assuming nodes is an iterable of (key, value) tuples.

---

## Fix Python - Improve Mermaid Lint Warning Message

- [x] Resolved
- [ ] Was Already Fixed
- [ ] Ignored

> [!note]- Rationale/Evidence
> The mermaid-lint warning now includes the exception class name and message: `(... skipped (RuntimeError): ...)`.

> In tools/roadmap/validate\_dag.py around lines 51 to 54, the except block prints a generic warning and omits the specific exception type; change the print to include the exception class name and message (e.g. include type(e).**name** and the error text or use repr(e)) so the log shows which specific error occurred and its details; keep the same exception tuple and formatting consistent with existing messages.

```python
# Suggested change structure for tools/roadmap/validate_dag.py:
except (RuntimeError, FileNotFoundError) as e:
    print(f"validate_dag: warning: mermaid lint skipped ({type(e).__name__}): {e}")
```
  
---

## Fix Python - Optimize Cycle Detection Initialization/Reconstruction

- [x] Resolved
- [ ] Was Already Fixed
- [ ] Ignored

> [!note]- Rationale/Evidence
> Switched color-map initialization to `dict.fromkeys(nodes_set, WHITE)` and used list unpacking `[ *stack[i:], v ]` when reconstructing a cycle path.

> In tools/roadmap/validate\_dag.py around lines 76 to 112, replace the dict comprehension initializing colors with dict.fromkeys(nodes\_set, WHITE) to satisfy Ruff C420, and change the cycle reconstruction expression stack[i:] + [v] to use list unpacking [\*stack[i:], v] to address Ruff RUF005; keep the same semantics and variable names, only alter these two expressions.

```python
# Suggested changes for tools/roadmap/validate_dag.py:
# (1) Line 85:
color: dict[str, int] = dict.fromkeys(nodes_set, WHITE)
# (2) Line 101:
cycle_path = [*stack[i:], v]
```
