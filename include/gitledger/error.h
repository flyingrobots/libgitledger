#ifndef GITLEDGER_ERROR_H
#define GITLEDGER_ERROR_H

#include <stddef.h>
#include <stdbool.h>
#include <stdarg.h>
#include <stdint.h>

#include "gitledger/context.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef struct gitledger_error gitledger_error_t;

typedef enum
{
    GL_STATUS_OK    = 0,
    GL_STATUS_ERROR = 1
} gitledger_status_t;

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

typedef struct
{
    const char* file;
    int         line;
    const char* func;
} gitledger_source_location_t;

gitledger_domain_t      gitledger_error_domain(const gitledger_error_t* err);
gitledger_code_t        gitledger_error_code(const gitledger_error_t* err);
gitledger_error_flags_t gitledger_error_flags(const gitledger_error_t* err);
const char*             gitledger_error_message(const gitledger_error_t* err);
const gitledger_error_t* gitledger_error_cause(const gitledger_error_t* err);
const char*             gitledger_error_file(const gitledger_error_t* err);
int                     gitledger_error_line(const gitledger_error_t* err);
const char*             gitledger_error_func(const gitledger_error_t* err);

void gitledger_error_retain(gitledger_error_t* err);
void gitledger_error_release(gitledger_error_t* err);

gitledger_error_t* gitledger_error_create_ctx_loc(gitledger_context_t* ctx,
                                                  gitledger_domain_t    domain,
                                                  gitledger_code_t      code,
                                                  gitledger_source_location_t location,
                                                  const char*           fmt,
                                                  ...);

gitledger_error_t* gitledger_error_create_ctx_loc_v(gitledger_context_t*     ctx,
                                                    gitledger_domain_t       domain,
                                                    gitledger_code_t         code,
                                                    gitledger_source_location_t location,
                                                    const char*              fmt,
                                                    va_list                  args);

gitledger_error_t* gitledger_error_with_cause_ctx_loc(gitledger_context_t*     ctx,
                                                      gitledger_domain_t       domain,
                                                      gitledger_code_t         code,
                                                      const gitledger_error_t* cause,
                                                      gitledger_source_location_t location,
                                                      const char*              fmt,
                                                      ...);

gitledger_error_t* gitledger_error_with_cause_ctx_loc_v(gitledger_context_t*     ctx,
                                                        gitledger_domain_t       domain,
                                                        gitledger_code_t         code,
                                                        const gitledger_error_t* cause,
                                                        gitledger_source_location_t location,
                                                        const char*              fmt,
                                                        va_list                  args);

static inline gitledger_error_t* gitledger_error_create_ctx_auto(gitledger_context_t* ctx,
                                                                 gitledger_domain_t    domain,
                                                                 gitledger_code_t      code,
                                                                 const char*           fmt,
                                                                 ...)
{
    gitledger_source_location_t location = { __FILE__, __LINE__, __func__ };
    va_list                     args;
    va_start(args, fmt);
    gitledger_error_t* err = gitledger_error_create_ctx_loc_v(ctx, domain, code, location, fmt, args);
    va_end(args);
    return err;
}

static inline gitledger_error_t* gitledger_error_with_cause_ctx_auto(gitledger_context_t*     ctx,
                                                                     gitledger_domain_t       domain,
                                                                     gitledger_code_t         code,
                                                                     const gitledger_error_t* cause,
                                                                     const char*              fmt,
                                                                     ...)
{
    gitledger_source_location_t location = { __FILE__, __LINE__, __func__ };
    va_list                     args;
    va_start(args, fmt);
    gitledger_error_t* err =
        gitledger_error_with_cause_ctx_loc_v(ctx, domain, code, cause, location, fmt, args);
    va_end(args);
    return err;
}

#define GITLEDGER_ERROR_CREATE(ctx, domain, code, ...) \
    gitledger_error_create_ctx_auto((ctx), (domain), (code), __VA_ARGS__)

#define GITLEDGER_ERROR_WITH_CAUSE(ctx, domain, code, cause, ...) \
    gitledger_error_with_cause_ctx_auto((ctx), (domain), (code), (cause), __VA_ARGS__)

typedef bool (*gitledger_error_visitor_t)(const gitledger_error_t* err, void* userdata);
void gitledger_error_walk(const gitledger_error_t* top,
                          gitledger_error_visitor_t visitor,
                          void*                     userdata);

size_t      gitledger_error_render_json(const gitledger_error_t* err, char* buf, size_t size);
const char* gitledger_error_json(gitledger_error_t* err);

#ifdef __cplusplus
}
#endif

#endif /* GITLEDGER_ERROR_H */
