#include "libgitledger/version.h"

#include <stddef.h>

static const gitledger_semantic_version_t METAGRAPH_VERSION_VALUE = {0, 1, 0};
static char                               gitledger_version_buffer[16];

static int
write_decimal(unsigned int value, char **cursor, size_t *remaining)
{
    char   digits[10];
    size_t idx = 0U;

    do
        {
            if (idx >= sizeof(digits))
                {
                    return 0;
                }
            digits[idx++] = (char) ('0' + (value % 10U));
            value /= 10U;
        }
    while (value != 0U);

    if (idx > *remaining)
        {
            return 0;
        }

    while (idx-- > 0U)
        {
            **cursor = digits[idx];
            (*cursor)++;
            (*remaining)--;
        }

    return 1;
}

gitledger_semantic_version_t gitledger_semantic_version(void)
{
    return METAGRAPH_VERSION_VALUE;
}

const char* gitledger_semantic_version_string(void)
{
    char * cursor    = gitledger_version_buffer;
    size_t remaining = sizeof(gitledger_version_buffer);

    if (!write_decimal((unsigned int) METAGRAPH_VERSION_VALUE.major, &cursor, &remaining))
        {
            return "";
        }

    if (remaining == 0U)
        {
            return "";
        }

    *cursor++ = '.';
    remaining--;

    if (!write_decimal((unsigned int) METAGRAPH_VERSION_VALUE.minor, &cursor, &remaining))
        {
            return "";
        }

    if (remaining == 0U)
        {
            return "";
        }

    *cursor++ = '.';
    remaining--;

    if (!write_decimal((unsigned int) METAGRAPH_VERSION_VALUE.patch, &cursor, &remaining))
        {
            return "";
        }

    if (remaining == 0U)
        {
            return "";
        }

    *cursor = '\0';
    return gitledger_version_buffer;
}
