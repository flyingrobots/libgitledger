# `libgitledger`

> A *Git-Native* Ledger Library (C, `libgit2`): Spec + Project Plan with Step-By-Step Tasks & Tests

This is the unification of two proven systems: **Shiplog**’s field-tested deployment ledger and **git-mind**’s hexagonal, binary-safe engine, distilled into a reusable C library with a stable ABI and high-performance indexing. It uses Git itself as the database, leans on `libgit2`, and bakes in policy + trust. In short: batteries included, foot-guns removed.

---

## N. Document status

### Intended Audience

- Myself
- Reviewers
- Collaborators
- Future binding authors

### Decision log (short)

- **Git backend**: `libgit2` (not shelling out) — keeps things fast, safe, and embeddable.
- **Architecture**: strict Hexagonal (ports & adapters).
- **Governance**: Policy-as-Code + Multi-Signature Trust are first-class in the library (not app-specific).
- **Query performance**: Roaring bitmap cache, rebuildable.

These choices align with my previous work, the `git-mind`/`shiplog` lineage.

---

## I. Overview

`libgitledger` is a portable, embeddable C library for append-only ledgers inside a Git repository. Each ledger is a linear history of Git commits on dedicated refs; entries are optionally signed, policy-checked, and indexed for instant queries. It enables both human-readable (`shiplog` style) and binary-safe (`git-mind` style) payloads via a pluggable encoder. ￼

**Why this exists**: I’ve built the pattern twice already. `shiplog` (battle-tested CLI & policy/trust) and `git-mind` (rigorous hexagonal architecture + roaring bitmap cache). `libgitledger` fuses them into one stable core library with bindings for Go/JS/Python.

---

## II. Goals & Non-Goals

### Goals

- Git-native persistence (objects + refs are the DB).
- Append-only (fast-forward only), immutability by default.
- Library-first: stable C ABI, no global state; embeddable; safe for bindings.
- Pluggable encoder/indexer so shiplog and git-mind both fit naturally. ￼
- Policy as Code and Multi-Signature Trust (chain or attestation) built-in. ￼
- High-performance queries using roaring bitmap cache, fully rebuildable. ￼

### Non-Goals

- Not a full “ledger server”. No background daemons; it’s a library.
- Not a replacement for Git’s transport/auth or repo mgmt.
- No reliance on shelling out to `git(1)` in core; a separate optional adapter may be explored later for platforms where `libgit2` is unavailable.

---

## III. Core Principles

- **Git-Native**: object store + refs as the database; ref updates = writes.
- **Append-Only**: fast-forward updates; rejects history rewrites.
- **Hexagonal Architecture**: domain core is pure C; all I/O behind ports; libgit2 only in adapters. ￼
- **Pluggable Everything**: allocators, loggers, encoders, indexers. ￼
- **Secure & Auditable**: signing, policy enforcement, trust thresholds. ￼
- **Portable & Bindable**: stable ABI; minimal dependencies; deterministic behavior.

---

## IV. Reference Namespace & Data Model

**Ref map (per ledger `L`)**:

- **Journal (append-only commits)**: `refs/gitledger/journal/<L>`
- **Cache (roaring bitmaps)**: `refs/gitledger/cache/<L>`
- **Policy doc**: `refs/gitledger/policy/<L>`
- **Trust doc**: `refs/gitledger/trust/<L>`
- **Entry notes**: `refs/gitledger/notes/<L>`
- **Tag-entry associations (notes on tag objects)**: `refs/gitledger/tag_notes`

This structure blends `shiplog`’s policy/trust refs and `git-mind`’s journal/cache separation.

**Entry** = a Git commit on the ledger ref.

- Payload lives in the commit message (encoder-defined; can be human-readable with JSON trailers like `shiplog` or base64-CBOR like `git-mind`).
- **Notes**: arbitrary blobs (`stdout`/`stderr`, artifacts) via Git notes on the entry commit. (Shiplog’s `run` semantics made general.) ￼
- **Signatures**: commit signatures or detached attestations, enforced by policy/trust. ￼

---

## V. Architecture

### 5.1 Hexagonal (Ports & Adapters)

