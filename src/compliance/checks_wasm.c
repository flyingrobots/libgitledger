#include "ledger/compliance.h"

int lk_comp_run_wasm(lk_comp_suite* s)
{
    if (!s)
        return -1;
    s->summary.wasm = LK_COMP_NA;
    return 0;
}
