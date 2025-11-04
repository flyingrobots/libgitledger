// Minimal compliance harness types for Ledger-Kernel
#pragma once
#include <stddef.h>

/**
 * Compliance test result status.
 * - PASS: All requirements satisfied.
 * - PARTIAL: Some requirements met, others pending; not a failure.
 * - FAIL: One or more required checks failed.
 * - NA: Not applicable or not yet implemented on this platform/config.
 */
typedef enum
{
    LK_COMP_PASS    = 0,
    LK_COMP_PARTIAL = 1,
    LK_COMP_FAIL    = 2,
    LK_COMP_NA      = 3
} lk_comp_status;

typedef struct
{
    const char*    id;      // e.g., "C-1"
    const char**   clauses; // non-owning: must outlive lk_comp_case
    size_t         nclauses;
    lk_comp_status status;
    const char*    notes; // optional
} lk_comp_case;

/**
 * A compliance suite run. The suite owns the cases array (cases), which
 * must be released with lk_comp_suite_free(). The strings referenced by
 * cases[i].id/clauses[j]/notes and the implementation/version pointers are
 * non-owning and must outlive the suite.
 */
/**
 * Opaque container for a compliance run. The suite owns the `cases` array and
 * must be released with lk_comp_suite_free(). Caller-provided strings such as
 * `implementation`, `version`, and any case `id`/`clauses[]`/`notes` pointers
 * are non-owning and must outlive the suite.
 */
typedef struct
{
    const char*   implementation; // e.g., libgitledger (non-owning)
    const char*   version;        // from library (non-owning)
    lk_comp_case* cases;          // owning array allocated by suite
    size_t        ncases;
    struct
    {
        lk_comp_status core;   // Summary for core checks
        lk_comp_status policy; // Summary for policy checks
        lk_comp_status wasm;   // Summary for wasm checks
    } summary;
} lk_comp_suite;

/**
 * Run the core checks.
 *
 * Params:
 *  - s: suite to populate. May be zero-initialized. On success, `s->cases`
 *       holds an owning array; call lk_comp_suite_free() to release.
 * Returns:
 *  - 0 on success; -1 on allocation or internal error. On failure, `s` is
 *    left in a consistent state (no leaked ownership).
 */
int lk_comp_run_core(lk_comp_suite* s);

/** Run the policy checks. Mirrors lk_comp_run_core semantics. */
int lk_comp_run_policy(lk_comp_suite* s);

/** Run the wasm checks. Mirrors lk_comp_run_core semantics. */
int lk_comp_run_wasm(lk_comp_suite* s);

/** Write JSON report to out_path. Returns 0 on success; -1 on I/O error. */
int lk_comp_report_write(const lk_comp_suite* s, const char* out_path);

/**
 * Run selected groups in order and update the suite summary.
 *
 * Each enabled group is reset to LK_COMP_NA before its sub-runner executes;
 * disabled groups preserve any previously computed summary so callers can
 * invoke groups incrementally across multiple calls.
 *
 * Returns the first non-zero error from a sub-runner, or 0 on success.
 */
int lk_comp_run_all(lk_comp_suite* s, int run_core, int run_policy, int run_wasm);

/** Free resources owned by the suite (cases array). Safe on NULL. */
void lk_comp_suite_free(lk_comp_suite* s);
