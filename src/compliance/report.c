#include "ledger/compliance.h"
#include <errno.h>
#include <stdio.h>
#include <string.h>
#include <time.h>

static const char* status_str(lk_comp_status s)
{
    switch (s)
        {
        case LK_COMP_PASS:
            return "PASS";
        case LK_COMP_PARTIAL:
            return "PARTIAL";
        case LK_COMP_FAIL:
            return "FAIL";
        default:
            return "N/A";
        }
}

static int json_escape(FILE* f, const char* s)
{
    for (; *s; ++s)
        {
            unsigned char c = (unsigned char) *s;
            if (c == '"' || c == '\\')
                {
                    if (fputc('\\', f) == EOF || fputc(c, f) == EOF)
                        return -1;
                }
            else if (c == '\n')
                {
                    if (fputs("\\n", f) == EOF)
                        return -1;
                }
            else if (c == '\r')
                {
                    if (fputs("\\r", f) == EOF)
                        return -1;
                }
            else if (c == '\t')
                {
                    if (fputs("\\t", f) == EOF)
                        return -1;
                }
            else if (c == '\b')
                {
                    if (fputs("\\b", f) == EOF)
                        return -1;
                }
            else if (c == '\f')
                {
                    if (fputs("\\f", f) == EOF)
                        return -1;
                }
            else if (c <= 0x1F)
                {
                    char              buf[7];
                    static const char hex[] = "0123456789abcdef";
                    buf[0]                  = '\\';
                    buf[1]                  = 'u';
                    buf[2]                  = '0';
                    buf[3]                  = '0';
                    buf[4]                  = hex[(c >> 4) & 0xF];
                    buf[5]                  = hex[c & 0xF];
                    buf[6]                  = '\0';
                    if (fputs(buf, f) == EOF)
                        return -1;
                }
            else
                {
                    if (fputc(c, f) == EOF)
                        return -1;
                }
        }
    return 0;
}

static int write_case(FILE* f, const lk_comp_case* c)
{
    if (!f || !c)
        return -1;
    if (c->nclauses && !c->clauses)
        return -1;
    if (fputs("    {\n", f) == EOF)
        return -1;
    if (fputs("      \"id\": \"", f) == EOF)
        return -1;
    if (json_escape(f, c->id ? c->id : "?") < 0)
        return -1;
    if (fputs("\",\n", f) == EOF)
        return -1;
    if (fputs("      \"clauses\": [", f) == EOF)
        return -1;
    for (size_t j = 0; j < c->nclauses; j++)
        {
            if (!c->clauses[j])
                return -1;
            if (j)
                {
                    if (fputs(", \"", f) == EOF)
                        return -1;
                }
            else
                {
                    if (fputs("\"", f) == EOF)
                        return -1;
                }
            if (json_escape(f, c->clauses[j]) < 0)
                return -1;
            if (fputs("\"", f) == EOF)
                return -1;
        }
    if (fputs("],\n", f) == EOF)
        return -1;
    if (fputs("      \"status\": \"", f) == EOF)
        return -1;
    if (fputs(status_str(c->status), f) == EOF)
        return -1;
    if (fputs("\",\n", f) == EOF)
        return -1;
    if (fputs("      \"notes\": \"", f) == EOF)
        return -1;
    if (json_escape(f, c->notes ? c->notes : "") < 0)
        return -1;
    if (fputs("\"\n", f) == EOF)
        return -1;
    if (fputs("    }", f) == EOF)
        return -1;
    return 0;
}

int lk_comp_report_write(const lk_comp_suite* s, const char* out_path)
{
    if (!s || !out_path)
        return -1;
    FILE* f = fopen(out_path, "wb");
    if (!f)
        return -1;
    int       ok = 1;
    char      iso[64]; // ISO 8601 "YYYY-MM-DDTHH:MM:SSZ" fits in < 32 bytes; 64 is ample headroom.
    time_t    t = time(NULL);
    struct tm g;
#if defined(_WIN32)
    if (gmtime_s(&g, &t) != 0)
        {
            ok = 0;
        }
#else
    struct tm* pg = gmtime(&t);
    if (!pg)
        {
            ok = 0;
        }
    else
        g = *pg;
#endif
    if (ok)
        {
            if (strftime(iso, sizeof(iso), "%Y-%m-%dT%H:%M:%SZ", &g) == 0)
                ok = 0;
        }
    if (!ok)
        {
            fclose(f);
            remove(out_path);
            return -1;
        }

// Helper-style macros to keep write sites readable. They set ok=0 and
// jump to cleanup on error.
#define write_or_fail(expr)                                                                        \
    do                                                                                             \
        {                                                                                          \
            if ((expr) < 0)                                                                        \
                {                                                                                  \
                    ok = 0;                                                                        \
                    goto done;                                                                     \
                }                                                                                  \
        }                                                                                          \
    while (0)
#define write_str_or_fail(s)                                                                       \
    do                                                                                             \
        {                                                                                          \
            if (fputs((s), f) == EOF)                                                              \
                {                                                                                  \
                    ok = 0;                                                                        \
                    goto done;                                                                     \
                }                                                                                  \
        }                                                                                          \
    while (0)

    write_str_or_fail("{\n");
    write_str_or_fail("  \"implementation\": \"");
    write_or_fail(json_escape(f, s->implementation ? s->implementation : "libgitledger"));
    write_str_or_fail("\",\n");
    write_str_or_fail("  \"version\": \"");
    write_or_fail(json_escape(f, s->version ? s->version : "0.0.0"));
    write_str_or_fail("\",\n");
    write_str_or_fail("  \"date\": \"");
    write_str_or_fail(iso);
    write_str_or_fail("\",\n");
    write_str_or_fail("  \"results\": [\n");
    const size_t MAX_CASES = 10000u;
    if (s->ncases > MAX_CASES)
        {
            ok = 0;
            goto done;
        }
    if (s->ncases && !s->cases)
        {
            ok = 0;
            goto done;
        }
    for (size_t i = 0; i < s->ncases; i++)
        {
            const lk_comp_case* c = &s->cases[i];
            if (write_case(f, c) < 0)
                {
                    ok = 0;
                    goto done;
                }
            write_str_or_fail(i + 1 < s->ncases ? ",\n" : "\n");
        }
    write_str_or_fail("  ],\n");
    write_str_or_fail("  \"summary\": {\n");
    write_str_or_fail("    \"core\": \"");
    write_str_or_fail(status_str(s->summary.core));
    write_str_or_fail("\",\n");
    write_str_or_fail("    \"policy\": \"");
    write_str_or_fail(status_str(s->summary.policy));
    write_str_or_fail("\",\n");
    write_str_or_fail("    \"wasm\": \"");
    write_str_or_fail(status_str(s->summary.wasm));
    write_str_or_fail("\"\n");
    write_str_or_fail("  }\n");
    write_str_or_fail("}\n");
done:
    if (fflush(f) == EOF || ferror(f))
        ok = 0;
    fclose(f);
    if (!ok)
        {
            remove(out_path);
            return -1;
        }
    return 0;
}
