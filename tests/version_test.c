#include "gitledger/version.h"

#include <inttypes.h>
#include <stddef.h>
#include <stdio.h>
#include <string.h>

int main(void)
{
    gitledger_semantic_version_t const version = gitledger_semantic_version();

    char         buffer[64];
    size_t const written      = gitledger_semantic_version_snprintf(buffer, sizeof buffer);
    size_t const expected_len = strlen("0.1.0");

    if (written != expected_len)
        {
            fprintf(stderr,
                    "version_test: expected snprintf length %" PRIuMAX ", got %" PRIuMAX "\n",
                    (uintmax_t) expected_len, (uintmax_t) written);
            fprintf(stderr, "version_test: buffer contents >>%s<<\n", buffer);
            return 1;
        }
    if (strcmp(buffer, "0.1.0") != 0)
        {
            fprintf(stderr, "version_test: buffer mismatch expected '0.1.0', got '%s'\n", buffer);
            return 1;
        }

    const char* const version_text = gitledger_semantic_version_string();
    if (version_text == NULL)
        {
            fprintf(stderr, "version_test: gitledger_semantic_version_string() returned NULL\n");
            return 1;
        }
    if (strcmp(version_text, "0.1.0") != 0)
        {
            fprintf(stderr, "version_test: expected version string '0.1.0', got '%s'\n",
                    version_text);
            return 1;
        }

    if (version.major != 0 || version.minor != 1 || version.patch != 0)
        {
            fprintf(stderr, "version_test: expected semantic version 0.1.0, got %u.%u.%u\n",
                    version.major, version.minor, version.patch);
            return 1;
        }

    (void) printf("libgitledger version %u.%u.%u (%s)\n", version.major, version.minor,
                  version.patch, version_text);

    /* snprintf semantics: n==0 must return required length and not write. */
    {
        char   tiny[1] = {'X'}; /* sentinel to detect unintended writes */
        size_t ret     = gitledger_semantic_version_snprintf(tiny, 0);
        if (ret != expected_len)
            {
                fprintf(stderr, "version_test: n=0 expected %" PRIuMAX ", got %" PRIuMAX "\n",
                        (uintmax_t) expected_len, (uintmax_t) ret);
                return 1;
            }
        if (tiny[0] != 'X')
            {
                fprintf(stderr, "version_test: n=0 wrote to buffer unexpectedly\n");
                return 1;
            }
    }

    /* Truncation: n=5 must NUL-terminate and return required length. */
    {
        char small[5];
        memset(small, 'Z', sizeof small);
        size_t ret = gitledger_semantic_version_snprintf(small, sizeof small);
        if (ret != expected_len)
            {
                fprintf(stderr, "version_test: n=5 expected %" PRIuMAX ", got %" PRIuMAX "\n",
                        (uintmax_t) expected_len, (uintmax_t) ret);
                return 1;
            }
        if (small[sizeof small - 1] != '\0')
            {
                fprintf(stderr, "version_test: n=5 buffer not NUL-terminated\n");
                return 1;
            }
        if (strncmp(small, "0.1.", sizeof small - 1) != 0)
            {
                fprintf(stderr, "version_test: n=5 prefix mismatch, got '%s'\n", small);
                return 1;
            }
    }
    return 0;
}