```mermaid
graph LR
    subgraph "External World (Clients & Infrastructure)"
        CLI["User / Calling App (e.g., git-mind)"]
        libgit2(libgit2 Library)
        FS(Filesystem / POSIX)
        System_Logger(Standard I/O / System Logger)
        Env(Environment Variables)
        Metrics(Prometheus Metrics)
        Crypto_Backend(GPGME / SSH-Agent)
    end

    subgraph "libgitledger Library"
        subgraph "Adapters (Concrete Implementations)"
            A[libgit2_repository_adapter.c] --> libgit2
            B[posix_fs_adapter.c] --> FS
            C[stdio_logger_adapter.c] --> System_Logger
            D[env_adapter.c] --> Env
            E[prom_metrics_adapter.c] --> Metrics
            F[crypto_signer_adapter.c] --> Crypto_Backend
        end

        subgraph "Ports (Abstract Interfaces - C Vtables)"
            subgraph "Inbound/Driving Ports (Public API)"
                P_CTX(gitledger_init/shutdown)
                P_LEDGER(gitledger_ledger_open/close)
                P_APPEND(gitledger_append)
                P_QUERY(gitledger_query_terms)
                P_CACHE_REBUILD(gitledger_cache_rebuild)
                P_POLICY_TRUST(gitledger_policy/trust_set/get)
                P_VERIFY(gitledger_verify_integrity)
                P_NOTES(gitledger_attach_note)
                P_TAGS(gitledger_tag_associate)
            end
            subgraph "Outbound/Driven Ports (Dependencies)"
                PO_GIT(git_repo_port)
                PO_TIME(time_port)
                PO_ENV(env_port)
                PO_FS_TEMP(fs_temp_port)
                PO_LOGGER(logger_port)
                PO_METRICS(metrics_port)
                PO_SIGNER(signing_port)
            end
        end

        subgraph "Application Layer (Use Cases, Orchestration)"
            AL[Application Services: Entry Append, Query Orchestration, Policy/Trust Mgmt]
        end

        subgraph "Domain Layer (Pure Business Logic - Policy, Trust, Journal, Cache Logic)"
            DL_JOURNAL[Journal Core: Entry, Commit Plans, CBOR/Encoder]
            DL_POLICY[Policy Logic: Rules, Enforcement]
            DL_TRUST[Trust Logic: Multi-Sig, Keys, Verification]
            DL_CACHE_CORE[Cache Core: Roaring Bitmaps, Term Management]
            DL_VERIFICATION[Verification Logic: Chain, Signatures]
            PL_ENCODER(Pluggable Encoder: encode_fn)
            PL_INDEXER(Pluggable Indexer: terms_for_payload_fn)
        end
    end

    CLI --> P_CTX
    CLI --> P_LEDGER
    CLI --> P_APPEND
    CLI --> P_QUERY
    CLI --> P_CACHE_REBUILD
    CLI --> P_POLICY_TRUST
    CLI --> P_VERIFY
    CLI --> P_NOTES
    CLI --> P_TAGS

    P_APPEND -- "uses" --> PL_ENCODER
    P_CACHE_REBUILD -- "uses" --> PL_INDEXER

    P_CTX -- "configures" --> AL
    P_LEDGER -- "configures" --> AL
    P_APPEND --> AL
    P_QUERY --> AL
    P_CACHE_REBUILD --> AL
    P_POLICY_TRUST --> AL
    P_VERIFY --> AL
    P_NOTES --> AL
    P_TAGS --> AL

    AL -- "orchestrates" --> DL_JOURNAL
    AL -- "enforces" --> DL_POLICY
    AL -- "verifies" --> DL_TRUST
    AL -- "builds/queries" --> DL_CACHE_CORE
    AL -- "utilizes" --> DL_VERIFICATION

    DL_JOURNAL -- "needs I/O" --> PO_GIT
    DL_POLICY -- "needs I/O" --> PO_GIT
    DL_TRUST -- "needs I/O" --> PO_GIT
    DL_CACHE_CORE -- "needs I/O" --> PO_GIT
    DL_CACHE_CORE -- "needs temp FS" --> PO_FS_TEMP
    DL_VERIFICATION -- "needs Signing" --> PO_SIGNER
    DL_VERIFICATION -- "needs I/O" --> PO_GIT

    AL -- "needs Time/Env/Logging/Metrics" --> PO_TIME
    AL -- "needs Time/Env/Logging/Metrics" --> PO_ENV
    AL -- "needs Time/Env/Logging/Metrics" --> PO_LOGGER
    AL -- "needs Time/Env/Logging/Metrics" --> PO_METRICS

    PO_GIT -- "implements" --> A
    PO_FS_TEMP -- "implements" --> B
    PO_LOGGER -- "implements" --> C
    PO_ENV -- "implements" --> D
    PO_METRICS -- "implements" --> E
    PO_SIGNER -- "implements" --> F
    PO_TIME -- "implements" --> B

    style CLI fill:#ADD8E6,stroke:#333,stroke-width:2px
    style libgit2 fill:#FFFACD,stroke:#333,stroke-width:2px
    style FS fill:#FFFACD,stroke:#333,stroke-width:2px
    style System_Logger fill:#FFFACD,stroke:#333,stroke-width:2px
    style Env fill:#FFFACD,stroke:#333,stroke-width:2px
    style Metrics fill:#FFFACD,stroke:#333,stroke-width:2px
    style Crypto_Backend fill:#FFFACD,stroke:#333,stroke-width:2px

    style P_CTX fill:#90EE90,stroke:#333,stroke-width:2px
    style P_LEDGER fill:#90EE90,stroke:#333,stroke-width:2px
    style P_APPEND fill:#90EE90,stroke:#333,stroke-width:2px
    style P_QUERY fill:#90EE90,stroke:#333,stroke-width:2px
    style P_CACHE_REBUILD fill:#90EE90,stroke:#333,stroke-width:2px
    style P_POLICY_TRUST fill:#90EE90,stroke:#333,stroke-width:2px
    style P_VERIFY fill:#90EE90,stroke:#333,stroke-width:2px
    style P_NOTES fill:#90EE90,stroke:#333,stroke-width:2px
    style P_TAGS fill:#90EE90,stroke:#333,stroke-width:2px

    style PO_GIT fill:#90EE90,stroke:#333,stroke-width:2px
    style PO_TIME fill:#90EE90,stroke:#333,stroke-width:2px
    style PO_ENV fill:#90EE90,stroke:#333,stroke-width:2px
    style PO_FS_TEMP fill:#90EE90,stroke:#333,stroke-width:2px
    style PO_LOGGER fill:#90EE90,stroke:#333,stroke-width:2px
    style PO_METRICS fill:#90EE90,stroke:#333,stroke-width:2px
    style PO_SIGNER fill:#90EE90,stroke:#333,stroke-width:2px

    style A fill:#FFDAB9,stroke:#333,stroke-width:2px
    style B fill:#FFDAB9,stroke:#333,stroke-width:2px
    style C fill:#FFDAB9,stroke:#333,stroke-width:2px
    style D fill:#FFDAB9,stroke:#333,stroke-width:2px
    style E fill:#FFDAB9,stroke:#333,stroke-width:2px
    style F fill:#FFDAB9,stroke:#333,stroke-width:2px

    style AL fill:#ADD8E6,stroke:#333,stroke-width:2px
    style DL_JOURNAL fill:#B0E0E6,stroke:#333,stroke-width:2px
    style DL_POLICY fill:#B0E0E6,stroke:#333,stroke-width:2px
    style DL_TRUST fill:#B0E0E6,stroke:#333,stroke-width:2px
    style DL_CACHE_CORE fill:#B0E0E6,stroke:#333,stroke-width:2px
    style DL_VERIFICATION fill:#B0E0E6,stroke:#333,stroke-width:2px

    style PL_ENCODER fill:#FFE4B5,stroke:#333,stroke-width:2px
    style PL_INDEXER fill:#FFE4B5,stroke:#333,stroke-width:2px
```

