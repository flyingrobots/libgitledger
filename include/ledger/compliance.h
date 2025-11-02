// Minimal compliance harness types for Ledger‑Kernel
#pragma once
#include <stddef.h>

typedef enum {
  LK_COMP_PASS = 0,
  LK_COMP_PARTIAL = 1,
  LK_COMP_FAIL = 2,
  LK_COMP_NA = 3
} lk_comp_status;

typedef struct {
  const char* id;               // e.g., "C-1"
  const char** clauses;         // e.g., {"FS-10"}
  size_t nclauses;
  lk_comp_status status;
  const char* notes;            // optional
} lk_comp_case;

typedef struct {
  const char* implementation;   // e.g., libgitledger
  const char* version;          // from library
  lk_comp_case* cases;
  size_t ncases;
  struct {
    lk_comp_status core;
    lk_comp_status policy;
    lk_comp_status wasm;
  } summary;
} lk_comp_suite;

int lk_comp_run_core(lk_comp_suite* s);
int lk_comp_run_policy(lk_comp_suite* s);
int lk_comp_run_wasm(lk_comp_suite* s);

int lk_comp_report_write(const lk_comp_suite* s, const char* out_path);

