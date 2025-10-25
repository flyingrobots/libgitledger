#include "libgitledger/version.h"

#include <stddef.h>
#include <stdint.h>

static const gitledger_semantic_version_t GITLEDGER_VERSION_VALUE = {0, 1, 0};

enum
{
    GL_VERSION_DECIMAL_DIGIT_CAP = 10,
    GL_VERSION_DECIMAL_BASE      = 10,
    /* 10 digits * 3 + 2 dots + 1 NUL = 33; round up for safety. */
    GL_VERSION_BUFFER_SIZE = 34
};

static char gitledger_version_buffer[GL_VERSION_BUFFER_SIZE];

static int write_decimal(uint32_t value, char** cursor, size_t* remaining)
{
    char   digits[GL_VERSION_DECIMAL_DIGIT_CAP];
    size_t idx = 0U;

    do
        {
            if (idx >= sizeof digits)
                {
                    return 0;
                }
            digits[idx++] = (char) ('0' + (value % GL_VERSION_DECIMAL_BASE));
            value /= GL_VERSION_DECIMAL_BASE;
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
    return GITLEDGER_VERSION_VALUE;
}

size_t gitledger_semantic_version_snprintf(char* buf, size_t n)
{
    if (buf == NULL || n == 0)
        {
            return 0U;
        }

    char*  cursor    = buf;
    size_t remaining = n;

    if (!write_decimal(GITLEDGER_VERSION_VALUE.major, &cursor, &remaining))
        {
            return 0U;
        }

    if (remaining <= 1U)
        {
            return 0U;
        }

    *cursor++ = '.';
    remaining--;

    if (!write_decimal(GITLEDGER_VERSION_VALUE.minor, &cursor, &remaining))
        {
            return 0U;
        }

    if (remaining <= 1U)
        {
            return 0U;
        }

    *cursor++ = '.';
    remaining--;

    if (!write_decimal(GITLEDGER_VERSION_VALUE.patch, &cursor, &remaining))
        {
            return 0U;
        }

    if (remaining == 0U)
        {
            return 0U;
        }

    *cursor = '\0';
    return (size_t) (cursor - buf);
}

const char* gitledger_semantic_version_string(void)
{
    if (gitledger_semantic_version_snprintf(gitledger_version_buffer,
                                            sizeof(gitledger_version_buffer)) == 0U)
        {
            return NULL;
        }

    return gitledger_version_buffer;
}
