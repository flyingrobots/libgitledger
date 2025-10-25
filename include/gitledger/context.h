#ifndef GITLEDGER_CONTEXT_H
#define GITLEDGER_CONTEXT_H

#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef struct gitledger_context gitledger_context_t;

typedef void* (*gitledger_alloc_fn)(void* userdata, size_t size);
typedef void (*gitledger_free_fn)(void* userdata, void* ptr);

typedef struct gitledger_allocator
{
    gitledger_alloc_fn alloc;
    gitledger_free_fn  free;
    void*              userdata;
} gitledger_allocator_t;

gitledger_context_t* gitledger_context_create(const gitledger_allocator_t* allocator);
void                 gitledger_context_retain(gitledger_context_t* ctx);
void                 gitledger_context_release(gitledger_context_t* ctx);

const gitledger_allocator_t* gitledger_context_allocator(const gitledger_context_t* ctx);
void*                        gitledger_context_alloc(gitledger_context_t* ctx, size_t size);
void                         gitledger_context_free(gitledger_context_t* ctx, void* ptr);

#ifdef __cplusplus
}
#endif

#endif /* GITLEDGER_CONTEXT_H */
