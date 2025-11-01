#include "gitledger/version.h"

#include <stddef.h>

static int str_eq(const char* a, const char* b)
{
    for (;;)
        {
            char ca = *a++;
            char cb = *b++;
            if (ca != cb)
                {
                    return 0;
                }
            if (ca == '\0')
                {
                    return 1;
                }
        }
}

int main(void)
{
    char   buf[16];
    size_t n = gitledger_semantic_version_snprintf(buf, sizeof buf);

    /* Expect "0.1.0" (length 5) and NUL termination within our buffer. */
    if (n != 5)
        {
            return 2;
        }

    if (!str_eq(buf, "0.1.0"))
        {
            return 3;
        }

    const char* s = gitledger_semantic_version_string();
    if (!s || !str_eq(s, "0.1.0"))
        {
            return 4;
        }

    return 0;
}
