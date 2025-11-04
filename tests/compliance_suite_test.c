#include "ledger/compliance.h"
#include <assert.h>

int main(void)
{
    lk_comp_suite s = {0};

    /* Run core only: expect core to be PARTIAL; wasm remains pristine (PASS). */
    int rc = lk_comp_run_all(&s, 1, 0, 0);
    assert(rc == 0);
    assert(s.summary.core == LK_COMP_PARTIAL);
    assert(s.summary.wasm == LK_COMP_PASS);

    /* Now run policy only: core should be preserved, policy updated. */
    rc = lk_comp_run_all(&s, 0, 1, 0);
    assert(rc == 0);
    assert(s.summary.core == LK_COMP_PARTIAL);
    /* Policy-only run should set policy to PARTIAL on success. */
    assert(s.summary.policy == LK_COMP_PARTIAL);
    /* wasm group was not executed; should remain pristine (PASS). */
    assert(s.summary.wasm == LK_COMP_PASS);

    lk_comp_suite_free(&s);
    return 0;
}
