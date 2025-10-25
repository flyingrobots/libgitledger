#include "gitledger/context.h"

#include <stdatomic.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#ifdef _POSIX_VERSION
#include <sched.h>
#endif
#if defined(_MSC_VER) && (defined(_M_IX86) || defined(_M_X64))
#include <intrin.h>
#endif

#include "gitledger/error.h"
#include "internal/context_internal.h"

#define GITLEDGER_CONTEXT_MAGIC 0xC0FFEE01u
#define GITLEDGER_SPIN_YIELD_THRESHOLD 64U
#define GITLEDGER_CONTEXT_DIAG_BUF 160U

typedef struct gitledger_error_node
{
    gitledger_error_t*           error;
    struct gitledger_error_node* next;
} gitledger_error_node_t;

struct gitledger_context
{
    uint32_t                magic;
    atomic_uint             generation;
    atomic_uint             refcount;
    gitledger_allocator_t   allocator;
    gitledger_error_node_t* errors;
    atomic_flag             lock;
};

static inline void context_cpu_relax(void)
{
#if defined(_MSC_VER) && (defined(_M_IX86) || defined(_M_X64))
    _mm_pause();
#elif defined(__i386__) || defined(__x86_64__)
    __builtin_ia32_pause();
#elif defined(__aarch64__)
    __asm__ __volatile__("yield");
#endif
}

static inline bool context_is_valid(const gitledger_context_t* ctx)
{
    return ctx && ctx->magic == GITLEDGER_CONTEXT_MAGIC;
}

static void* default_alloc(void* userdata, size_t size)
{
    (void) userdata;
    return malloc(size);
}

static void default_free(void* userdata, void* ptr)
{
    (void) userdata;
    free(ptr);
}

static void context_lock(gitledger_context_t* ctx)
{
    unsigned spin_count = 0;
    while (atomic_flag_test_and_set_explicit(&ctx->lock, memory_order_acquire))
        {
            context_cpu_relax();
            if (++spin_count >= GITLEDGER_SPIN_YIELD_THRESHOLD)
                {
#ifdef _POSIX_VERSION
                    sched_yield();
#endif
                    spin_count = 0;
                }
        }
}

static void context_unlock(gitledger_context_t* ctx)
{
    atomic_flag_clear_explicit(&ctx->lock, memory_order_release);
}

/* Call under lock: counts current error nodes while the caller holds the spinlock. */
static size_t context_count_errors_locked(const gitledger_context_t* ctx)
{
    size_t                        count = 0U;
    const gitledger_error_node_t* node  = ctx->errors;
    while (node)
        {
            ++count;
            node = node->next;
        }
    return count;
}

static size_t context_detach_and_free_error_nodes(gitledger_context_t* ctx)
{
    gitledger_error_node_t* node = ctx->errors;
    ctx->errors                  = NULL;
    size_t live_count            = 0U;
    while (node)
        {
            gitledger_error_node_t* next = node->next;
            if (node->error)
                {
                    gitledger_error_detach_context_internal(node->error);
                    ++live_count;
                }
            ctx->allocator.free(ctx->allocator.userdata, node);
            node = next;
        }
    return live_count;
}

static void context_debug_log_live_errors(size_t live_count)
{
    if (live_count == 0U)
        {
            return;
        }
    char   buf[GITLEDGER_CONTEXT_DIAG_BUF];
    size_t length        = 0U;
    int    written_chars = snprintf(
        buf, sizeof buf,
        "gitledger_context_destroy: %zu live error(s) at context teardown (leaked)\n",
        live_count);
    if (written_chars < 0)
        {
            const char* fallback =
                "gitledger_context_destroy: live error(s) at context teardown (leaked)\n";
            length = strlen(fallback);
            if (length >= sizeof buf)
                {
                    length = sizeof buf - 1U;
                }
            memcpy(buf, fallback, length);
            buf[length] = '\0';
        }
    else
        {
            length = (size_t) written_chars;
            if (length >= sizeof buf)
                {
                    length      = sizeof buf - 1U;
                    buf[length] = '\0';
                }
        }
    (void) fwrite(buf, 1U, length, stderr);
}

