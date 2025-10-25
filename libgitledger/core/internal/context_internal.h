#ifndef GITLEDGER_CONTEXT_INTERNAL_H
#define GITLEDGER_CONTEXT_INTERNAL_H

#include "gitledger/context.h"

#ifdef __cplusplus
extern "C" {
#endif

struct gitledger_error;

void gitledger_context_track_error_internal(gitledger_context_t* ctx, struct gitledger_error* err);
void gitledger_context_untrack_error_internal(gitledger_context_t* ctx, struct gitledger_error* err);

#ifdef __cplusplus
}
#endif

#endif /* GITLEDGER_CONTEXT_INTERNAL_H */
