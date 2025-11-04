// Minimal compliance harness types for Ledger-Kernel
#pragma once
#include <stddef.h>

#ifdef __cplusplus
extern "C"
{
#endif

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

    /**
     * A single compliance case/result row.
     *
     * Purpose:
     *  - Describes one requirement (by identifier) and the evaluation status
     *    for the current implementation under test.
     *
     * Ownership/Lifetime:
     *  - All pointer members (`id`, `clauses`, each `clauses[i]`, `notes`) are
     *    non-owning views supplied by the caller. They must remain valid for the
     *    lifetime of any report generation that references them.
     *  - The suite owns only the array of `lk_comp_case` structs when produced by
     *    lk_comp_run_core(); callers must release that array via
     *    lk_comp_suite_free().
     */
    typedef struct
    {
        const char*    id;      // e.g., "C-1" (non-owning)
        const char**   clauses; // non-owning: points to caller memory
        size_t         nclauses;
        lk_comp_status status;
        const char*    notes; // optional (non-owning)
    } lk_comp_case;

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
     * Precondition:
     *  - `s` must be non-NULL and in a defined state. Passing an uninitialized
     *    struct with indeterminate pointers is undefined behavior. A
     *    zero-initialized struct is valid. If `s->cases` is non-NULL, this
     *    function may free and replace it.
     *
     * Semantics:
     *  - On success, `s->cases` holds an owning array; call lk_comp_suite_free()
     *    to release it.
     *
     * Returns:
     *  - 0 on success; -1 on error (including `s == NULL`, allocation failure, or
     *    other internal errors). On failure, `s` is left in a consistent state
     *    (no leaked ownership).
     */
    int lk_comp_run_core(lk_comp_suite* s);

    /**
     * Run the policy checks.
     *
     * Precondition:
     *  - `s` must be non-NULL.
     *
     * Semantics:
     *  - On success, only updates `s->summary.policy`. It does not allocate,
     *    free, or otherwise mutate `s->cases`.
     *
     * Returns:
     *  - 0 on success; -1 on error (including NULL input).
     */
    int lk_comp_run_policy(lk_comp_suite* s);

    /**
     * Run the wasm checks.
     *
     * Precondition:
     *  - `s` must be non-NULL.
     *
     * Semantics:
     *  - On success, only updates `s->summary.wasm`. It does not allocate,
     *    free, or otherwise mutate `s->cases`.
     *
     * Returns:
     *  - 0 on success; -1 on error (including NULL input).
     */
    int lk_comp_run_wasm(lk_comp_suite* s);

    /**
     * Write a JSON report to the given path.
     *
     * Returns 0 on success; -1 on error. Errors include invalid or NULL input
     * parameters, structural validation failures of the suite (e.g., inconsistent
     * case/clause arrays), and I/O errors while writing the file.
     */
    int lk_comp_report_write(const lk_comp_suite* s, const char* out_path);

    /**
     * Run selected groups in order and update the suite summary.
     *
     * Precondition:
     *  - `s` must be non-NULL.
     *
     * @param s          Suite to update.
     * @param run_core   Non-zero to run core checks; zero to skip.
     * @param run_policy Non-zero to run policy checks; zero to skip.
     * @param run_wasm   Non-zero to run WASM checks; zero to skip.
     *
     * Semantics:
     *  - Each enabled group is reset to LK_COMP_NA before its sub-runner executes.
     *  - Disabled groups preserve any previously computed summary, allowing
     *    incremental execution across multiple calls.
     *  - Execution halts on the first sub-runner error.
     *
     * Returns:
     *  - 0 on success; -1 on error (including NULL input or any sub-runner failure).
     */
    int lk_comp_run_all(lk_comp_suite* s, int run_core, int run_policy, int run_wasm);

    /**
     * Free resources owned by the suite (cases array).
     * Calling with NULL is a safe no-op (returns immediately).
     */
    void lk_comp_suite_free(lk_comp_suite* s);

#ifdef __cplusplus
} /* extern "C" */
#endif
