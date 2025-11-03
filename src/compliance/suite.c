#include "ledger/compliance.h"
#include <stdlib.h>

int lk_comp_run_all(lk_comp_suite* s, int run_core, int run_policy, int run_wasm)
{
    if (!s)
        return -1;
    // Reset overall summary to a known baseline; each enabled sub-runner
    // (core/policy/wasm) sets its own field. This makes retries idempotent
    // and avoids stale values when a subset of runners are executed.
    s->summary.core   = LK_COMP_NA;
    s->summary.policy = LK_COMP_NA;
    s->summary.wasm   = LK_COMP_NA;
    int rc            = 0;
    if (run_core)
        {
            rc = lk_comp_run_core(s);
            if (rc)
                return rc;
        }
    if (run_policy)
        {
            rc = lk_comp_run_policy(s);
            if (rc)
                return rc;
        }
    if (run_wasm)
        {
            rc = lk_comp_run_wasm(s);
            if (rc)
                return rc;
        }
    return 0;
}

void lk_comp_suite_free(lk_comp_suite* s)
{
    if (!s)
        return;
    if (s->cases)
        {
            free(s->cases);
            s->cases = NULL;
        }
    s->ncases = 0;
}
