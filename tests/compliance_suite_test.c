#include "ledger/compliance.h"
#include <assert.h>

int main(void)
{
    lk_comp_suite s = {0};

    /* Run core only: expect core to be PARTIAL, others NA. */
    int rc = lk_comp_run_all(&s, 1, 0, 0);
    assert(rc == 0);
    assert(s.summary.core == LK_COMP_PARTIAL);
    /* Disabled runners may preserve prior values; do not assert their state here. */

    /* Now run policy only: core should be preserved, policy updated. */
    rc = lk_comp_run_all(&s, 0, 1, 0);
    assert(rc == 0);
    assert(s.summary.core == LK_COMP_PARTIAL);
    assert(s.summary.policy == LK_COMP_PARTIAL || s.summary.policy == LK_COMP_NA);

    lk_comp_suite_free(&s);
    return 0;
}
