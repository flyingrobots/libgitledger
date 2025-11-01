#ifndef GITLEDGER_ERROR_H
#define GITLEDGER_ERROR_H

#include <stdarg.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#include "gitledger/context.h"
#include "gitledger/export.h"

#ifdef __cplusplus
extern "C"
{
#endif

    typedef struct gitledger_error gitledger_error_t;

    typedef enum
    {
        GL_DOMAIN_OK        = 0,
        GL_DOMAIN_GENERIC   = 1,
        GL_DOMAIN_ALLOCATOR = 2,
        GL_DOMAIN_GIT       = 3,
        GL_DOMAIN_POLICY    = 4,
        GL_DOMAIN_TRUST     = 5,
        GL_DOMAIN_IO        = 6,
        GL_DOMAIN_CONFIG    = 7
    } gitledger_domain_t;

    typedef enum
    {
        GL_CODE_OK                 = 0,
        GL_CODE_UNKNOWN            = 1,
        GL_CODE_OOM                = 2,
        GL_CODE_INVALID_ARGUMENT   = 3,
        GL_CODE_NOT_FOUND          = 4,
        GL_CODE_CONFLICT           = 5,
        GL_CODE_PERMISSION_DENIED  = 6,
        GL_CODE_POLICY_VIOLATION   = 7,
        GL_CODE_TRUST_VIOLATION    = 8,
        GL_CODE_IO_ERROR           = 9,
        GL_CODE_DEPENDENCY_MISSING = 10
    } gitledger_code_t;

    typedef uint32_t gitledger_error_flags_t;

    enum
    {
        GL_ERRFLAG_NONE      = (gitledger_error_flags_t) 0,
        GL_ERRFLAG_RETRYABLE = (gitledger_error_flags_t) 1U << 0,
        GL_ERRFLAG_PERMANENT = (gitledger_error_flags_t) 1U << 1,
        GL_ERRFLAG_AUTH      = (gitledger_error_flags_t) 1U << 2
    };

/**
 * Maximum causal depth rendered into JSON before truncation.
 * API NOTE: increasing this constant changes output and behaviour; callers and
 * downstream tools depending on the previous depth may break.
 */
#define GITLEDGER_ERROR_MAX_DEPTH 64U

    typedef struct
    {
        const char* file;
        int         line;
        const char* func;
    } gitledger_source_location_t;

    GITLEDGER_API gitledger_domain_t       gitledger_error_domain(const gitledger_error_t* err);
    GITLEDGER_API gitledger_code_t         gitledger_error_code(const gitledger_error_t* err);
    GITLEDGER_API gitledger_error_flags_t  gitledger_error_flags(const gitledger_error_t* err);
    GITLEDGER_API const char*              gitledger_error_message(const gitledger_error_t* err);
    GITLEDGER_API const gitledger_error_t* gitledger_error_cause(const gitledger_error_t* err);
    GITLEDGER_API const char*              gitledger_error_file(const gitledger_error_t* err);
    GITLEDGER_API int                      gitledger_error_line(const gitledger_error_t* err);
    GITLEDGER_API const char*              gitledger_error_func(const gitledger_error_t* err);

    GITLEDGER_API const char* gitledger_domain_name(gitledger_domain_t domain);
    GITLEDGER_API const char* gitledger_code_name(gitledger_code_t code);
    GITLEDGER_API size_t      gitledger_error_flags_format(gitledger_error_flags_t flags, char* buf,
                                                           size_t size);

    GITLEDGER_API void gitledger_error_retain(gitledger_error_t* err);
    GITLEDGER_API void gitledger_error_release(gitledger_error_t* err);

    /*
     * Ownership & Lifetime
     * --------------------
     * - Create/return semantics: Functions that return gitledger_error_t*
     *   transfer one owning reference to the caller (initial refcount = 1).
     * - Cause retention: gitledger_error_with_cause_* retains the supplied
     *   cause (when non-NULL); the parent owns exactly one reference to its
     *   cause and releasing the parent releases that reference.
     * - Borrowed access: gitledger_error_cause(e) returns a borrowed pointer;
     *   callers must call gitledger_error_retain() if they need the cause to
     *   outlive the parent.
     * - Context teardown: destroying a context with live errors is forbidden.
     *   WHY: this prevents double-free/use-after-free hazards during context
     *   destruction and ensures snapshot-allocated error state remains safe
     *   to reference. In Debug builds we abort; in Release builds we refuse
     *   teardown and emit a diagnostic to stderr. Always release all errors
     *   before releasing their context.
     */

    GITLEDGER_API gitledger_error_t*
    gitledger_error_create_ctx_loc(gitledger_context_t* ctx, gitledger_domain_t domain,
                                   gitledger_code_t code, gitledger_source_location_t location,
                                   const char* fmt, ...) GITLEDGER_ATTR_PRINTF(5, 6);

    GITLEDGER_API gitledger_error_t*
    gitledger_error_create_ctx_loc_v(gitledger_context_t* ctx, gitledger_domain_t domain,
                                     gitledger_code_t code, gitledger_source_location_t location,
                                     const char* fmt, va_list args) GITLEDGER_ATTR_PRINTF(5, 0);

    GITLEDGER_API gitledger_error_t*
    gitledger_error_with_cause_ctx_loc(gitledger_context_t* ctx, gitledger_domain_t domain,
                                       gitledger_code_t code, const gitledger_error_t* cause,
                                       gitledger_source_location_t location, const char* fmt, ...)
        GITLEDGER_ATTR_PRINTF(6, 7);

    GITLEDGER_API gitledger_error_t*
    gitledger_error_with_cause_ctx_loc_v(gitledger_context_t* ctx, gitledger_domain_t domain,
                                         gitledger_code_t code, const gitledger_error_t* cause,
                                         gitledger_source_location_t location, const char* fmt,
                                         va_list args) GITLEDGER_ATTR_PRINTF(6, 0);

    /* Macros capture caller location at the call-site. Callers must supply a
       format string as the first variadic argument; pass "" when no message
       arguments are needed. Using only __VA_ARGS__ avoids GNU-specific empty
       varargs handling. */
#define GITLEDGER_ERROR_CREATE(ctx, domain, code, ...)                                             \
    gitledger_error_create_ctx_loc((ctx), (domain), (code),                                        \
                                   (gitledger_source_location_t) {__FILE__, __LINE__, __func__},   \
                                   __VA_ARGS__)

#define GITLEDGER_ERROR_WITH_CAUSE(ctx, domain, code, cause, ...)                                  \
    gitledger_error_with_cause_ctx_loc(                                                            \
        (ctx), (domain), (code), (cause),                                                          \
        (gitledger_source_location_t) {__FILE__, __LINE__, __func__}, __VA_ARGS__)

    typedef bool (*gitledger_error_visitor_t)(const gitledger_error_t* err, void* userdata);
    GITLEDGER_API void gitledger_error_walk(const gitledger_error_t*  top,
                                            gitledger_error_visitor_t visitor, void* userdata);

    GITLEDGER_API size_t      gitledger_error_render_json(const gitledger_error_t* err, char* buf,
                                                          size_t size);
    GITLEDGER_API const char* gitledger_error_json(gitledger_error_t* err);
    GITLEDGER_API char* gitledger_error_json_copy(gitledger_context_t* ctx, gitledger_error_t* err);
    GITLEDGER_API char* gitledger_error_message_copy(gitledger_context_t*     ctx,
                                                     const gitledger_error_t* err);

#ifdef __cplusplus
}
#endif

#endif /* GITLEDGER_ERROR_H */