```mermaid
graph LR
    subgraph "Clients"
        A["CLI Tool (e.g., git-ledger)"]
        B["Higher-Level App (e.g., git-mind)"]
        C["Language Bindings (Go, JS, Python)"]
    end

    subgraph "libgitledger Library"
        LGL(libgitledger)
    end

    subgraph "Core External Dependencies"
        D[libgit2 Library]
        E[Filesystem / POSIX]
        F[Standard I/O / System Logger]
        G[Environment Variables]
        H["Metrics System (e.g., Prometheus)"]
        I["Cryptographic Backend (GPGME / SSH Agent)"]
    end

    A -- "Uses Public C API" --> LGL
    B -- "Uses Public C API" --> LGL
    C -- "Uses Public C API" --> LGL

    LGL -- "Interacts with" --> D
    LGL -- "Interacts with" --> E
    LGL -- "Interacts with" --> F
    LGL -- "Interacts with" --> G
    LGL -- "Interacts with" --> H
    LGL -- "Interacts with" --> I

    style LGL fill:#B0E0E6,stroke:#333,stroke-width:2px
    style A fill:#ADD8E6,stroke:#333,stroke-width:2px
    style B fill:#ADD8E6,stroke:#333,stroke-width:2px
    style C fill:#ADD8E6,stroke:#333,stroke-width:2px
    style D fill:#FFFACD,stroke:#333,stroke-width:2px
    style E fill:#FFFACD,stroke:#333,stroke-width:2px
    style F fill:#FFFACD,stroke:#333,stroke-width:2px
    style G fill:#FFFACD,stroke:#333,stroke-width:2px
    style H fill:#FFFACD,stroke:#333,stroke-width:2px
    style I fill:#FFFACD,stroke:#333,stroke-width:2px
```

