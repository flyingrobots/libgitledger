#ifndef GITLEDGER_LIBGITLEDGER_VERSION_H
#define GITLEDGER_LIBGITLEDGER_VERSION_H

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
    const char*                  gitledger_semantic_version_string(void);

#ifdef __cplusplus
}
#endif

#endif /* GITLEDGER_LIBGITLEDGER_VERSION_H */
