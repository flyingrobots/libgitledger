#include "gitledger/error.h"
#include "gitledger/context.h"

#include <stdatomic.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "../internal/context_internal.h"

#define GITLEDGER_JSON_APPEND_LITERAL(writer_ptr, literal) \
    writer_append((writer_ptr), (literal), sizeof(literal) - 1U)

static int gl_safe_vsnprintf(char* buffer, size_t size, const char* fmt, va_list args)
{
    /* We rely on vsnprintf with explicit bounds; suppress analyzer false positives. */
    // NOLINTNEXTLINE(clang-analyzer-security.insecureAPI.DeprecatedOrUnsafeBufferHandling)
    return vsnprintf(buffer, size, fmt, args);
}

static int gl_safe_snprintf(char* buffer, size_t size, const char* fmt, ...)
{
    va_list args;
    va_start(args, fmt);
    // NOLINTNEXTLINE(clang-analyzer-security.insecureAPI.DeprecatedOrUnsafeBufferHandling)
    int written = vsnprintf(buffer, size, fmt, args);
    va_end(args);
    return written;
}

static void gl_safe_memset(void* dst, int value, size_t size)
{
    // NOLINTNEXTLINE(clang-analyzer-security.insecureAPI.DeprecatedOrUnsafeBufferHandling)
    memset(dst, value, size);
}

static void gl_safe_memcpy(void* dst, const void* src, size_t size)
{
    // NOLINTNEXTLINE(clang-analyzer-security.insecureAPI.DeprecatedOrUnsafeBufferHandling)
    memcpy(dst, src, size);
}


typedef struct error_json_frame
{
    const gitledger_error_t* err;
    int                      state;
} error_json_frame_t;

enum
{
    GL_JSON_STATIC_STACK_DEPTH  = 16,
    GL_JSON_LINE_BUFFER_SIZE    = 16,
    GL_JSON_ESCAPE_BUFFER_SIZE  = 7,
    GL_JSON_ASCII_MIN_PRINTABLE = 0x20
};

typedef struct
{
    char*  cursor;
    size_t remaining;
    size_t total;
} gl_json_writer_t;

static gl_json_writer_t gl_json_writer_init(char* buffer, size_t size)
{
    gl_json_writer_t writer = {
        .cursor    = (buffer && size) ? buffer : NULL,
        .remaining = (buffer && size) ? size : 0U,
        .total     = 0U
    };
    return writer;
}