```mermaid
graph TD
    subgraph "libgitledger Library"
        subgraph "External World (View from within libgitledger)"
            CL["Client (CLI, App, Bindings)"]
            LG2(libgit2)
            POS("POSIX/FS")
            S_LOG(System Logger)
            S_ENV(System Env)
            S_MET(System Metrics)
            S_CRYPTO(System Crypto)
        end

        subgraph "Adapters (Concrete Technology Bindings)"
            A_GIT[libgit2_repo_adapter] --> LG2
            A_FS[posix_fs_adapter] --> POS
            A_LOG[stdio_logger_adapter] --> S_LOG
            A_ENV[env_adapter] --> S_ENV
            A_MET[metrics_adapter] --> S_MET
            A_SIGN[crypto_signer_adapter] --> S_CRYPTO
        end

        subgraph "Ports (Abstract Interfaces - C Vtables)"
            subgraph "Driving Ports (Public API Endpoints)"
                P_APP(Append Entry)
                P_QUERY(Query Ledger)
                P_MGMT(Policy/Trust/Cache/Verify)
            end
            subgraph "Driven Ports (External Resource Needs)"
                P_GIT(git_repo_port)
                P_FS(fs_temp_port)
                P_LOG(logger_port)
                P_ENV(env_port)
                P_TIME(time_port)
                P_MET(metrics_port)
                P_SIGN(signing_port)
            end
        end

        subgraph "Application Layer (Use Cases / Orchestration)"
            AL[Ledger Services: Handle Public API Calls, Orchestrate Domain Logic]
        end

        subgraph "Domain Layer (Pure C Business Logic)"
            DC_JOURNAL[Journal Core: Entries, Commit Plans]
            DC_POLICY[Policy Logic: Rules, Enforcement]
            DC_TRUST[Trust Logic: Multi-Sig, Keys]
            DC_CACHE[Cache Core: Roaring Bitmaps, Indexing]
            DC_VERIFY[Verification Logic: Chain, Signatures]
            PL_ENC(Pluggable Encoder)
            PL_IDX(Pluggable Indexer)
        end
    end

    CL --> P_APP
    CL --> P_QUERY
    CL --> P_MGMT

    P_APP --> AL
    P_QUERY --> AL
    P_MGMT --> AL

    AL -- "orchestrates" --> DC_JOURNAL
    AL -- "enforces" --> DC_POLICY
    AL -- "validates" --> DC_TRUST
    AL -- "manages" --> DC_CACHE
    AL -- "uses" --> DC_VERIFY
    AL -- "uses" --> PL_ENC
    AL -- "uses" --> PL_IDX

    DC_JOURNAL -- "needs" --> P_GIT
    DC_POLICY -- "needs" --> P_GIT
    DC_TRUST -- "needs" --> P_GIT
    DC_CACHE -- "needs" --> P_GIT
    DC_CACHE -- "needs" --> P_FS
    DC_VERIFY -- "needs" --> P_GIT
    DC_VERIFY -- "needs" --> P_SIGN

    AL -- "utilizes" --> P_LOG
    AL -- "utilizes" --> P_ENV
    AL -- "utilizes" --> P_TIME
    AL -- "utilizes" --> P_MET

    P_GIT -- "implemented by" --> A_GIT
    P_FS -- "implemented by" --> A_FS
    P_LOG -- "implemented by" --> A_LOG
    P_ENV -- "implemented by" --> A_ENV
    P_TIME -- "implemented by" --> A_FS
    P_MET -- "implemented by" --> A_MET
    P_SIGN -- "implemented by" --> A_SIGN

    style LGL fill:white,stroke:#333,stroke-width:2px
    style CL fill:#ADD8E6,stroke:#333,stroke-width:2px
    style LG2 fill:#FFFACD,stroke:#333,stroke-width:2px
    style POS fill:#FFFACD,stroke:#333,stroke-width:2px
    style S_LOG fill:#FFFACD,stroke:#333,stroke-width:2px
    style S_ENV fill:#FFFACD,stroke:#333,stroke-width:2px
    style S_MET fill:#FFFACD,stroke:#333,stroke-width:2px
    style S_CRYPTO fill:#FFFACD,stroke:#333,stroke-width:2px

    style A_GIT fill:#FFDAB9,stroke:#333,stroke-width:2px
    style A_FS fill:#FFDAB9,stroke:#333,stroke-width:2px
    style A_LOG fill:#FFDAB9,stroke:#333,stroke-width:2px
    style A_ENV fill:#FFDAB9,stroke:#333,stroke-width:2px
    style A_MET fill:#FFDAB9,stroke:#333,stroke-width:2px
    style A_SIGN fill:#FFDAB9,stroke:#333,stroke-width:2px

    style P_APP fill:#90EE90,stroke:#333,stroke-width:2px
    style P_QUERY fill:#90EE90,stroke:#333,stroke-width:2px
    style P_MGMT fill:#90EE90,stroke:#333,stroke-width:2px
    style P_GIT fill:#90EE90,stroke:#333,stroke-width:2px
    style P_FS fill:#90EE90,stroke:#333,stroke-width:2px
    style P_LOG fill:#90EE90,stroke:#333,stroke-width:2px
    style P_ENV fill:#90EE90,stroke:#333,stroke-width:2px
    style P_TIME fill:#90EE90,stroke:#333,stroke-width:2px
    style P_MET fill:#90EE90,stroke:#333,stroke-width:2px
    style P_SIGN fill:#90EE90,stroke:#333,stroke-width:2px

    style AL fill:#ADD8E6,stroke:#333,stroke-width:2px
    style DC_JOURNAL fill:#B0E0E6,stroke:#333,stroke-width:2px
    style DC_POLICY fill:#B0E0E6,stroke:#333,stroke-width:2px
    style DC_TRUST fill:#B0E0E6,stroke:#333,stroke-width:2px
    style DC_CACHE fill:#B0E0E6,stroke:#333,stroke-width:2px
    style DC_VERIFY fill:#B0E0E6,stroke:#333,stroke-width:2px
    style PL_ENC fill:#FFE4B5,stroke:#333,stroke-width:2px
    style PL_IDX fill:#FFE4B5,stroke:#333,stroke-width:2px
```

