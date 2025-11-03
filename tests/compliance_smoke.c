#include "ledger/compliance.h"
int main(void){
  lk_comp_suite s = {0};
  int rc = lk_comp_run_all(&s, 1, 1, 1);
  lk_comp_suite_free(&s);
  return rc ? 1 : 0;
}

