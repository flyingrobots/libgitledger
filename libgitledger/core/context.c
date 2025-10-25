#include "gitledger/context.h"

#include <stdatomic.h>
#include <stdlib.h>
#include <string.h>

#include "gitledger/error.h"

typedef struct gitledger_error_node
{
    gitledger_error_t*          error;
    struct gitledger_error_node* next;
} gitledger_error_node_t;

struct gitledger_context
{
    atomic_uint           refcount;
    gitledger_allocator_t allocator;
    gitledger_error_node_t* errors;
    atomic_flag           lock;
};

static void* default_alloc(void* userdata, size_t size)
{
    (void) userdata;
    return malloc(size);
}

static void default_free(void* userdata, void* ptr) // NOLINT(bugprone-easily-swappable-parameters)
{
    (void) userdata;
    free(ptr);
}

static void context_lock(gitledger_context_t* ctx)
{
    while (atomic_flag_test_and_set_explicit(&ctx->lock, memory_order_acquire))
        {
        }
}

static void context_unlock(gitledger_context_t* ctx)
{
    atomic_flag_clear_explicit(&ctx->lock, memory_order_release);
}

static void context_register_error(gitledger_context_t* ctx, gitledger_error_t* err)
{
    if (!ctx)
        {
            return;
        }

    gitledger_error_node_t* node = (gitledger_error_node_t*) gitledger_context_alloc(ctx, sizeof(gitledger_error_node_t));
    if (!node)
        {
            return;
        }
    node->error = err;

    context_lock(ctx);
    node->next  = ctx->errors;
    ctx->errors = node;
    context_unlock(ctx);
}

static void context_unregister_error(gitledger_context_t* ctx, gitledger_error_t* err)
{
    if (!ctx)
        {
            return;
        }

    context_lock(ctx);
    gitledger_error_node_t** cursor = &ctx->errors;
    while (*cursor)
        {
            if ((*cursor)->error == err)
                {
                    gitledger_error_node_t* doomed = *cursor;
                    *cursor                      = doomed->next;
                    context_unlock(ctx);
                    gitledger_context_free(ctx, doomed);
                    return;
                }
            cursor = &(*cursor)->next;
        }
    context_unlock(ctx);
}

gitledger_context_t* gitledger_context_create(const gitledger_allocator_t* allocator)
{
    gitledger_allocator_t alloc = { default_alloc, default_free, NULL };
    if (allocator)
        {
            alloc = *allocator;
            if (!alloc.alloc)
                {
                    alloc.alloc = default_alloc;
                }
            if (!alloc.free)
                {
                    alloc.free = default_free;
                }
        }

    gitledger_context_t* ctx = (gitledger_context_t*) alloc.alloc(alloc.userdata, sizeof(gitledger_context_t));
    if (!ctx)
        {
            return NULL;
        }
    atomic_init(&ctx->refcount, 1U);
    ctx->allocator = alloc;
    ctx->errors    = NULL;
    atomic_flag_clear(&ctx->lock);
    return ctx;
}

void gitledger_context_retain(gitledger_context_t* ctx)
{
    if (ctx)
        {
            atomic_fetch_add_explicit(&ctx->refcount, 1U, memory_order_relaxed);
        }
}

static void context_destroy(gitledger_context_t* ctx)
{
    gitledger_error_node_t* node = ctx->errors;
    while (node)
        {
            gitledger_error_node_t* next = node->next;
            gitledger_error_release(node->error);
            ctx->allocator.free(ctx->allocator.userdata, node);
            node = next;
        }
    ctx->allocator.free(ctx->allocator.userdata, ctx);
}

void gitledger_context_release(gitledger_context_t* ctx)
{
    if (!ctx)
        {
            return;
        }
    if (atomic_fetch_sub_explicit(&ctx->refcount, 1U, memory_order_acq_rel) == 1U)
        {
            context_destroy(ctx);
        }
}

const gitledger_allocator_t* gitledger_context_allocator(const gitledger_context_t* ctx)
{
    return ctx ? &ctx->allocator : NULL;
}

void* gitledger_context_alloc(gitledger_context_t* ctx, size_t size)
{
    if (!ctx || !ctx->allocator.alloc)
        {
            return NULL;
        }
    return ctx->allocator.alloc(ctx->allocator.userdata, size);
}

void gitledger_context_free(gitledger_context_t* ctx, void* ptr)
{
    if (!ctx || !ctx->allocator.free || !ptr)
        {
            return;
        }
    ctx->allocator.free(ctx->allocator.userdata, ptr);
}

/* Internal hooks used by the error subsystem */
void gitledger_context_track_error_internal(gitledger_context_t* ctx, gitledger_error_t* err)
{
    context_register_error(ctx, err);
}

void gitledger_context_untrack_error_internal(gitledger_context_t* ctx, gitledger_error_t* err)
{
    context_unregister_error(ctx, err);
}
