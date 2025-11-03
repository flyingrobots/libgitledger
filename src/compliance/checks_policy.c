#include "ledger/compliance.h"

int lk_comp_run_policy(lk_comp_suite* s){
  if (!s) return -1;
  s->summary.policy = LK_COMP_PARTIAL;
  return 0;
}
