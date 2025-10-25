#include "gitledger/version.h"

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
            fprintf(stderr, "version_test: expected snprintf length %zu, got %zu\n", expected_len,
                    written);
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
    return 0;
}
