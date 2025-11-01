#include "gitledger/error.h"
#include "gitledger/context.h"

#include <limits.h>
#include <stdarg.h>
#include <stdatomic.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "../internal/context_internal.h"

#define GITLEDGER_JSON_STATIC_STACK_DEPTH 16U
#define GITLEDGER_JSON_ESCAPE_BUFFER_SIZE 7U
#define GITLEDGER_JSON_ASCII_MIN_PRINTABLE 0x20U
#define GITLEDGER_JSON_LINE_BUFFER_SIZE 32U

typedef struct
{
    char*  data;
    size_t capacity;
    size_t length;
    size_t required;
    bool   overflow;
} gl_buf_t;

typedef struct error_json_frame
{
    const gitledger_error_t* err;
    int                      state;
} error_json_frame_t;

static int gl_safe_vsnprintf(char* buffer, size_t size, const char* fmt, va_list args)
{
    return vsnprintf(buffer, size, fmt, args);
}

static int gl_safe_snprintf(char* buffer, size_t size, const char* fmt, ...)
{
    va_list args;
    va_start(args, fmt);
    int written = gl_safe_vsnprintf(buffer, size, fmt, args);
    va_end(args);
    return written;
}

static void gl_safe_memset(void* dst, int value, size_t size)
{
    memset(dst, value, size);
}

static void gl_safe_memcpy(void* dst, const void* src, size_t size)
{
    memcpy(dst, src, size);
}

static void gl_buf_init(gl_buf_t* buf, char* data, size_t capacity)
{
    buf->data     = data;
    buf->capacity = (data && capacity) ? capacity : 0U;
    buf->length   = 0U;
    buf->required = 0U;
    buf->overflow = false;
    if (buf->capacity > 0U)
        {
            buf->data[0] = '\0';
        }
}

static void gl_buf_append(gl_buf_t* buf, const char* data, size_t len)
{
    if (len == 0U)
        {
            return;
        }

    if (buf->required <= SIZE_MAX - len)
        {
            buf->required += len;
        }
    else
        {
            buf->required = SIZE_MAX;
            buf->overflow = true;
        }

    if (buf->overflow || buf->capacity == 0U)
        {
            return;
        }

    size_t available = (buf->capacity > buf->length + 1U) ? (buf->capacity - buf->length - 1U) : 0U;
    if (available < len)
        {
            if (available > 0U)
                {
                    gl_safe_memcpy(buf->data + buf->length, data, available);
                    buf->length += available;
                }
            buf->overflow = true;
            return;
        }

    gl_safe_memcpy(buf->data + buf->length, data, len);
    buf->length += len;
}

static void gl_buf_putc(gl_buf_t* buf, char character)
{
    gl_buf_append(buf, &character, 1U);
}

static void gl_buf_append_literal(gl_buf_t* buf, const char* literal)
{
    gl_buf_append(buf, literal, strlen(literal));
}

static void gl_buf_finalize(gl_buf_t* buf)
{
    if (buf->capacity == 0U || !buf->data)
        {
            return;
        }
    size_t index     = (buf->length < buf->capacity) ? buf->length : buf->capacity - 1U;
    buf->data[index] = '\0';
}

struct gitledger_error
{
    gitledger_context_t* ctx;
    /* Context generation snapshot for cache invalidation; atomic under C11. */
#if __STDC_VERSION__ >= 201112L
    _Atomic(uint32_t) ctx_generation;
#else
    uint32_t ctx_generation;
#endif
    atomic_uint refcount;
    gitledger_allocator_t allocator; /* snapshot of allocator for safe frees */
    gitledger_domain_t domain;
    gitledger_code_t code;
    gitledger_error_flags_t flags;
    char* message;
#if __STDC_VERSION__ >= 201112L
    _Atomic(void*) json_cache; /* published via CAS; freed via atomic exchange */
#else
    void* json_cache; /* non-atomic fallback under C99 */
#endif
    gitledger_error_t* cause;
    const char* file;
    const char* func;
    int line;
};