struct gitledger_error
{
    gitledger_context_t*    ctx;
    atomic_uint             refcount;
    gitledger_domain_t      domain;
    gitledger_code_t        code;
    gitledger_error_flags_t flags;
    char*                   message;
    char*                   json_cache;
    gitledger_error_t*      cause;
    const char*             file;
    const char*             func;
    int                     line;
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

static char* duplicate_format(gitledger_context_t* ctx, const char* fmt, va_list args)
{
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
    gitledger_error_t* err = (gitledger_error_t*) gitledger_context_alloc(ctx, sizeof(gitledger_error_t));
    if (!err)
        {
            return NULL;
        }
    gl_safe_memset(err, 0, sizeof(*err));
    err->ctx = ctx;
    atomic_init(&err->refcount, 1U);
    return err;
}

static void free_error(gitledger_error_t* err)
{
    gitledger_context_t* ctx = err->ctx;
    if (err->message)
        {
            gitledger_context_free(ctx, err->message);
        }
    if (err->json_cache)
        {
            gitledger_context_free(ctx, err->json_cache);
        }
    gitledger_context_free(ctx, err);
}

static const char* domain_to_string(gitledger_domain_t domain)
{
    switch (domain)
        {
            case GL_DOMAIN_OK: return "OK";
            case GL_DOMAIN_GENERIC: return "GENERIC";
            case GL_DOMAIN_ALLOCATOR: return "ALLOCATOR";
            case GL_DOMAIN_GIT: return "GIT";
            case GL_DOMAIN_POLICY: return "POLICY";
            case GL_DOMAIN_TRUST: return "TRUST";
            case GL_DOMAIN_IO: return "IO";
            case GL_DOMAIN_CONFIG: return "CONFIG";
        }
    return "UNKNOWN";
}

static const char* code_to_string(gitledger_code_t code)
{
    switch (code)
        {
            case GL_CODE_OK: return "OK";
            case GL_CODE_UNKNOWN: return "UNKNOWN";
            case GL_CODE_OOM: return "OUT_OF_MEMORY";
            case GL_CODE_INVALID_ARGUMENT: return "INVALID_ARGUMENT";
            case GL_CODE_NOT_FOUND: return "NOT_FOUND";
            case GL_CODE_CONFLICT: return "CONFLICT";
            case GL_CODE_PERMISSION_DENIED: return "PERMISSION_DENIED";
            case GL_CODE_POLICY_VIOLATION: return "POLICY_VIOLATION";
            case GL_CODE_TRUST_VIOLATION: return "TRUST_VIOLATION";
            case GL_CODE_IO_ERROR: return "IO_ERROR";
            case GL_CODE_DEPENDENCY_MISSING: return "DEPENDENCY_MISSING";
        }
    return "UNKNOWN";
}

static void writer_append(gl_json_writer_t* writer, const char* data, size_t len)
{
    if (writer->remaining > 1U && writer->cursor)
        {
            size_t copy = len;
            if (copy >= writer->remaining)
                {
                    copy = writer->remaining - 1U;
                }
            gl_safe_memcpy(writer->cursor, data, copy);
            writer->cursor += copy;
            writer->remaining -= copy;
        }
    writer->total += len;
}

static void writer_append_char(gl_json_writer_t* writer, char chr)
{
    writer_append(writer, &chr, 1U);
}

static void writer_append_escaped(gl_json_writer_t* writer, const char* text)
{
    for (const unsigned char* byte_ptr = (const unsigned char*) text; *byte_ptr; ++byte_ptr)
        {
            char        scratch[GL_JSON_ESCAPE_BUFFER_SIZE] = {0};
            size_t      length  = 0U;
            switch (*byte_ptr)
                {
                    case '\\': scratch[0] = '\\'; scratch[1] = '\\'; length = 2U; break;
                    case '\"': scratch[0] = '\\'; scratch[1] = '"'; length = 2U; break;
                    case '\b': scratch[0] = '\\'; scratch[1] = 'b'; length = 2U; break;
                    case '\f': scratch[0] = '\\'; scratch[1] = 'f'; length = 2U; break;
                    case '\n': scratch[0] = '\\'; scratch[1] = 'n'; length = 2U; break;
                    case '\r': scratch[0] = '\\'; scratch[1] = 'r'; length = 2U; break;
                    case '\t': scratch[0] = '\\'; scratch[1] = 't'; length = 2U; break;
                    default:
                        if (*byte_ptr < GL_JSON_ASCII_MIN_PRINTABLE)
                            {
                                const int written =
                                    gl_safe_snprintf(scratch, sizeof scratch, "\\u%04x", *byte_ptr);
                                if (written > 0 && written < (int) sizeof scratch)
                                    {
                                        length = (size_t) written;
                                    }
                                else
                                    {
                                        scratch[0] = '?';
                                        length     = 1U;
                                    }
                            }
                        else
                            {
                                scratch[0] = (char) *byte_ptr;
                                length     = 1U;
                            }
                        break;
                }
            writer_append(writer, scratch, length);
        }
}

static void write_flags_array(gl_json_writer_t* writer, gitledger_error_flags_t flags)
{
    writer_append_char(writer, '[');
    bool first = true;
    if ((flags & GL_ERRFLAG_RETRYABLE) != 0U)
        {
            const char* name = "\"RETRYABLE\"";
            if (!first)
                {
                    writer_append_char(writer, ',');
                }
            writer_append(writer, name, strlen(name));
            first = false;
        }
    if ((flags & GL_ERRFLAG_PERMANENT) != 0U)
        {
            const char* name = "\"PERMANENT\"";
            if (!first)
                {
                    writer_append_char(writer, ',');
                }
            writer_append(writer, name, strlen(name));
            first = false;
        }
    if ((flags & GL_ERRFLAG_AUTH) != 0U)
        {
            const char* name = "\"AUTH\"";
            if (!first)
                {
                    writer_append_char(writer, ',');
                }
            writer_append(writer, name, strlen(name));
        }
    writer_append_char(writer, ']');
}

static void json_write_error_fields(gl_json_writer_t* writer, const gitledger_error_t* err)
{
    const char* domain = domain_to_string(err->domain);
    GITLEDGER_JSON_APPEND_LITERAL(writer, "\"domain\":\"");
    writer_append(writer, domain, strlen(domain));
    writer_append_char(writer, '\"');

    GITLEDGER_JSON_APPEND_LITERAL(writer, ",\"code\":\"");
    const char* code = code_to_string(err->code);
    writer_append(writer, code, strlen(code));
    writer_append_char(writer, '\"');

    GITLEDGER_JSON_APPEND_LITERAL(writer, ",\"flags\":");
    write_flags_array(writer, err->flags);

    GITLEDGER_JSON_APPEND_LITERAL(writer, ",\"message\":\"");
    writer_append_escaped(writer, err->message ? err->message : "");
    writer_append_char(writer, '\"');

    if (err->file)
        {
            GITLEDGER_JSON_APPEND_LITERAL(writer, ",\"file\":\"");
            writer_append_escaped(writer, err->file);
            writer_append_char(writer, '\"');
            GITLEDGER_JSON_APPEND_LITERAL(writer, ",\"line\":");
            char linebuf[GL_JSON_LINE_BUFFER_SIZE];
            const int length = gl_safe_snprintf(linebuf, sizeof linebuf, "%d", err->line);
            if (length > 0)
                {
                    writer_append(writer, linebuf, (size_t) length);
                }
        }

    if (err->func)
        {
            GITLEDGER_JSON_APPEND_LITERAL(writer, ",\"func\":\"");
            writer_append_escaped(writer, err->func);
            writer_append_char(writer, '\"');
        }
}

static bool json_push_cause_frame(error_json_frame_t* stack,
                                  size_t*              stack_size,
                                  size_t               capacity,
                                  const gitledger_error_t* cause)
{
    if (!cause || *stack_size >= capacity)
        {
            return false;
        }
    stack[*stack_size] = (error_json_frame_t){ cause, 0 };
    ++(*stack_size);
    return true;
}

static size_t json_error_chain_depth(const gitledger_error_t* err)
{
    size_t depth = 0;
    for (const gitledger_error_t* cur = err; cur; cur = cur->cause)
        {
            ++depth;
        }
    return depth;
}

static error_json_frame_t* json_acquire_stack(size_t depth,
                                              error_json_frame_t* static_storage,
                                              size_t* capacity,
                                              bool* use_heap)
{
    *capacity = GL_JSON_STATIC_STACK_DEPTH;
    *use_heap = false;
    if (depth <= *capacity)
        {
            return static_storage;
        }

    error_json_frame_t* heap = (error_json_frame_t*) malloc(sizeof(error_json_frame_t) * depth);
    if (heap)
        {
            *capacity = depth;
            *use_heap = true;
            return heap;
        }
    return static_storage;
}

static void json_release_stack(error_json_frame_t* stack, bool use_heap)
{
    if (use_heap)
        {
            free(stack);
        }
}

static void json_write_error(gl_json_writer_t* writer, const gitledger_error_t* err)
{
    const size_t depth = json_error_chain_depth(err);
    error_json_frame_t stack_static[GL_JSON_STATIC_STACK_DEPTH];
    size_t capacity = 0;
    bool   use_heap = false;
    error_json_frame_t* stack = json_acquire_stack(depth, stack_static, &capacity, &use_heap);

    size_t stack_size = 0;
    if (err)
        {
            stack[stack_size++] = (error_json_frame_t){ err, 0 };
        }

    while (stack_size > 0)
        {
            error_json_frame_t* frame = &stack[stack_size - 1];
            const gitledger_error_t* cur = frame->err;

            if (frame->state == 0)
                {
                    writer_append_char(writer, '{');

                    json_write_error_fields(writer, cur);

                    frame->state = 1;
                    if (cur->cause)
                        {
                            if (json_push_cause_frame(stack, &stack_size, capacity, cur->cause))
                                {
                                    GITLEDGER_JSON_APPEND_LITERAL(writer, ",\"cause\":");
                                    continue;
                                }
                            GITLEDGER_JSON_APPEND_LITERAL(writer, ",\"cause\":{\"truncated\":true}");
                        }

                }

            writer_append_char(writer, '}');
            --stack_size;
        }

    json_release_stack(stack, use_heap);
}

gitledger_error_flags_t gitledger_error_flags(const gitledger_error_t* err)
{
    return err ? err->flags : GL_ERRFLAG_NONE;
}

gitledger_domain_t gitledger_error_domain(const gitledger_error_t* err)
{
    return err ? err->domain : GL_DOMAIN_GENERIC;
}

gitledger_code_t gitledger_error_code(const gitledger_error_t* err)
{
    return err ? err->code : GL_CODE_UNKNOWN;
}

const char* gitledger_error_message(const gitledger_error_t* err)
{
    if (!err)
        {
            return "";
        }
    if (!err->message)
        {
            return "";
        }
    return err->message;
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
                    gitledger_error_t* next = current->cause;
                    current->cause          = NULL;
                    gitledger_context_untrack_error_internal(current->ctx, current);
                    free_error(current);
                    current = next;
                    continue;
                }
            break;
        }
}

