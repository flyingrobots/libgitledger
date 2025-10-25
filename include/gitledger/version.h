#ifndef GITLEDGER_LIBGITLEDGER_VERSION_H
#define GITLEDGER_LIBGITLEDGER_VERSION_H

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C"
{
#endif

    typedef struct gitledger_semantic_version
    {
        uint32_t major;
        uint32_t minor;
        uint32_t patch;
    } gitledger_semantic_version_t;

    gitledger_semantic_version_t gitledger_semantic_version(void);

    size_t gitledger_semantic_version_snprintf(char* buf, size_t n);

    const char* gitledger_semantic_version_string(void); /* Returns NULL on failure. */

#ifdef __cplusplus
}
#endif

#endif /* GITLEDGER_LIBGITLEDGER_VERSION_H */