static gitledger_error_flags_t default_flags(gitledger_domain_t domain, gitledger_code_t code)
{
    switch (domain)
        {
        case GL_DOMAIN_IO:
            return GL_ERRFLAG_RETRYABLE;
        case GL_DOMAIN_POLICY:
        case GL_DOMAIN_TRUST:
            return GL_ERRFLAG_PERMANENT;
        default:
            break;
        }

    switch (code)
        {
        case GL_CODE_OOM:
        case GL_CODE_IO_ERROR:
            return GL_ERRFLAG_RETRYABLE;
        case GL_CODE_POLICY_VIOLATION:
        case GL_CODE_TRUST_VIOLATION:
        case GL_CODE_INVALID_ARGUMENT:
            return GL_ERRFLAG_PERMANENT;
        default:
            break;
        }
    return GL_ERRFLAG_NONE;
}

static const char* domain_to_string(gitledger_domain_t domain)
{
    switch (domain)
        {
        case GL_DOMAIN_OK:
            return "OK";
        case GL_DOMAIN_GENERIC:
            return "GENERIC";
        case GL_DOMAIN_ALLOCATOR:
            return "ALLOCATOR";
        case GL_DOMAIN_GIT:
            return "GIT";
        case GL_DOMAIN_POLICY:
            return "POLICY";
        case GL_DOMAIN_TRUST:
            return "TRUST";
        case GL_DOMAIN_IO:
            return "IO";
        case GL_DOMAIN_CONFIG:
            return "CONFIG";
        }
    return "UNKNOWN";
}

static const char* code_to_string(gitledger_code_t code)
{
    switch (code)
        {
        case GL_CODE_OK:
            return "OK";
        case GL_CODE_UNKNOWN:
            return "UNKNOWN";
        case GL_CODE_OOM:
            return "OUT_OF_MEMORY";
        case GL_CODE_INVALID_ARGUMENT:
            return "INVALID_ARGUMENT";
        case GL_CODE_NOT_FOUND:
            return "NOT_FOUND";
        case GL_CODE_CONFLICT:
            return "CONFLICT";
        case GL_CODE_PERMISSION_DENIED:
            return "PERMISSION_DENIED";
        case GL_CODE_POLICY_VIOLATION:
            return "POLICY_VIOLATION";
        case GL_CODE_TRUST_VIOLATION:
            return "TRUST_VIOLATION";
        case GL_CODE_IO_ERROR:
            return "IO_ERROR";
        case GL_CODE_DEPENDENCY_MISSING:
            return "DEPENDENCY_MISSING";
        }
    return "UNKNOWN";
}

/* Escape per RFC 8259: ensure control chars (<0x20), backslash and quotes are encoded.
   Use unsigned char iteration to avoid signed-char UB on non-ASCII platforms.
   A small on-stack scratch is used for short sequences (e.g., \uXXXX). */
static void gl_json_escape(gl_buf_t* buf, const char* text)
{
    if (!text) /* Early return avoids dereferencing NULL and keeps builder intact. */
        {
            return;
        }
    for (const unsigned char* cursor = (const unsigned char*) text; *cursor; ++cursor)
        {
            /* scratch capacity covers "\\u%04x" plus NUL. */
            char scratch[GITLEDGER_JSON_ESCAPE_BUFFER_SIZE] = {0};
            switch (*cursor)
                {
                case '\\':
                    gl_buf_append(buf, "\\\\", 2U);
                    break;
                case '\"':
                    gl_buf_append(buf, "\\\"", 2U);
                    break;
                case '\b':
                    gl_buf_append(buf, "\\b", 2U);
                    break;
                case '\f':
                    gl_buf_append(buf, "\\f", 2U);
                    break;
                case '\n':
                    gl_buf_append(buf, "\\n", 2U);
                    break;
                case '\r':
                    gl_buf_append(buf, "\\r", 2U);
                    break;
                case '\t':
                    gl_buf_append(buf, "\\t", 2U);
                    break;
                default:
                    /* JSON forbids control chars < 0x20: emit \uXXXX to remain portable. */
                    if (*cursor < GITLEDGER_JSON_ASCII_MIN_PRINTABLE)
                        {
                            /* snprintf ensures bounds; only append when it produced output. */
                            int written =
                                gl_safe_snprintf(scratch, sizeof scratch, "\\u%04x", *cursor);
                            if (written > 0)
                                {
                                    gl_buf_append(buf, scratch, (size_t) written);
                                }
                        }
                    else
                        {
                            /* Fast path for printable single-byte ASCII. */
                            scratch[0] = (char) *cursor;
                            gl_buf_append(buf, scratch, 1U);
                        }
                    break;
                }
        }
}