```mermaid
sequenceDiagram
    participant Client
    participant Public_API as gitledger_append()
    participant App_Services as Application Services
    participant Policy_Trust as Policy & Trust Domain
    participant Journal_Core as Journal Domain
    participant Pluggable_Encoder as Encoder V1
    participant Git_Repo_Port as git_repo_port
    participant libgit2_Adapter as libgit2 Adapter
    participant libgit2 as libgit2 Library

    Client->>Public_API: gitledger_append(payload, encoder, ...)
    Public_API->>App_Services: Call App Service for Append
    App_Services->>Pluggable_Encoder: encode(payload)
    Pluggable_Encoder-->>App_Services: commit_message_bytes
    App_Services->>Git_Repo_Port: get_latest_journal_oid()
    Git_Repo_Port->>libgit2_Adapter: get_ref_target("refs/gitledger/journal/...")
    libgit2_Adapter->>libgit2: git_reference_lookup(), git_reference_target()
    libgit2-->>libgit2_Adapter: current_HEAD_oid
    libgit2_Adapter-->>Git_Repo_Port: current_HEAD_oid
    Git_Repo_Port-->>App_Services: current_HEAD_oid

    App_Services->>Journal_Core: build_commit_plan(commit_msg_bytes, current_HEAD_oid)
    Journal_Core-->>App_Services: commit_plan (new_commit_oid)

    App_Services->>Policy_Trust: enforce_policy_for_append(commit_plan, require_sign)
    Policy_Trust->>Git_Repo_Port: read_policy_ref(), read_trust_ref()
    Git_Repo_Port->>libgit2_Adapter: git_reference_lookup(), git_blob_lookup()
    libgit2_Adapter-->>Git_Repo_Port: policy_json, trust_json
    Git_Repo_Port-->>Policy_Trust: policy_json, trust_json
    Policy_Trust->>Policy_Trust: Check signatures, authors, size, etc.
    Policy_Trust-->>App_Services: GL_OK (or GL_ERR_POLICY/TRUST)

    App_Services->>Git_Repo_Port: execute_commit_plan(commit_plan)
    Git_Repo_Port->>libgit2_Adapter: create_commit(), update_ref_fastforward()
    libgit2_Adapter->>libgit2: git_commit_create(), git_reference_update_head()
    libgit2-->>libgit2_Adapter: success/conflict
    libgit2_Adapter-->>Git_Repo_Port: success/conflict (new_commit_oid)
    Git_Repo_Port-->>App_Services: new_commit_oid

    App_Services-->>Public_API: new_commit_oid
    Public_API-->>Client: new_commit_oid (GL_OK)
```

