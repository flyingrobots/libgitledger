#include "libgitledger/version.h"

#include <assert.h>
#include <stdio.h>
#include <string.h>

int main(void)
{
    gitledger_semantic_version_t const version      = gitledger_semantic_version();
    const char* const                  version_text = gitledger_semantic_version_string();

    assert(version.major == 0);
    assert(version.minor == 1);
    assert(version.patch == 0);
    assert(strcmp(version_text, "0.1.0") == 0);

    (void) printf("libgitledger version %d.%d.%d (%s)\n", version.major, version.minor,
                  version.patch, version_text);
    return 0;
}