static char* duplicate_format(gitledger_context_t* ctx, const char* fmt, va_list args)
{
    if (!fmt || fmt[0] == '\0')
        {
            char* empty = (char*) gitledger_context_alloc(ctx, 1U);
            if (empty)
                {
                    empty[0] = '\0';
                }
            return empty;
        }
    va_list copy;
    va_copy(copy, args);
    int needed = gl_safe_vsnprintf(NULL, 0, fmt, copy);
    va_end(copy);

    if (needed < 0)
        {
            return NULL;
        }

    size_t size = (size_t) needed + 1U;
    char*  buf  = (char*) gitledger_context_alloc(ctx, size);
    if (!buf)
        {
            return NULL;
        }
    gl_safe_vsnprintf(buf, size, fmt, args);
    return buf;
}

static gitledger_error_t* allocate_error(gitledger_context_t* ctx)
{
    gitledger_error_t* err = (gitledger_error_t*) gitledger_context_alloc(ctx, sizeof(*err));
    if (!err)
        {
            return NULL;
        }
    gl_safe_memset(err, 0, sizeof(*err));
    err->ctx = ctx;
    {
        uint32_t snap = gitledger_context_generation_snapshot_internal(ctx);
#if __STDC_VERSION__ >= 201112L
        atomic_store_explicit(&err->ctx_generation, snap, memory_order_release);
#else
        err->ctx_generation = snap;
#endif
    }
    atomic_init(&err->refcount, 1U);
    const gitledger_allocator_t* pal = gitledger_context_allocator(ctx);
    if (pal)
        {
            err->allocator = *pal; /* snapshot allocator for post-context teardown safety */
        }
    return err;
}

static void free_error(gitledger_error_t* err)
{
    gitledger_allocator_t allocator_snapshot = err->allocator;
    if (allocator_snapshot.free)
        {
            /* Single-owner free via atomic exchange to avoid double free. */
            void* cache_ptr = NULL;
#if __STDC_VERSION__ >= 201112L
            cache_ptr = atomic_exchange(&err->json_cache, NULL);
#else
            cache_ptr = err->json_cache;
            err->json_cache = NULL;
#endif
            if (cache_ptr)
                {
                    allocator_snapshot.free(allocator_snapshot.userdata, cache_ptr);
                }
            if (err->message)
                {
                    allocator_snapshot.free(allocator_snapshot.userdata, err->message);
                }
        }
    err->ctx = NULL;
#if __STDC_VERSION__ >= 201112L
    atomic_store_explicit(&err->ctx_generation, 0U, memory_order_release);
#else
    err->ctx_generation = 0U;
#endif
    if (allocator_snapshot.free)
        {
            allocator_snapshot.free(allocator_snapshot.userdata, err);
        }
}

/* Internal: called by context teardown to detach an error from its context. */
void gitledger_error_detach_context_internal(gitledger_error_t* err)
{
    if (!err)
        {
            return;
        }
    err->ctx = NULL;
#if __STDC_VERSION__ >= 201112L
    atomic_store_explicit(&err->ctx_generation, 0U, memory_order_release);
#else
    err->ctx_generation = 0U;
#endif
}

static void write_flags_array(gl_buf_t* buf, gitledger_error_flags_t flags)
{
    gl_buf_putc(buf, '[');
    bool first = true;

    if ((flags & GL_ERRFLAG_RETRYABLE) != 0U)
        {
            if (!first)
                {
                    gl_buf_putc(buf, ',');
                }
            gl_buf_append_literal(buf, "\"RETRYABLE\"");
            first = false;
        }
    if ((flags & GL_ERRFLAG_PERMANENT) != 0U)
        {
            if (!first)
                {
                    gl_buf_putc(buf, ',');
                }
            gl_buf_append_literal(buf, "\"PERMANENT\"");
            first = false;
        }
    if ((flags & GL_ERRFLAG_AUTH) != 0U)
        {
            if (!first)
                {
                    gl_buf_putc(buf, ',');
                }
            gl_buf_append_literal(buf, "\"AUTH\"");
        }
    gl_buf_putc(buf, ']');
}

