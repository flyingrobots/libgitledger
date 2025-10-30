#include "gitledger/version.h"

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

static size_t decimal_length(uint32_t value)
{
    size_t len = 1U;
    while (value >= (uint32_t) GL_VERSION_DECIMAL_BASE)
        {
            value /= (uint32_t) GL_VERSION_DECIMAL_BASE;
            ++len;
        }
    return len;
}

size_t gitledger_semantic_version_snprintf(char* buf, size_t n)
{
    /* Compute required length up-front to honor snprintf semantics. */
    const size_t major_len = decimal_length(GITLEDGER_VERSION_VALUE.major);
    const size_t minor_len = decimal_length(GITLEDGER_VERSION_VALUE.minor);
    const size_t patch_len = decimal_length(GITLEDGER_VERSION_VALUE.patch);
    const size_t required  = major_len + 1U + minor_len + 1U + patch_len;

    if (n == 0U)
        {
            /* No write; return the number of chars that would have been written. */
            return required;
        }

    if (buf == NULL)
        {
            return required; /* mirror snprintf: behave as if only returning length */
        }

    /* Render into a scratch buffer guaranteed to be large enough, then copy. */
    char   tmp[GL_VERSION_BUFFER_SIZE];
    char*  cursor    = tmp;
    size_t remaining = sizeof tmp;

    (void) write_decimal(GITLEDGER_VERSION_VALUE.major, &cursor, &remaining);
    *cursor++ = '.';
    --remaining;
    (void) write_decimal(GITLEDGER_VERSION_VALUE.minor, &cursor, &remaining);
    *cursor++ = '.';
    --remaining;
    (void) write_decimal(GITLEDGER_VERSION_VALUE.patch, &cursor, &remaining);
    *cursor = '\0';

    /* Copy up to n-1 bytes and NUL-terminate. */
    const size_t to_copy = (required < (n - 1U)) ? required : (n - 1U);
    if (to_copy > 0U)
        {
            for (size_t i = 0; i < to_copy; ++i)
                {
                    buf[i] = tmp[i];
                }
        }
    buf[to_copy] = '\0';
    return required;
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
