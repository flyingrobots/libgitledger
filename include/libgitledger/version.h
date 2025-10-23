#ifndef METAGRAPH_LIBGITLEDGER_VERSION_H
#define METAGRAPH_LIBGITLEDGER_VERSION_H

#ifdef __cplusplus
extern "C"
{
#endif

    typedef struct gitledger_semantic_version
    {
        int major;
        int minor;
        int patch;
    } gitledger_semantic_version_t;

    gitledger_semantic_version_t gitledger_semantic_version(void);
    const char*                  gitledger_semantic_version_string(void);

#ifdef __cplusplus
}
#endif

#endif /* METAGRAPH_LIBGITLEDGER_VERSION_H */