static void json_write_error_fields(gl_buf_t* buf, const gitledger_error_t* err)
{
    gl_buf_append_literal(buf, "\"domain\":\"");
    gl_buf_append_literal(buf, domain_to_string(err->domain));
    gl_buf_putc(buf, '"');

    gl_buf_append_literal(buf, ",\"code\":\"");
    gl_buf_append_literal(buf, code_to_string(err->code));
    gl_buf_putc(buf, '"');

    gl_buf_append_literal(buf, ",\"flags\":");
    write_flags_array(buf, err->flags);

    gl_buf_append_literal(buf, ",\"message\":\"");
    if (err->message)
        {
            gl_json_escape(buf, err->message);
        }
    gl_buf_putc(buf, '"');

    if (err->file)
        {
            gl_buf_append_literal(buf, ",\"file\":\"");
            gl_json_escape(buf, err->file);
            gl_buf_putc(buf, '"');

            gl_buf_append_literal(buf, ",\"line\":");
            char number[GITLEDGER_JSON_LINE_BUFFER_SIZE];
            int  written = gl_safe_snprintf(number, sizeof number, "%d", err->line);
            if (written > 0)
                {
                    gl_buf_append(buf, number, (size_t) written);
                }
        }

    if (err->func)
        {
            gl_buf_append_literal(buf, ",\"func\":\"");
            gl_json_escape(buf, err->func);
            gl_buf_putc(buf, '"');
        }
}

static bool json_push_cause_frame(error_json_frame_t* stack, size_t capacity, size_t* stack_size,
                                  const gitledger_error_t* cause)
{
    if (!cause || *stack_size >= capacity)
        {
            return false;
        }
    stack[*stack_size].err   = cause;
    stack[*stack_size].state = 0;
    (*stack_size)++;
    return true;
}

static bool json_emit_frame(gl_buf_t* buf, error_json_frame_t* stack, size_t* stack_size,
                            size_t capacity, bool* truncated)
{
    error_json_frame_t*      frame   = &stack[*stack_size - 1U];
    const gitledger_error_t* current = frame->err;
    if (frame->state == 0)
        {
            gl_buf_putc(buf, '{');
            json_write_error_fields(buf, current);
            frame->state = 1;
            if (json_push_cause_frame(stack, capacity, stack_size, current->cause))
                {
                    gl_buf_append_literal(buf, ",\"cause\":");
                    return true;
                }
            if (current->cause)
                {
                    *truncated = true;
                    gl_buf_append_literal(buf, ",\"cause\":{\"truncated\":true}");
                }
        }

    gl_buf_putc(buf, '}');
    (*stack_size)--;
    return false;
}

static size_t json_measure_depth(const gitledger_error_t* err, bool* truncated)
{
    size_t                   depth = 0U;
    const gitledger_error_t* iter  = err;
    while (iter && depth < GITLEDGER_ERROR_MAX_DEPTH)
        {
            ++depth;
            iter = iter->cause;
        }
    if (iter && truncated)
        {
            *truncated = true;
        }
    return depth;
}

static error_json_frame_t* json_acquire_stack(size_t depth, error_json_frame_t* storage,
                                              size_t* capacity, int* use_heap_flag, bool* truncated)
{
    error_json_frame_t* stack = storage;
    *capacity                 = GITLEDGER_JSON_STATIC_STACK_DEPTH;
    *use_heap_flag            = 0;
    if (depth > *capacity)
        {
            stack = (error_json_frame_t*) malloc(depth * sizeof(*stack));
            if (stack)
                {
                    *capacity      = depth;
                    *use_heap_flag = 1;
                }
            else
                {
                    stack     = storage;
                    *capacity = GITLEDGER_JSON_STATIC_STACK_DEPTH;
                    if (truncated)
                        {
                            *truncated = true;
                        }
                }
        }
    return stack;
}

