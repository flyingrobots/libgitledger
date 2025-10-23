#ifndef GITLEDGER_GITLEDGER_H
#define GITLEDGER_GITLEDGER_H

#ifdef __cplusplus
extern "C" {
#endif

/**
 * Return the semantic version of the libgitledger library encoded as
 * major * 10000 + minor * 100 + patch. Placeholder until real API lands.
 */
int gitledger_version(void);

#ifdef __cplusplus
}
#endif

#endif /* GITLEDGER_GITLEDGER_H */