static void context_register_error(gitledger_context_t* ctx, gitledger_error_t* err)
{
    if (!context_is_valid(ctx))
        {
            return;
        }

    gitledger_error_node_t* node =
        (gitledger_error_node_t*) gitledger_context_alloc(ctx, sizeof(gitledger_error_node_t));
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
    if (!context_is_valid(ctx))
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
                    *cursor                        = doomed->next;
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
    gitledger_allocator_t alloc = {default_alloc, default_free, NULL};
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

    gitledger_context_t* ctx =
        (gitledger_context_t*) alloc.alloc(alloc.userdata, sizeof(gitledger_context_t));
    if (!ctx)
        {
            return NULL;
        }
    ctx->magic = GITLEDGER_CONTEXT_MAGIC;
    atomic_init(&ctx->generation, 1U);
    atomic_init(&ctx->refcount, 1U);
    ctx->allocator = alloc;
    ctx->errors    = NULL;
    atomic_flag_clear(&ctx->lock);
    return ctx;
}

void gitledger_context_retain(gitledger_context_t* ctx)
{
    if (context_is_valid(ctx))
        {
            atomic_fetch_add_explicit(&ctx->refcount, 1U, memory_order_relaxed);
        }
}

static void context_destroy(gitledger_context_t* ctx)
{
    /* Enforce lifecycle: destroying with live errors is a contract breach. */
    size_t live       = 0U;
    bool   has_errors = false;
    context_lock(ctx);
    has_errors = (ctx->errors != NULL);
    if (has_errors)
        {
            live = context_count_errors_locked(ctx);
        }
    context_unlock(ctx);
#ifndef NDEBUG
    if (has_errors)
        {
            context_debug_log_live_errors(live);
            abort();
        }
#else
    if (has_errors)
        {
            context_debug_log_live_errors(live);
            /* Keep the context alive: bump refcount back and refuse teardown. */
            (void) atomic_fetch_add_explicit(&ctx->refcount, 1U, memory_order_relaxed);
            return;
        }
#endif

    /* Context is not the owner of errors; detach registry only. */
    gitledger_context_bump_generation_internal(ctx);
    size_t live_count = context_detach_and_free_error_nodes(ctx);
    context_debug_log_live_errors(live_count);

    ctx->magic = 0;
    ctx->allocator.free(ctx->allocator.userdata, ctx);
}

int gitledger_context_try_release(gitledger_context_t* ctx)
{
    if (!context_is_valid(ctx))
        {
            return -1;
        }
    if (atomic_fetch_sub_explicit(&ctx->refcount, 1U, memory_order_acq_rel) == 1U)
        {
            context_destroy(ctx);
            return 1;
        }
    return 0;
}

void gitledger_context_release(gitledger_context_t* ctx)
{
    (void) gitledger_context_try_release(ctx);
}

const gitledger_allocator_t* gitledger_context_allocator(const gitledger_context_t* ctx)
{
    return context_is_valid(ctx) ? &ctx->allocator : NULL;
}

void* gitledger_context_alloc(gitledger_context_t* ctx, size_t size)
{
    if (!context_is_valid(ctx) || !ctx->allocator.alloc)
        {
            return NULL;
        }
    return ctx->allocator.alloc(ctx->allocator.userdata, size);
}

void gitledger_context_free(gitledger_context_t* ctx, void* ptr)
{
    if (!context_is_valid(ctx) || !ctx->allocator.free || !ptr)
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

int gitledger_context_valid(const gitledger_context_t* ctx)
{
    return context_is_valid(ctx) ? 1 : 0;
}

bool gitledger_context_is_valid_internal(const gitledger_context_t* ctx)
{
    return context_is_valid(ctx);
}

uint32_t gitledger_context_generation_snapshot_internal(const gitledger_context_t* ctx)
{
    if (!context_is_valid(ctx))
        {
            return 0U;
        }
    return (uint32_t) atomic_load_explicit(&ctx->generation, memory_order_acquire);
}

void gitledger_context_bump_generation_internal(gitledger_context_t* ctx)
{
    if (!context_is_valid(ctx))
        {
            return;
        }
    atomic_fetch_add_explicit(&ctx->generation, 1U, memory_order_release);
}