static void json_write_error(gl_buf_t* buf, const gitledger_error_t* err, bool* truncated)
{
    bool   truncated_flag = false;
    size_t measured_depth = json_measure_depth(err, &truncated_flag);

    error_json_frame_t  stack_static[GITLEDGER_JSON_STATIC_STACK_DEPTH];
    size_t              capacity      = 0U;
    int                 use_heap_flag = 0;
    error_json_frame_t* stack         = json_acquire_stack(measured_depth, stack_static, &capacity,
                                                           &use_heap_flag, &truncated_flag);

    const bool use_heap = use_heap_flag != 0;

    size_t stack_size = 0U;
    if (err)
        {
            stack[0].err   = err;
            stack[0].state = 0;
            stack_size     = 1U;
        }

    while (stack_size > 0U)
        {
            if (json_emit_frame(buf, stack, &stack_size, capacity, &truncated_flag))
                {
                    continue;
                }
        }

    if (use_heap)
        {
            free(stack);
        }

    if (truncated)
        {
            *truncated = truncated_flag;
        }
}

gitledger_domain_t gitledger_error_domain(const gitledger_error_t* err)
{
    return err ? err->domain : GL_DOMAIN_GENERIC;
}

gitledger_code_t gitledger_error_code(const gitledger_error_t* err)
{
    return err ? err->code : GL_CODE_UNKNOWN;
}

gitledger_error_flags_t gitledger_error_flags(const gitledger_error_t* err)
{
    return err ? err->flags : GL_ERRFLAG_NONE;
}

const char* gitledger_error_message(const gitledger_error_t* err)
{
    return (err && err->message) ? err->message : "";
}

const gitledger_error_t* gitledger_error_cause(const gitledger_error_t* err)
{
    return err ? err->cause : NULL;
}

const char* gitledger_error_file(const gitledger_error_t* err)
{
    return err ? err->file : NULL;
}

int gitledger_error_line(const gitledger_error_t* err)
{
    return err ? err->line : 0;
}

const char* gitledger_error_func(const gitledger_error_t* err)
{
    return err ? err->func : NULL;
}

const char* gitledger_domain_name(gitledger_domain_t domain)
{
    return domain_to_string(domain);
}

const char* gitledger_code_name(gitledger_code_t code)
{
    return code_to_string(code);
}

size_t gitledger_error_flags_format(gitledger_error_flags_t flags, char* buf, size_t size)
{
    const char* names[3];
    size_t      count = 0U;
    if ((flags & GL_ERRFLAG_RETRYABLE) != 0U)
        {
            names[count++] = "RETRYABLE";
        }
    if ((flags & GL_ERRFLAG_PERMANENT) != 0U)
        {
            names[count++] = "PERMANENT";
        }
    if ((flags & GL_ERRFLAG_AUTH) != 0U)
        {
            names[count++] = "AUTH";
        }

    size_t required = 0U;
    for (size_t i = 0; i < count; ++i)
        {
            size_t part = strlen(names[i]);
            if (required > 0U)
                {
                    ++required; /* separator */
                }
            required += part;
        }

    if (buf && size > 0U)
        {
            size_t written = 0U;
            for (size_t i = 0; i < count; ++i)
                {
                    if (written > 0U && written < size - 1U)
                        {
                            buf[written++] = '|';
                        }
                    const char* name = names[i];
                    while (*name && written < size - 1U)
                        {
                            buf[written++] = *name++;
                        }
                }
            buf[(written < size) ? written : size - 1U] = '\0';
        }
    return required;
}

void gitledger_error_retain(gitledger_error_t* err)
{
    if (err)
        {
            atomic_fetch_add_explicit(&err->refcount, 1U, memory_order_relaxed);
        }
}

void gitledger_error_release(gitledger_error_t* err)
{
    gitledger_error_t* current = err;
    while (current)
        {
            if (atomic_fetch_sub_explicit(&current->refcount, 1U, memory_order_acq_rel) == 1U)
                {
                    gitledger_context_t* ctx  = current->ctx;
                    gitledger_error_t*   next = current->cause;
                    if (ctx)
                        {
                            gitledger_context_untrack_error_internal(ctx, current);
                        }
                    current->cause = NULL;
                    free_error(current);
                    current = next;
                    continue;
                }
            break;
        }
}