#### Domain Core

Pure C types & logic

- entries
- chain rules
- verification
- commit “plan” building

#### Ports (interfaces)

- `git_repo_port` (read/write objects/refs; notes; tags; signature extraction)
- `time_port`, `env_port`, `fs_temp_port`, `logger_port`, `metrics_port`, `signing_port` (optional)

#### Adapters

- `libgit2` adapter implements `git_repo_port`.
- `stdio` logger; `null` metrics; POSIX `temp-fs`, etc.

This mirrors `git-mind`’s pattern exactly, making unit tests trivial and adapters swappable. ￼

### 5.2 Memory & Logging

- **Pluggable allocator**: `gitledger_allocator_t` with user hooks; defaults to `malloc`/`free`.
- **Pluggable logger**: categories + levels, shipped stdio adapter.
- **Structured errors**: result + error types; error stacks. (Inspired by `gm_result_t`) ￼

---

## VI. Public C API (sketch)

**Header namespace**: `include/gitledger/…` with `gitledger.h` umbrella.

```c
#ifdef __cplusplus

extern "C" {

#endif

/* --- Opaque handles --- */

typedef struct gitledger_ctx gitledger_ctx_t;

typedef struct gitledger_ledger gitledger_ledger_t;

typedef struct gitledger_error gitledger_error_t;

typedef struct gitledger_iter gitledger_iter_t;

/* --- Basic types --- */

typedef enum {

GL_OK = 0, GL_ERR_IO, GL_ERR_GIT, GL_ERR_POLICY, GL_ERR_TRUST,

GL_ERR_NOT_FOUND, GL_ERR_CONFLICT, GL_ERR_INVALID, GL_ERR_NOSIG,

GL_ERR_UNSUPPORTED, GL_ERR_OOM, GL_ERR_INTERNAL

} gitledger_code_t;

typedef struct {

void *(*malloc_fn)(size_t);

void *(*realloc_fn)(void*, size_t);

void (*free_fn)(void*);

} gitledger_allocator_t;

typedef void (*gitledger_log_fn)(int level, const char *domain, const char *msg);

/* --- Encoders & Indexers --- */

typedef struct {

/* Input: user payload blob; Output: commit message bytes (NUL not required). */

int (*encode)(const void *payload, size_t payload_len,

char **out_msg, size_t *out_msg_len, gitledger_error_t **err);

} gitledger_encoder_v1_t;

typedef struct {

/* Output: array of "term" strings (e.g., "service:api", "status:ok"). */

int (*terms_for_payload)(const char *commit_msg, size_t msg_len,

char ***out_terms, size_t *out_term_count,

gitledger_error_t **err);

} gitledger_indexer_v1_t;

/* --- Init/Config --- */

int gitledger_init(gitledger_ctx_t **out, gitledger_error_t **err);

int gitledger_shutdown(gitledger_ctx_t *ctx);

int gitledger_set_allocator(gitledger_ctx_t *ctx, const gitledger_allocator_t *a);

int gitledger_set_logger(gitledger_ctx_t *ctx, gitledger_log_fn fn);

/* --- Ledger lifecycle --- */

int gitledger_ledger_open(gitledger_ctx_t *ctx, const char *repo_path,

const char *ledger_name, gitledger_ledger_t **out,

gitledger_error_t **err);

int gitledger_ledger_close(gitledger_ledger_t *L);

/* --- Append / Read --- */

int gitledger_append(gitledger_ledger_t *L,

const void *payload, size_t payload_len,

const gitledger_encoder_v1_t *enc,

int require_sign, /* policy default if -1 */

char /* oid[41] */ out_oid_hex[41],

gitledger_error_t **err);

int gitledger_get_latest_entry(gitledger_ledger_t *L,

char out_oid_hex[41], gitledger_error_t **err);

int gitledger_get_entry_message(gitledger_ledger_t *L, const char *oid_hex,

char **out_msg, size_t *out_len, gitledger_error_t **err);

/* --- Notes / Tags --- */

int gitledger_attach_note(gitledger_ledger_t *L, const char *oid_hex,

const void *note, size_t note_len,

gitledger_error_t **err);

int gitledger_tag_associate(gitledger_ledger_t *L, const char *tag_name,

const char *entry_oid_hex, gitledger_error_t **err);

/* --- Policy & Trust --- */

int gitledger_policy_get(gitledger_ledger_t *L, char **json, size_t *len, gitledger_error_t **err);

int gitledger_policy_set(gitledger_ledger_t *L, const char *json, size_t len, gitledger_error_t **err);

int gitledger_trust_get(gitledger_ledger_t *L, char **json, size_t *len, gitledger_error_t **err);

int gitledger_trust_set(gitledger_ledger_t *L, const char *json, size_t len, gitledger_error_t **err);

/* --- Cache & Query (roaring) --- */

int gitledger_cache_rebuild(gitledger_ledger_t *L, const gitledger_indexer_v1_t *indexer,

gitledger_error_t **err);

int gitledger_query_terms(gitledger_ledger_t *L, /* e.g., ["service:api","+author:j","-status:fail"] */

const char **terms, size_t nterms,

gitledger_iter_t **out_iter, gitledger_error_t **err);

int gitledger_iter_next(gitledger_iter_t *it, char out_oid_hex[41]);

int gitledger_iter_free(gitledger_iter_t *it);

/* --- Verify / Errors --- */

int gitledger_verify_ledger_integrity(gitledger_ledger_t *L, int deep, gitledger_error_t **err);

const char *gitledger_error_str(const gitledger_error_t *err);

void gitledger_error_free(gitledger_error_t *err);

#ifdef __cplusplus

}

#endif
```

