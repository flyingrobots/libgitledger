#include "gitledger/context.h"
#include "gitledger/error.h"

#ifdef NDEBUG
static void test_teardown_refusal_with_live_errors(void);
#endif

#include <assert.h>
#include <limits.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static bool collect_messages(const gitledger_error_t* err, void* userdata)
{
    (void) err;
    (*(int*) userdata)++;
    return true;
}

typedef struct counting_allocator_state
{
    size_t allocations;
    size_t frees;
} counting_allocator_state_t;

static void* counting_alloc(void* userdata, size_t size)
{
    counting_allocator_state_t* state = (counting_allocator_state_t*) userdata;
    void*                       ptr   = malloc(size);
    if (ptr)
        {
            state->allocations++;
        }
    return ptr;
}

static void counting_free(void* userdata, void* ptr)
{
    counting_allocator_state_t* state = (counting_allocator_state_t*) userdata;
    if (ptr)
        {
            state->frees++;
        }
    free(ptr);
}

static gitledger_context_t* create_counting_context(counting_allocator_state_t* state)
{
    gitledger_allocator_t alloc = {
        .alloc = counting_alloc, .free = counting_free, .userdata = state};
    return gitledger_context_create(&alloc);
}

static void test_basic_json_behavior(void)
{
    fprintf(stderr, "test_basic_json_behavior\n");
    gitledger_context_t* ctx = gitledger_context_create(NULL);
    assert(ctx);

    gitledger_error_t* leaf = GITLEDGER_ERROR_CREATE(ctx, GL_DOMAIN_GIT, GL_CODE_NOT_FOUND,
                                                     "Object %s not found", "abc123");
    assert(leaf);

    gitledger_error_t* root =
        GITLEDGER_ERROR_WITH_CAUSE(ctx, GL_DOMAIN_POLICY, GL_CODE_POLICY_VIOLATION, leaf,
                                   "Policy blocked update for %s", "refs/main");
    assert(root);

    assert(gitledger_error_cause(root) == leaf);
    assert((gitledger_error_flags(root) & GL_ERRFLAG_PERMANENT) != 0U);

    size_t required = gitledger_error_render_json(root, NULL, 0);
    assert(required != SIZE_MAX && required > 1U);
    char* json_buffer = malloc(sizeof *json_buffer * required);
    assert(json_buffer);
    size_t actual = gitledger_error_render_json(root, json_buffer, required);
    assert(actual == required);
    (void) actual;
    assert(json_buffer[0] == '{');

    const char* cached = gitledger_error_json(root);
    assert(cached && cached[0] == '{');
    const char* cached_again = gitledger_error_json(root);
    assert(cached == cached_again);
    assert(strcmp(cached, json_buffer) == 0);
    (void) cached;
    (void) cached_again;

    int visited = 0;
    gitledger_error_walk(root, collect_messages, &visited);
    assert(visited == 2);

    free(json_buffer);
    gitledger_error_release(root);
    gitledger_error_release(leaf);
    gitledger_context_release(ctx);
}

static size_t count_occurrences(const char* haystack, const char* needle)
{
    size_t      count  = 0;
    size_t      step   = strlen(needle);
    const char* cursor = haystack;
    while ((cursor = strstr(cursor, needle)) != NULL)
        {
            ++count;
            cursor += step;
        }
    return count;
}

static void test_deep_cause_chain(void)
{
    fprintf(stderr, "test_deep_cause_chain\n");
    gitledger_context_t* ctx = gitledger_context_create(NULL);
    assert(ctx);

    const size_t       depth   = 32;
    gitledger_error_t* current = GITLEDGER_ERROR_CREATE(ctx, GL_DOMAIN_GENERIC, GL_CODE_UNKNOWN,
                                                        "layer %lu", (unsigned long) 0);
    assert(current);

    for (size_t i = 1; i < depth; ++i)
        {
            gitledger_error_t* next = GITLEDGER_ERROR_WITH_CAUSE(
                ctx, GL_DOMAIN_GENERIC, GL_CODE_UNKNOWN, current, "layer %lu", (unsigned long) i);
            assert(next);
            gitledger_error_release(current);
            current = next;
        }

    size_t required = gitledger_error_render_json(current, NULL, 0);
    assert(required != SIZE_MAX && required > 1U);
    char* json_buffer = malloc(sizeof *json_buffer * required);
    assert(json_buffer);
    gitledger_error_render_json(current, json_buffer, required);

    const char* pattern           = "\"cause\"";
    size_t      cause_occurrences = count_occurrences(json_buffer, pattern);
    assert(cause_occurrences == depth - 1U);
    (void) cause_occurrences;

    free(json_buffer);
    gitledger_error_release(current);
    gitledger_context_release(ctx);
}

