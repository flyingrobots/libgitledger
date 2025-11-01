#ifndef GITLEDGER_CONTEXT_INTERNAL_H
#define GITLEDGER_CONTEXT_INTERNAL_H

#include "gitledger/context.h"

#include <stdbool.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C"
{
#endif

    struct gitledger_error;

    /* Returns true when the error is successfully tracked (registered) in the
       context registry; false when tracking failed (e.g., allocator OOM). */
    bool     gitledger_context_track_error_internal(gitledger_context_t*    ctx,
                                                    struct gitledger_error* err);
    void     gitledger_context_untrack_error_internal(gitledger_context_t*    ctx,
                                                      struct gitledger_error* err);
    bool     gitledger_context_is_valid_internal(const gitledger_context_t* ctx);
    uint32_t gitledger_context_generation_snapshot_internal(const gitledger_context_t* ctx);
    void     gitledger_context_bump_generation_internal(gitledger_context_t* ctx);

    /* Error-side internal utility used by context teardown to sever the
       association without touching refcounts. */
    void gitledger_error_detach_context_internal(struct gitledger_error* err);

#ifdef __cplusplus
}
#endif

#endif /* GITLEDGER_CONTEXT_INTERNAL_H */