static gitledger_error_t* create_error_internal(gitledger_context_t* ctx, gitledger_domain_t domain,
                                                gitledger_code_t            code,
                                                const gitledger_error_t*    cause,
                                                gitledger_source_location_t location,
                                                const char* fmt, va_list args)
{
    if (!gitledger_context_is_valid_internal(ctx))
        {
            return NULL;
        }

    gitledger_error_t* err = allocate_error(ctx);
    if (!err)
        {
            return NULL;
        }

    err->domain = domain;
    err->code   = code;
    err->flags  = default_flags(domain, code);
    err->file   = location.file;
    err->line   = location.line;
    err->func   = location.func;

    va_list copy;
    va_copy(copy, args);
    err->message = duplicate_format(ctx, fmt ? fmt : "", copy);
    va_end(copy);
    if (!err->message)
        {
            gitledger_context_free(ctx, err);
            return NULL;
        }

    if (cause)
        {
            gitledger_error_retain((gitledger_error_t*) cause);
            err->cause = (gitledger_error_t*) cause;
        }

    /* If the context fails to register this error (e.g., allocator OOM for the
       registry node), returning an error still pointing at the context is unsafe:
       the context might be destroyed later, leaving err->ctx dangling and any
       subsequent release/json walk would dereference freed memory. Detach the
       association if tracking fails; callers still own the error via its
       snapshot allocator and can safely release it. */
    if (!gitledger_context_track_error_internal(ctx, err))
        {
            gitledger_error_detach_context_internal(err);
        }
    return err;
}

gitledger_error_t* gitledger_error_create_ctx_loc_v(gitledger_context_t*        ctx,
                                                    gitledger_domain_t          domain,
                                                    gitledger_code_t            code,
                                                    gitledger_source_location_t location,
                                                    const char* fmt, va_list args)
{
    return create_error_internal(ctx, domain, code, NULL, location, fmt, args);
}

gitledger_error_t* gitledger_error_create_ctx_loc(gitledger_context_t* ctx,
                                                  gitledger_domain_t domain, gitledger_code_t code,
                                                  gitledger_source_location_t location,
                                                  const char*                 fmt, ...)
{
    va_list args;
    va_start(args, fmt);
    gitledger_error_t* err =
        gitledger_error_create_ctx_loc_v(ctx, domain, code, location, fmt, args);
    va_end(args);
    return err;
}

gitledger_error_t* gitledger_error_with_cause_ctx_loc_v(gitledger_context_t*        ctx,
                                                        gitledger_domain_t          domain,
                                                        gitledger_code_t            code,
                                                        const gitledger_error_t*    cause,
                                                        gitledger_source_location_t location,
                                                        const char* fmt, va_list args)
{
    return create_error_internal(ctx, domain, code, cause, location, fmt, args);
}

gitledger_error_t*
gitledger_error_with_cause_ctx_loc(gitledger_context_t* ctx, gitledger_domain_t domain,
                                   gitledger_code_t code, const gitledger_error_t* cause,
                                   gitledger_source_location_t location, const char* fmt, ...)
{
    va_list args;
    va_start(args, fmt);
    gitledger_error_t* err =
        gitledger_error_with_cause_ctx_loc_v(ctx, domain, code, cause, location, fmt, args);
    va_end(args);
    return err;
}

void gitledger_error_walk(const gitledger_error_t* top, gitledger_error_visitor_t visitor,
                          void* userdata)
{
    const gitledger_error_t* current = top;
    size_t                   depth   = 0U;
    while (current && depth < GITLEDGER_ERROR_MAX_DEPTH)
        {
            if (!visitor(current, userdata))
                {
                    return;
                }
            current = current->cause;
            ++depth;
        }
}

