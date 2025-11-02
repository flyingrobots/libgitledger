#include "ledger/compliance.h"
#include <stdio.h>
#include <string.h>
#include <time.h>

static const char* status_str(lk_comp_status s){
  switch (s){
    case LK_COMP_PASS: return "PASS";
    case LK_COMP_PARTIAL: return "PARTIAL";
    case LK_COMP_FAIL: return "FAIL";
    default: return "N/A";
  }
}

static void json_escape(FILE* f, const char* s){
  for (; *s; ++s){
    unsigned char c=(unsigned char)*s;
    if (c=='"' || c=='\\') { fputc('\\',f); fputc(c,f); }
    else if (c=='\n') { fputs("\\n",f); }
    else { fputc(c,f); }
  }
}

int lk_comp_report_write(const lk_comp_suite* s, const char* out_path){
  FILE* f=fopen(out_path,"wb");
  if (!f) return -1;
  char iso[64];
  time_t t=time(NULL); struct tm g; gmtime_r(&t,&g);
  strftime(iso,sizeof(iso),"%Y-%m-%dT%H:%M:%SZ",&g);

  fputs("{\n",f);
  fputs("  \"implementation\": \"",f); json_escape(f,s->implementation?s->implementation:"libgitledger"); fputs("\",\n",f);
  fputs("  \"version\": \"",f); json_escape(f,s->version?s->version:"0.0.0"); fputs("\",\n",f);
  fputs("  \"date\": \"",f); fputs(iso,f); fputs("\",\n",f);
  fputs("  \"results\": [\n",f);
  for (size_t i=0;i<s->ncases;i++){
    const lk_comp_case* c=&s->cases[i];
    fputs("    {\n",f);
    fputs("      \"id\": \"",f); json_escape(f,c->id?c->id:"?"); fputs("\",\n",f);
    fputs("      \"clauses\": [",f);
    for (size_t j=0;j<c->nclauses;j++){
      fputs(j?", \"":"\"",f); json_escape(f,c->clauses[j]); fputs("\"",f);
    }
    fputs("],\n",f);
    fputs("      \"status\": \"",f); fputs(status_str(c->status),f); fputs("\",\n",f);
    fputs("      \"notes\": \"",f); json_escape(f,c->notes?c->notes:""); fputs("\"\n",f);
    fputs("    }",f);
    fputs(i+1<s->ncases?",\n":"\n",f);
  }
  fputs("  ],\n",f);
  fputs("  \"summary\": {\n",f);
  fputs("    \"core\": \"",f); fputs(status_str(s->summary.core),f); fputs("\",\n",f);
  fputs("    \"policy\": \"",f); fputs(status_str(s->summary.policy),f); fputs("\",\n",f);
  fputs("    \"wasm\": \"",f); fputs(status_str(s->summary.wasm),f); fputs("\"\n",f);
  fputs("  }\n",f);
  fputs("}\n",f);
  fclose(f);
  return 0;
}

