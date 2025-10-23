#include "libgitledger/version.h"

#include <stdio.h>

static const gitledger_semantic_version_t METAGRAPH_VERSION_VALUE = {0, 1, 0};
static char                               gitledger_version_buffer[16];

gitledger_semantic_version_t gitledger_semantic_version(void)
{
    return METAGRAPH_VERSION_VALUE;
}

const char* gitledger_semantic_version_string(void)
{
    int const written = snprintf(gitledger_version_buffer, sizeof(gitledger_version_buffer),
                                 "%d.%d.%d", METAGRAPH_VERSION_VALUE.major,
                                 METAGRAPH_VERSION_VALUE.minor, METAGRAPH_VERSION_VALUE.patch);

    if (written < 0)
        {
            return "";
        }

    return gitledger_version_buffer;
}