static void test_allocator_balance(void)
{
    fprintf(stderr, "test_allocator_balance\n");
    counting_allocator_state_t state = {0, 0};
    gitledger_context_t*       ctx   = create_counting_context(&state);
    assert(ctx);

    gitledger_error_t* base = GITLEDGER_ERROR_CREATE(ctx, GL_DOMAIN_GENERIC,
                                                     GL_CODE_INVALID_ARGUMENT, "%s", "base error");
    assert(base);

    gitledger_error_t* top = GITLEDGER_ERROR_WITH_CAUSE(ctx, GL_DOMAIN_GENERIC, GL_CODE_CONFLICT,
                                                        base, "%s", "top error");
    assert(top);

    gitledger_error_release(top);
    gitledger_error_release(base);
    gitledger_context_release(ctx);

    assert(state.allocations == state.frees);
}

typedef struct failing_allocator_state
{
    size_t calls;
    size_t fail_at; /* 1-based: return NULL on this allocation call */
} failing_allocator_state_t;

static void* failing_alloc(void* userdata, size_t size)
{
    failing_allocator_state_t* st = (failing_allocator_state_t*) userdata;
    st->calls++;
    if (st->fail_at != 0 && st->calls == st->fail_at)
        {
            (void) size;
            return NULL; /* simulate OOM at specific allocation */
        }
    return malloc(size);
}

static void failing_free(void* userdata, void* ptr)
{
    (void) userdata;
    free(ptr);
}

static void test_error_detaches_when_tracking_fails(void)
{
    fprintf(stderr, "test_error_detaches_when_tracking_fails\n");

    /* Allocation sequence in error creation:
       1) allocate_error -> gitledger_error_t
       2) duplicate_format -> message buffer
       3) context_register_error -> registry node (we fail here) */
    failing_allocator_state_t st = {0, 3};
    gitledger_allocator_t     alloc = {.alloc = failing_alloc, .free = failing_free, .userdata = &st};
    gitledger_context_t*      ctx   = gitledger_context_create(&alloc);
    assert(ctx);

    gitledger_error_t* err = GITLEDGER_ERROR_CREATE(ctx, GL_DOMAIN_GENERIC, GL_CODE_UNKNOWN,
                                                    "%s", "track failure path");
    assert(err);

    /* With tracking failed, the context must be destroyable immediately. */
    int rc = gitledger_context_try_release(ctx);
    (void) rc; /* keep used even under NDEBUG */
    assert(rc == 1);

    /* The error must remain usable and releasable without touching a freed ctx. */
    const char* json = gitledger_error_json(err);
    (void) json; /* keep used even under NDEBUG */
    assert(json && json[0] == '{');
    gitledger_error_release(err);
}

int main(void)
{
    test_basic_json_behavior();
    test_deep_cause_chain();
    test_allocator_balance();
    test_error_detaches_when_tracking_fails();
#ifdef NDEBUG
    /* Release builds must refuse context teardown with live errors. */
    test_teardown_refusal_with_live_errors();
#endif
    return 0;
}

#ifdef NDEBUG
static void test_teardown_refusal_with_live_errors(void)
{
    fprintf(stderr, "test_teardown_refusal_with_live_errors (Release)\n");
    gitledger_context_t* ctx = gitledger_context_create(NULL);
    assert(ctx);

    gitledger_error_t* err =
        GITLEDGER_ERROR_CREATE(ctx, GL_DOMAIN_GENERIC, GL_CODE_UNKNOWN, "%s", "live");
    assert(err);

    /* First try to release the context should be refused because err is live. */
    int rc = gitledger_context_try_release(ctx);
    (void) rc;
    assert(rc == 0);
    assert(gitledger_context_valid(ctx) == 1);

    gitledger_error_release(err);
    rc = gitledger_context_try_release(ctx);
    assert(rc == 1);
}
#endif
