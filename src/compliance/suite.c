#include "ledger/compliance.h"
#include <stdlib.h>

extern int lk_comp_run_core(lk_comp_suite* s);
extern int lk_comp_run_policy(lk_comp_suite* s);
extern int lk_comp_run_wasm(lk_comp_suite* s);

int lk_comp_run_all(lk_comp_suite* s, int run_core, int run_policy, int run_wasm){
  s->summary.core = LK_COMP_NA;
  s->summary.policy = LK_COMP_NA;
  s->summary.wasm = LK_COMP_NA;
  if (run_core) lk_comp_run_core(s);
  if (run_policy) lk_comp_run_policy(s);
  if (run_wasm) lk_comp_run_wasm(s);
  return 0;
}