size_t gitledger_error_render_json(const gitledger_error_t* err, char* buf, size_t size)
{
    if (!err)
        {
            if (buf && size > 0U)
                {
                    buf[0] = '\0';
                }
            return 1U;
        }

    gl_buf_t builder;
    gl_buf_init(&builder, buf, size);

    bool truncated = false;
    json_write_error(&builder, err, &truncated);
    gl_buf_finalize(&builder);

    (void) truncated;
    if (builder.required == SIZE_MAX)
        {
            return SIZE_MAX;
        }
    return builder.required + 1U;
}

static void ensure_json_cache_current(gitledger_error_t* err)
{
    if (!err->ctx)
        {
            return;
        }

    uint32_t snapshot = gitledger_context_generation_snapshot_internal(err->ctx);
    {
#if __STDC_VERSION__ >= 201112L
        uint32_t observed = atomic_load_explicit(&err->ctx_generation, memory_order_acquire);
#else
        uint32_t observed = err->ctx_generation;
#endif
        if (observed != snapshot)
        {
            /* Invalidate cached JSON atomically so only one thread frees it. */
            void* cache_ptr = NULL;
#if __STDC_VERSION__ >= 201112L
            cache_ptr = atomic_exchange(&err->json_cache, NULL);
#else
            cache_ptr       = err->json_cache;
            err->json_cache = NULL;
#endif
            if (cache_ptr)
                {
                    gitledger_context_free(err->ctx, cache_ptr);
                }
            /* Publish new generation snapshot. */
#if __STDC_VERSION__ >= 201112L
            atomic_store_explicit(&err->ctx_generation, snapshot, memory_order_release);
#else
            err->ctx_generation = snapshot;
#endif
        }
    }
}

/*
 * JSON cache ownership & lifetime
 * -------------------------------
 * - Ownership: the returned pointer is owned by the error object.
 * - Volatility: the pointer may be invalidated when the context generation
 *   changes or when another thread publishes a newer cache.
 * - Stability: callers must copy via gitledger_error_json_copy() if they need
 *   a stable, long‑lived snapshot.
 */
const char* gitledger_error_json(gitledger_error_t* err)
{
    if (!err)
        {
            return "{}";
        }

    ensure_json_cache_current(err);

    void* cached_ptr = NULL;
#if __STDC_VERSION__ >= 201112L
    cached_ptr = atomic_load(&err->json_cache);
#else
    cached_ptr = err->json_cache;
#endif
    if (cached_ptr)
        {
            return (const char*) cached_ptr;
        }

    if (!err->ctx)
        {
            return "{}";
        }

    size_t required = gitledger_error_render_json(err, NULL, 0U);
    char*  buffer   = (char*) gitledger_context_alloc(err->ctx, required);
    if (!buffer)
        {
            return "{}";
        }
    gitledger_error_render_json(err, buffer, required);
#if __STDC_VERSION__ >= 201112L
    void* expected = NULL;
    if (atomic_compare_exchange_strong(&err->json_cache, &expected, buffer))
        {
            return buffer;
        }
    /* Another thread published a cache; keep theirs and free ours. */
    gitledger_context_free(err->ctx, buffer);
    return (const char*) expected;
#else
    if (err->json_cache == NULL)
        {
            err->json_cache = buffer;
            return buffer;
        }
    gitledger_context_free(err->ctx, buffer);
    return (const char*) err->json_cache;
#endif
}

char* gitledger_error_json_copy(gitledger_context_t* ctx, gitledger_error_t* err)
{
    if (!ctx || !gitledger_context_is_valid_internal(ctx))
        {
            return NULL;
        }
    const char* json = gitledger_error_json(err);
    size_t      len  = strlen(json) + 1U;
    char*       copy = (char*) gitledger_context_alloc(ctx, len);
    if (!copy)
        {
            return NULL;
        }
    gl_safe_memcpy(copy, json, len);
    return copy;
}

char* gitledger_error_message_copy(gitledger_context_t* ctx, const gitledger_error_t* err)
{
    if (!ctx || !err || !gitledger_context_is_valid_internal(ctx))
        {
            return NULL;
        }
    const char* message = gitledger_error_message(err);
    size_t      len     = strlen(message) + 1U;
    char*       copy    = (char*) gitledger_context_alloc(ctx, len);
    if (!copy)
        {
            return NULL;
        }
    gl_safe_memcpy(copy, message, len);
    return copy;
}
