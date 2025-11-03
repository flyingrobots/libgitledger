#include "ledger/compliance.h"
#include <stdio.h>
#include <string.h>
#include <time.h>
#include <errno.h>

static const char* status_str(lk_comp_status s){
  switch (s){
    case LK_COMP_PASS: return "PASS";
    case LK_COMP_PARTIAL: return "PARTIAL";
    case LK_COMP_FAIL: return "FAIL";
    default: return "N/A";
  }
}

static int json_escape(FILE* f, const char* s){
  for (; *s; ++s){
    unsigned char c=(unsigned char)*s;
    if (c=='"' || c=='\\') { if (fputc('\\',f)==EOF || fputc(c,f)==EOF) return -1; }
    else if (c=='\n') { if (fputs("\\n",f)==EOF) return -1; }
    else if (c=='\r') { if (fputs("\\r",f)==EOF) return -1; }
    else if (c=='\t') { if (fputs("\\t",f)==EOF) return -1; }
    else if (c=='\b') { if (fputs("\\b",f)==EOF) return -1; }
    else if (c=='\f') { if (fputs("\\f",f)==EOF) return -1; }
    else if (c<=0x1F) {
      char buf[7];
      static const char hex[] = "0123456789abcdef";
      buf[0]='\\'; buf[1]='u'; buf[2]='0'; buf[3]='0';
      buf[4]=hex[(c>>4)&0xF]; buf[5]=hex[c&0xF]; buf[6]='\0';
      if (fputs(buf,f)==EOF) return -1;
    } else { if (fputc(c,f)==EOF) return -1; }
  }
  return 0;
}

int lk_comp_report_write(const lk_comp_suite* s, const char* out_path){
  if (!s || !out_path) return -1;
  FILE* f=fopen(out_path,"wb");
  if (!f) return -1;
  int ok = 1;
  char iso[64];
  time_t t=time(NULL);
  struct tm g;
  #if defined(_WIN32)
    if (gmtime_s(&g, &t) != 0) { ok = 0; }
  #else
    struct tm* pg = gmtime(&t);
    if (!pg) { ok = 0; }
    else g = *pg;
  #endif
  if (ok) {
    if (strftime(iso,sizeof(iso),"%Y-%m-%dT%H:%M:%SZ",&g) == 0) ok = 0;
  }
  if (!ok) { fclose(f); remove(out_path); return -1; }

  #define W(x) do { if ((x)<0) { ok=0; goto done; } } while(0)
  #define WP(slit) do { if (fputs((slit),f)==EOF) { ok=0; goto done; } } while(0)

  WP("{\n");
  WP("  \"implementation\": \""); W(json_escape(f,s->implementation?s->implementation:"libgitledger")); WP("\",\n");
  WP("  \"version\": \""); W(json_escape(f,s->version?s->version:"0.0.0")); WP("\",\n");
  WP("  \"date\": \""); WP(iso); WP("\",\n");
  WP("  \"results\": [\n");
  const size_t MAX_CASES = 10000u;
  if (s->ncases > MAX_CASES) { ok=0; goto done; }
  for (size_t i=0;i<s->ncases;i++){
    const lk_comp_case* c=&s->cases[i];
    WP("    {\n");
    WP("      \"id\": \""); W(json_escape(f,c->id?c->id:"?")); WP("\",\n");
    WP("      \"clauses\": [");
    for (size_t j=0;j<c->nclauses;j++){
      if (j) WP(", \""); else WP("\"");
      W(json_escape(f,c->clauses[j])); WP("\"");
    }
    WP("],\n");
    WP("      \"status\": \""); WP(status_str(c->status)); WP("\",\n");
    WP("      \"notes\": \""); W(json_escape(f,c->notes?c->notes:"")); WP("\"\n");
    WP("    }");
    WP(i+1<s->ncases?",\n":"\n");
  }
  WP("  ],\n");
  WP("  \"summary\": {\n");
  WP("    \"core\": \""); WP(status_str(s->summary.core)); WP("\",\n");
  WP("    \"policy\": \""); WP(status_str(s->summary.policy)); WP("\",\n");
  WP("    \"wasm\": \""); WP(status_str(s->summary.wasm)); WP("\"\n");
  WP("  }\n");
  WP("}\n");
done:
  if (fflush(f)==EOF || ferror(f)) ok=0;
  fclose(f);
  if (!ok) { remove(out_path); return -1; }
  return 0;
}
