# Issues Overview

## Existing Issues

| issue title | issue id | roadmap area | roadmap milestone | remarks | fate |
|---|---:|---|---|---|---|
| [M2] Minimal Linux CRT shim (_start) and freestanding CI job | 47 | Hardening and portability | M2 |  | Keep |
| End-to-end tests | 39 | Backlog | M7 |  | Split |
| Documentation and examples | 38 | Backlog | M7 |  | Keep |
| BLAKE3 checksum option | 37 | Backlog | M7 |  | Keep |
| Deep verify | 36 | Backlog | M7 |  | Split |
| Query integration tests | 35 | Backlog | M6 |  | Keep |
| CLI query commands | 34 | Backlog | M6 |  | Keep |
| Query engine | 33 | Backlog | M6 |  | Split |
| Cache writer | 32 | Backlog | M6 |  | Keep |
| CRoaring integration | 31 | Backlog | M6 |  | Keep |
| Indexer interface | 30 | Backlog | M6 |  | Keep |
| Notes and tags integration tests | 29 | Backlog | M5 |  | Keep |
| CLI enhancements | 28 | Backlog | M5 |  | Keep |
| Tag association | 27 | Backlog | M5 |  | Keep |
| Notes API | 26 | Backlog | M5 |  | Keep |
| Threshold enforcement | 25 | Backlog | M4 |  | Keep |
| Attestation support | 24 | Backlog | M4 |  | Keep |
| Commit signature validation | 23 | Backlog | M4 |  | Keep |
| Signature port | 22 | Backlog | M4 |  | Keep |
| Trust document storage | 21 | Backlog | M4 |  | Keep |
| Policy enforcement tests | 20 | Backlog | M3 |  | Keep |
| Append enforcement | 19 | Backlog | M3 |  | Keep |
| Author identity port | 18 | Backlog | M3 |  | Keep |
| Policy parser | 17 | Backlog | M3 |  | Keep |
| Policy document storage | 16 | Backlog | M3 |  | Keep |
| Append/read integration tests | 15 | Backlog | M2 |  | Keep |
| Read path | 14 | Backlog | M2 |  | Keep |
| Append path | 13 | Backlog | M2 |  | Keep |
| Ledger lifecycle | 12 | Backlog | M2 |  | Keep |
| libgit2 adapter | 11 | Backlog | M2 |  | Keep |
| Git repo port interface | 10 | Backlog | M2 |  | Keep |
| Context lifecycle | 9 | Backlog | M1 |  | Keep |
| Logger hooks | 8 | Backlog | M1 |  | Keep |
| Allocator hooks | 7 | Backlog | M1 |  | Keep |
| Error API | 6 | Backlog | M1 |  | Keep |
| Coding standards | 5 | Backlog | M0 |  | Keep |
| CI scaffolding | 4 | Backlog | M0 |  | Keep |
| Dependency placeholders | 3 | Backlog | M0 |  | Keep |
| Dual build system bootstrap | 2 | Backlog | M0 |  | Keep |
| Scaffold repo layout | 1 | Backlog | M0 |  | Keep |


## M3

| Issue Title | Issue Id | Roadmap Area | Remarks |
|---|---:|---|---|
| [M3] Public API v0.1 docs + visibility | 50 | Solidify core | Parent feature; header export audit + docs artifact |
| [M3][API] Add Doxygen config + CMake target | 51 | Solidify core | — |
| [M3][API] Annotate public headers with brief/group | 52 | Solidify core | — |
| [M3][API] CI job: build + upload API docs artifact | 53 | Hardening and portability | — |
| [M3] CLI scaffold + examples | 54 | Make it useful | Parent feature; minimal CLI with examples |
| [M3][CLI] Subcommand framework + help | 55 | Make it useful | — |
| [M3][CLI] Implement 'version' command | 56 | Make it useful | — |
| [M3][CLI] Implement 'error-demo' command | 57 | Make it useful | — |
| [M3] Windows DLL export audit + shared build CI | 58 | Hardening and portability | Ensure exports, run tests on windows-latest |

## M4

| Issue Title | Issue Id | Roadmap Area | Remarks |
|---|---:|---|---|
| [M4] Fuzzing harness for errors/version | 59 | Prove integrity | libFuzzer targets for error JSON and snprintf |
| [M4] libgit2 adapter (read-only) skeleton | 60 | Solidify core | Adapter interface + open/list objects |

## M5

| Issue Title | Issue Id | Roadmap Area | Remarks |
|---|---:|---|---|
| [M5] Symbol-policy guard for archives (cross-platform) | 61 | Hardening and portability | Deny/allow enforcement for lib archives on all OSes |

## M3

| Issue Title | Issue Id | Roadmap Area | Remarks |
|---|---:|---|---|
| [M3][Win] Audit GITLEDGER_API exports for DLL | 62 | Hardening and portability | Confirm only intended symbols exported |
| [M3][Win] Add MSVC shared build + test job | 63 | Hardening and portability | Add Windows shared build to CI and run tests |
| [M3][Win] Fix printf/PRIuMAX and headers for MSVC | 64 | Hardening and portability | Ensure MSVC-safe format macros and headers |

## M4

| Issue Title | Issue Id | Roadmap Area | Remarks |
|---|---:|---|---|
| [M4][Fuzz] error_json fuzzer | 65 | Prove integrity | libFuzzer target for error JSON |
| [M4][Fuzz] version_snprintf fuzzer | 66 | Prove integrity | libFuzzer target for version snprintf |
| [M4][Fuzz] CI lane (10s per target) | 67 | Hardening and portability | Optional short-budget fuzzing lane |
| [M4][git2] Define adapter interface header | 68 | Solidify core | Introduce adapter abstraction and flag |
| [M4][git2] Implement open repository + fixtures | 69 | Solidify core | Add open_repo() and seed tiny repo |
| [M4][git2] List commits (iterator) | 70 | Solidify core | Iterator returns minimal commit rows |

## M5

| Issue Title | Issue Id | Roadmap Area | Remarks |
|---|---:|---|---|
| [M5][sym] Linux archive policy (nm) | 71 | Hardening and portability | Enforce allow/deny on .a via nm/objdump |
| [M5][sym] macOS archive policy (nm -U) | 72 | Hardening and portability | Enforce allow/deny on .a via nm -U |
| [M5][sym] Windows archive policy (.lib) | 73 | Hardening and portability | Enforce allow/deny on .lib via dumpbin/llvm-nm |