static gitledger_error_t* create_error_internal(gitledger_context_t*     ctx,
                                                gitledger_domain_t       domain,
                                                gitledger_code_t         code,
                                                const gitledger_error_t* cause,
                                                gitledger_source_location_t location,
                                                const char*              fmt,
                                                va_list                  args)
{
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

    gitledger_context_track_error_internal(ctx, err);
    return err;
}

gitledger_error_t* gitledger_error_create_ctx_loc_v(gitledger_context_t*     ctx,
                                                    gitledger_domain_t       domain,
                                                    gitledger_code_t         code,
                                                    gitledger_source_location_t location,
                                                    const char*              fmt,
                                                    va_list                  args)
{
    return create_error_internal(ctx, domain, code, NULL, location, fmt ? fmt : "", args);
}

gitledger_error_t* gitledger_error_create_ctx_loc(gitledger_context_t* ctx,
                                                  gitledger_domain_t    domain,
                                                  gitledger_code_t      code,
                                                  gitledger_source_location_t location,
                                                  const char*           fmt,
                                                  ...)
{
    va_list args;
    va_start(args, fmt);
    gitledger_error_t* err = gitledger_error_create_ctx_loc_v(ctx, domain, code, location, fmt, args);
    va_end(args);
    return err;
}

gitledger_error_t* gitledger_error_with_cause_ctx_loc_v(gitledger_context_t*     ctx,
                                                        gitledger_domain_t       domain,
                                                        gitledger_code_t         code,
                                                        const gitledger_error_t* cause,
                                                        gitledger_source_location_t location,
                                                        const char*              fmt,
                                                        va_list                  args)
{
    return create_error_internal(ctx, domain, code, cause, location, fmt ? fmt : "", args);
}

