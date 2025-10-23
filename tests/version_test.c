#include "libgitledger/version.h"

#include <assert.h>
#include <stddef.h>
#include <stdio.h>
#include <string.h>

int main(void)
{
    gitledger_semantic_version_t const version = gitledger_semantic_version();

    char buffer[64];
    size_t const written = gitledger_semantic_version_snprintf(buffer, sizeof buffer);
    if (written != strlen("0.1.0"))
        {
            return 1;
        }
    assert(strcmp(buffer, "0.1.0") == 0);

    const char* const version_text = gitledger_semantic_version_string();
    assert(version_text != NULL);
    assert(strcmp(version_text, "0.1.0") == 0);

    assert(version.major == 0);
    assert(version.minor == 1);
    assert(version.patch == 0);

    (void) printf("libgitledger version %u.%u.%u (%s)\n", version.major, version.minor,
                  version.patch, version_text);
    return 0;
}
