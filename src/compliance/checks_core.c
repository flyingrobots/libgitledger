#include "ledger/compliance.h"
#include <stdlib.h>

int lk_comp_run_core(lk_comp_suite* s)
{
    if (!s)
        return -1;
    /* Reset summary for this group before attempting allocation so a failure
       path leaves a consistent NA state. */
    s->summary.core = LK_COMP_NA;
    // Skeleton: populate minimal cases and mark N/A or PARTIAL where pending.
    // If re-invoked, explicitly free/reset the cases array to avoid leaks
    // without coupling to lk_comp_suite_free() internals.
    if (s->cases)
        {
            free(s->cases);
            s->cases  = NULL;
            s->ncases = 0;
        }
    static const char* c1_clauses[] = {"FS-10"};
    static const char* c2_clauses[] = {"FS-7", "FS-8"};
    static const char* c3_clauses[] = {"FS-11"};
    lk_comp_case*      arr          = (lk_comp_case*) calloc(3, sizeof(lk_comp_case));
    if (!arr)
        return -1;
    s->cases  = arr;
    s->ncases = 3;
    // Designated initializers: fields not listed are intentionally left
    // zero/NULL. Update this block if new mandatory fields are added.
    s->cases[0]     = (lk_comp_case) {.id       = "C-1",
                                      .clauses  = c1_clauses,
                                      .nclauses = 1,
                                      .status   = LK_COMP_NA,
                                      .notes    = "Canonicalization pending"};
    s->cases[1]     = (lk_comp_case) {.id       = "C-2",
                                      .clauses  = c2_clauses,
                                      .nclauses = 2,
                                      .status   = LK_COMP_NA,
                                      .notes    = "Non-FF ref test pending"};
    s->cases[2]     = (lk_comp_case) {.id       = "C-3",
                                      .clauses  = c3_clauses,
                                      .nclauses = 1,
                                      .status   = LK_COMP_NA,
                                      .notes    = "Timestamp monotonicity pending"};
    s->summary.core = LK_COMP_PARTIAL;
    return 0;
}