**Notes:**

- Encoders return bytes; we do not force UTF-8. Git will store the bytes; use textual encodings (e.g., JSON + trailers; base64-CBOR) when needed. (Matches `shiplog`/`git-mind` styles.)
- Policy/Trust are JSON; the library enforces them during `append()` and on `verify_ledger_integrity()`. (Shiplog precedent.) ￼
- Tag association uses notes on tag objects under `refs/gitledger/tag_notes`. ￼

---

## VII. Policy & Trust (built-in)

### Policy as Code (per-ledger)

`policy.json` under `refs/gitledger/policy/<L>` with keys like:

- `require_signed: bool | "attestation" | "commit"`
- `allowed_authors: [emails]` (author allow-list)
- `allowed_encoders: [ids]` (optional)
- `max_entry_size_bytes`
- `push_protection: { server_enforced: bool }`

Enforced at append and verify time. Mirrors `shiplog`’s model, generalized for any ledger. ￼

### Multi-Signature Trust

`trust.json` under `refs/gitledger/trust/<L>` including:

- `maintainers: [{id, email, key_fingerprint}]`
- `threshold: N` (N-of-M approvals for trust changes)
- `signature_mode: "chain" | "attestation"`
- `allowed_signers: [...]`

Library verifies signatures of entries against current trust + policy; updates to `trust.json` themselves require quorum signatures. (Same governance pattern you already run.) ￼

### Signatures

- **Chain** = signed commit.
- **Attestation** = detached SSH/GPG signature note co-stored and linked.

Verification uses `libgit2` extraction + pluggable verification backend (GPGME/SSH sig adapter), defaulting to “present + fingerprint match” until crypto adapter is configured.

---

## VIII. Indexing & Querying

### Indexing

Indexer callback parses payload format and emits “terms” (`key:value`).

### Querying

Library builds roaring bitmaps: one bitmap per term; entry IDs are ordinal positions in the ledger chain.

Queries are boolean set ops over bitmaps (`AND`/`OR`/`NOT`). Cache is rebuildable from journal. This mirrors git-mind’s fast query path. ￼

Query API accepts a term array with leading operator shorthands (`+` for **MUST**, `-` for **MUST_NOT**). Result is an iterator of matching entry OIDs.

---

## IX. Concurrency, Atomicity, & Integrity

- **Append is optimistic**: we read `HEAD_oid`, create a commit object, then try to fast-forward `refs/gitledger/journal/<L>` from `HEAD_oid` → `new_oid`. If the ref moved, return `GL_ERR_CONFLICT` so the caller retries after reloading latest.
- **Integrity audit**: linear parent chain check, ref integrity, optional BLAKE3 checksums on ref tips. (You flagged this as “self-audit hooks.”) ￼

---

## X. Directory Layout (library repo)