gitledger_error_t* gitledger_error_with_cause_ctx_loc(gitledger_context_t*     ctx,
                                                      gitledger_domain_t       domain,
                                                      gitledger_code_t         code,
                                                      const gitledger_error_t* cause,
                                                      gitledger_source_location_t location,
                                                      const char*              fmt,
                                                      ...)
{
    va_list args;
    va_start(args, fmt);
    gitledger_error_t* err =
        gitledger_error_with_cause_ctx_loc_v(ctx, domain, code, cause, location, fmt, args);
    va_end(args);
    return err;
}

void gitledger_error_walk(const gitledger_error_t* top,
                          gitledger_error_visitor_t visitor,
                          void*                     userdata)
{
    const gitledger_error_t* current = top;
    while (current)
        {
            if (!visitor(current, userdata))
                {
                    return;
                }
            current = current->cause;
        }
}

size_t gitledger_error_render_json(const gitledger_error_t* err, char* buf, size_t size)
{
    if (!err)
        {
            if (buf && size)
                {
                    buf[0] = '\0';
                }
            return 1;
        }

    gl_json_writer_t writer = gl_json_writer_init(buf, size);
    json_write_error(&writer, err);

    if (buf && size)
        {
            if (writer.remaining == 0U)
                {
                    buf[size - 1U] = '\0';
                }
            else if (writer.cursor)
                {
                    *writer.cursor = '\0';
                }
        }

    return writer.total + 1U;
}

const char* gitledger_error_json(gitledger_error_t* err)
{
    if (!err)
        {
            return "{}";
        }
    if (!err->ctx)
        {
            return "{}";
        }
    if (err->json_cache)
        {
            return err->json_cache;
        }

    size_t needed = gitledger_error_render_json(err, NULL, 0);
    char*  buf    = (char*) gitledger_context_alloc(err->ctx, needed);
    if (!buf)
        {
            return "{}";
        }
    gitledger_error_render_json(err, buf, needed);
    err->json_cache = buf;
    return buf;
}