```bash
libgitledger/
├─ include/gitledger/ # public headers
├─ core/domain/ # pure ledger logic
├─ core/ports/ # abstract ports (git, fs, logger, signer, etc.)
├─ core/adapters/libgit2/ # git adapter impl
├─ core/cache/ # roaring integration
├─ core/policy_trust/ # policy & trust logic
├─ adapters/ # logger/fs/env/signing adapters
├─ tests/ # unit + integration
└─ cli/ # 'git-ledger' demo tool
```

This is aligned to the hexagonal structure used in [git-mind](https://github.com/neuroglyph/git-mind).

---

## XI. Security Considerations

- No shell `exec` in core; signing/verification uses pluggable crypto adapters.
- Key material never stored by lib; only fingerprints/IDs in trust docs.
- Policy default-deny if document missing (configurable).
- Replay protection via append-only + trust verification; server-side hooks recommended (`pre-receive`) — pattern borrowed from `shiplog`. ￼

---

## XII. Bindings & ABI

- Stable C ABI (opaque handles; no inline structs in public headers).
- No global state; all config on a context or ledger handle.
- Bindings can map errors to idiomatic exceptions/results (Go, JS, Python).
- Threading: ledger handles are not thread-safe; concurrent reads via separate handles; concurrent appends require higher-level retry.

---

## XIII. Error API

Errors are represented by opaque `gitledger_error_t` structures. Creation helpers capture the source
location and attach optional causes, producing a causal chain that callers can walk with
`gitledger_error_walk` without recursion. Each error records:

- `domain` (`gitledger_domain_t`) and `code` (`gitledger_code_t`) — numerical values are frozen.
- `flags` (`GL_ERRFLAG_RETRYABLE`, `GL_ERRFLAG_PERMANENT`, `GL_ERRFLAG_AUTH`).
- A UTF-8 message allocated via the context allocator.
- Optional source file, line, function.
- Optional cause (retained, released via reference counting).

Creation entry points come in two layers:

- `gitledger_error_create_ctx_loc_v` / `_with_cause_ctx_loc_v` accept an explicit
  `gitledger_source_location_t` and a `va_list`; they never allocate internal temporaries and are
  safe for bindings that already captured formatting arguments.
- `GITLEDGER_ERROR_CREATE` / `GITLEDGER_ERROR_WITH_CAUSE` are inline helpers that forward to the
  above, automatically capturing `__FILE__`, `__LINE__`, and `__func__`, and they work even when no
  variadic arguments are supplied.

Default guidance per domain/code:

| Domain | Example Codes | Flags | Guidance |
|--------|----------------|-------|----------|
| `GL_DOMAIN_GIT` | `GL_CODE_NOT_FOUND`, `GL_CODE_CONFLICT` | none | Inspect code and decide retry. |
| `GL_DOMAIN_POLICY` | `GL_CODE_POLICY_VIOLATION` | `PERMANENT` | Do not retry automatically; surface policy result. |
| `GL_DOMAIN_TRUST` | `GL_CODE_TRUST_VIOLATION` | `PERMANENT`, `AUTH` | Require credential / trust escalation. |
| `GL_DOMAIN_IO` | `GL_CODE_IO_ERROR` | `RETRYABLE` | Retry with backoff. |

`gitledger_error_render_json` returns the exact byte count (including the terminating NUL) required
to encode the full causal chain as deterministic JSON. Rendering is iterative, capped by
`GITLEDGER_ERROR_MAX_DEPTH`, and emits `"truncated":true` when the chain exceeds that limit.
`gitledger_error_json` memoises the JSON in a context-owned scratch buffer so repeated logging does not
re-render; `gitledger_error_json_copy` duplicates it for callers that need the data to outlive the
context. Messages are treated the same way via `gitledger_error_message_copy`. Domain / code / flag
strings are available through `gitledger_domain_name`, `gitledger_code_name`, and
`gitledger_error_flags_format` for bindings that want symbolic names.

Errors are reference counted; contexts track all outstanding errors and free them during teardown.
`gitledger_error_release` descends iteratively (no recursion) so deeply nested causal stacks cannot
overflow a thread’s call stack. Callers can opt into shared ownership via `gitledger_error_retain`
when an error must outlive the originating context.

---

## XIV. Testing Strategy (global)

- Unit tests on domain (no Git), using fake ports (pure hexagonal advantage). ￼
- Adapter tests against `libgit2` with ephemeral repos.
- Integration tests covering policy/trust/signing, notes, tag association, cache rebuild + queries.
- Property tests (fuzz payloads, malformed policy/trust).
- CI in Docker matrix; protect the local repo (shiplog’s discipline carried over). ￼
