# Corrected Execution Roadmap

> **Purpose**: This roadmap organizes work by **true dependencies** and **execution phases** (antichains), not feature milestones.
>
> **Key Changes from Original**:
> - ✅ No dependency cycles
> - ✅ Complete dependency graph (80 edges vs original 28)
> - ✅ Grouped by execution waves (what can run in parallel)
> - ✅ Realistic team sizing and timelines

---

## Executive Summary

| Metric | Value |
|--------|-------|
| **Total Duration** | 26 weeks (~6.5 months) |
| **Team Size** | 2-4 FTE (varies by phase) |
| **Total Effort** | 72 person-weeks |
| **Critical Path** | Foundation → Git Adapter → Crypto → Operations → Indexing |
| **Parallelization Efficiency** | 2.8x (72 person-weeks / 26 calendar weeks) |

---

## Phase 1: Foundation & Tooling (3 weeks)

**Team Size:** 3 FTE
**Critical Path:** Error API → Context lifecycle

### Core Systems Team (2 FTE)
*Skills: Systems programming, API design*

- **N6**: Error API (2 weeks)
  - Reference-counted error objects
  - Causal chain tracking
  - JSON rendering
  - **⚠️ CRITICAL PATH**: Everything depends on this

- **N7**: Allocator hooks (1 week)
  - Pluggable allocator interface
  - Default malloc/free implementation

- **N8**: Logger hooks (1 week)
  - Log levels and categories
  - Stdio adapter

- **N9**: Context lifecycle (1 week)
  - **Depends on**: N6, N7, N8
  - Initialization and teardown
  - Reference counting for contexts

### DevOps/Tooling Team (1 FTE)
*Skills: Build systems, CI/CD*

- **N4**: CI scaffolding (0.5 weeks) ✅ *Mostly complete*
- **N47**: Minimal Linux CRT shim (1 week)
- **N51**: Add Doxygen config + CMake target (0.5 weeks)
- **N31**: CRoaring integration (1 week)
- **N37**: BLAKE3 checksum option (0.5 weeks)

**Rationale**: Foundation must be solid. Error handling and context are the base for everything else. Tooling work can proceed in parallel.

---

## Phase 2: Interfaces & Platform (2 weeks)

**Team Size:** 3.5 FTE
**Parallelization**: High - all interface definitions can proceed simultaneously

### Core Systems Team (2 FTE)

- **N10**: Git repo port interface (1 week)
  - **Depends on**: N9
  - Abstract interface for Git operations
  - Vtable design for adapters

- **N17**: Policy parser (1 week)
  - **Depends on**: N9
  - JSON schema for policy documents
  - Strict validation

- **N18**: Author identity port (0.5 weeks)
  - **Depends on**: N9
  - Environment variable capture

- **N30**: Indexer interface (1 week)
  - **Depends on**: N9
  - Abstract interface for term extraction

- **N50**: Public API v0.1 docs + visibility (1 week)
  - **Depends on**: N9
  - API stability guarantees
  - Export visibility audit

### Platform Team (1 FTE)

- **N52**: Annotate public headers (1 week)
  - **Depends on**: N51
  - Doxygen comments

- **N53**: CI job: build + upload API docs artifact (1 week)
  - **Depends on**: N51, N52

- **N58**: Windows DLL export audit (1 week)
  - **Depends on**: N9

- **N61**: Symbol-policy guard (1 week)
  - **Depends on**: N9
  - Cross-platform archive inspection

- **N62**: Audit GITLEDGER_API exports (0.5 weeks)
  - **Depends on**: N9

- **N64**: Fix printf/PRIuMAX for MSVC (0.5 weeks)
  - **Depends on**: N9

### Security Team (0.5 FTE, part-time)

- **N22**: Signature port (1 week)
  - **Depends on**: N9
  - Abstract interface for crypto operations

- **N59**: Fuzzing harness (1 week)
  - **Depends on**: N9
  - libFuzzer integration

**Rationale**: Define all interfaces *before* implementing them. This prevents rework and enables parallel development in later phases.

---

## Phase 3: Git Adapter (4 weeks) ⚠️ CRITICAL PATH

**Team Size:** 4 FTE
**Bottleneck**: Git adapter is the critical dependency for all ledger operations

### Core Systems Team (2 FTE)

- **N11**: libgit2 adapter (3 weeks)
  - **Depends on**: N10
  - **⚠️ CRITICAL**: Everything depends on this
  - Implement git_repo_port using libgit2
  - Object reads, ref updates, notes API
  - Fast-forward enforcement

- **N68**: Define adapter interface header (0.5 weeks)
  - **Depends on**: N10
  - Extended adapter capabilities

### CLI Team (1 FTE)

- **N54**: CLI scaffold (1 week)
  - **Depends on**: N9

- **N55**: Subcommand framework + help (1 week)
  - **Depends on**: N54

- **N56**: Implement 'version' command (0.5 weeks)
  - **Depends on**: N55

- **N57**: Implement 'error-demo' command (0.5 weeks)
  - **Depends on**: N55

### Platform Team (1 FTE)

- **N63**: Add MSVC shared build + test job (1 week)
  - **Depends on**: N62

- **N65**: error_json fuzzer (0.5 weeks)
  - **Depends on**: N59

- **N66**: version_snprintf fuzzer (0.5 weeks)
  - **Depends on**: N59

- **N67**: CI fuzzing lane (1 week)
  - **Depends on**: N65, N66

- **N71**: Linux archive policy (0.5 weeks)
  - **Depends on**: N61

- **N72**: macOS archive policy (0.5 weeks)
  - **Depends on**: N61

- **N73**: Windows archive policy (0.5 weeks)
  - **Depends on**: N61

**Rationale**: The git adapter is the single biggest blocker. Get it done right with 2 senior engineers. CLI and platform work proceeds in parallel to maximize throughput.

---

## Phase 4: Core Features & Crypto (5 weeks)

**Team Size:** 3 FTE
**Parallel Streams**: Storage operations + signature validation

### Core Systems Team (2 FTE)

- **N12**: Ledger lifecycle (2 weeks)
  - **Depends on**: N9, N11
  - Open/close operations
  - Create ledger refs

- **N16**: Policy document storage (1 week)
  - **Depends on**: N11
  - Store policy JSON in Git

- **N21**: Trust document storage (1 week)
  - **Depends on**: N11
  - Store trust JSON in Git

- **N60**: libgit2 adapter extended (2 weeks)
  - **Depends on**: N11
  - Read-only skeleton

- **N69**: Implement open repository + fixtures (1 week)
  - **Depends on**: N60, N68
  - Test fixtures

### Security Team (1 FTE)

- **N23**: Commit signature validation (3 weeks)
  - **Depends on**: N22, N11
  - **⚠️ HARD**: Crypto integration
  - GPG/SSH signature extraction
  - Verification logic
  - As-of semantics for key rotation

**Rationale**: Storage operations and crypto validation can proceed in parallel. Allocate a dedicated security engineer for signature work (it's complex).

---

## Phase 5: Operations & Advanced Features (4 weeks)

**Team Size:** 3 FTE
**Unlocks**: End-user functionality (append/read)

### Core Systems Team (2 FTE)

- **N13**: Append path (2 weeks)
  - **Depends on**: N12
  - **Major milestone**: Users can write to ledger
  - Optimistic locking
  - Conflict detection

- **N14**: Read path (1 week)
  - **Depends on**: N12
  - Entry retrieval
  - Message decoding

- **N26**: Notes API (1.5 weeks)
  - **Depends on**: N11, N12
  - Attach artifacts to entries

- **N27**: Tag association (1.5 weeks)
  - **Depends on**: N11, N12
  - Link tags to entries

- **N70**: List commits (iterator) (1 week)
  - **Depends on**: N69
  - Commit traversal

### Security Team (1 FTE)

- **N24**: Attestation support (2 weeks)
  - **Depends on**: N23
  - Detached signatures
  - Note-based attestations

- **N25**: Threshold enforcement (2 weeks)
  - **Depends on**: N21, N17, N16
  - N-of-M signature verification
  - Trust updates require quorum

**Rationale**: Append/read are major user-facing milestones. Attestation work continues in parallel.

---

## Phase 6: Integration & Indexing (5 weeks)

**Team Size:** 4 FTE
**High Complexity**: Cache writer and query engine are the hardest technical challenges

### Core Systems Team (2 FTE)

- **N32**: Cache writer (3 weeks)
  - **Depends on**: N30, N31, N14
  - **⚠️ COMPLEX**: Roaring bitmap serialization
  - Ordinal stability guarantees
  - Atomic cache updates

- **N33**: Query engine (3 weeks)
  - **Depends on**: N32
  - **⚠️ COMPLEX**: Boolean term evaluation
  - Bitmap operations (AND/OR/NOT)
  - Iterator interface

### Integration Team (1 FTE)

- **N15**: Append/read integration tests (1 week)
  - **Depends on**: N13, N14

- **N19**: Append enforcement (2 weeks)
  - **Depends on**: N13, N16, N17, N18
  - Policy checks during append

- **N29**: Notes/tags integration tests (1 week)
  - **Depends on**: N26, N27

- **N36**: Deep verify (2 weeks)
  - **Depends on**: N14, N23, N25
  - Full ledger integrity audit

### CLI Team (1 FTE)

- **N28**: CLI enhancements (1 week)
  - **Depends on**: N55, N26, N27
  - Commands for notes and tags

**Rationale**: Cache and query are the performance multipliers. Dedicate 2 engineers to get it right. Integration work proceeds in parallel.

---

## Phase 7: Query & Final Testing (3 weeks)

**Team Size:** 2 FTE
**Focus**: Polish and comprehensive testing

### Integration Team (2 FTE)

- **N20**: Policy enforcement tests (1 week)
  - **Depends on**: N19

- **N34**: CLI query commands (1 week)
  - **Depends on**: N33, N55
  - User-facing query interface

- **N35**: Query integration tests (1 week)
  - **Depends on**: N33
  - Boolean query correctness

- **N39**: End-to-end tests (2 weeks)
  - **Depends on**: N36, N33, N70
  - Full system validation

- **N38**: Documentation and examples (2 weeks)
  - **Depends on**: N15, N20, N29, N35
  - Sample encoders
  - Server-side hook examples
  - Tutorial documentation

**Rationale**: Final testing and documentation before release.

---

## Critical Path Analysis

**The longest dependency chain** (determines minimum project duration):

```
N6 (Error API) → N9 (Context) → N10 (Git port) → N11 (libgit2 adapter)
  → N12 (Ledger) → N13 (Append) → N19 (Enforcement) → N20 (Tests)

Alternative path through indexing:
... → N14 (Read) → N32 (Cache) → N33 (Query) → N39 (E2E tests)
```

**Critical path length**: ~16-18 weeks of serialized work

**Actual timeline**: 26 weeks (due to resource constraints and parallel streams)

---

## Team Composition

### Core Systems Team (2 FTE, full duration)
**Skills required:**
- C systems programming (memory management, no UB)
- Git internals (object model, refs, notes)
- Hexagonal architecture
- libgit2 API expertise (or learning curve)

### Security Team (1 FTE, Phases 2-5)
**Skills required:**
- Cryptographic signatures (GPG, SSH)
- Threat modeling
- Security testing
- Fuzzing

### Platform/DevOps Team (1 FTE, Phases 1-3)
**Skills required:**
- CMake + Meson
- Docker, CI/CD
- Cross-platform builds (Linux, macOS, Windows)
- Symbol visibility and linking

### CLI Team (1 FTE, Phases 3, 6-7)
**Skills required:**
- Command-line UX design
- Argument parsing
- User-facing documentation

### Integration/Test Team (1-2 FTE, Phases 6-7)
**Skills required:**
- Test design
- Integration testing
- Technical writing

---

## Comparison to Original Roadmap

| Aspect | Original | Corrected |
|--------|----------|-----------|
| **Timeline** | 25-40 days | 26 weeks (6.5 months) |
| **Realism** | Wildly optimistic | Conservative with buffer |
| **Dependencies** | 28 edges | 80 edges (complete) |
| **Cycles** | Yes (M3↔M4) | No (validated) |
| **Team size** | Unspecified | 2-4 FTE by phase |
| **Parallelization** | Unclear | 2.8x efficiency |
| **Critical path** | Not identified | Git adapter + crypto |

---

## Risk Mitigation

### Technical Risks

1. **Git adapter complexity**
   - *Mitigation*: Allocate 2 senior engineers, 4 weeks
   - *Fallback*: Reduce scope to read-only initially

2. **Signature verification**
   - *Mitigation*: Dedicated security engineer, 5 weeks total
   - *Fallback*: Ship with "signature present" checks only, defer crypto validation to 1.1

3. **Query engine performance**
   - *Mitigation*: 2 engineers, 3 weeks each for cache + query
   - *Fallback*: Ship without indexing in 1.0, add in 1.1

### Resource Risks

1. **Team availability**
   - *Mitigation*: Phases 2-5 can tolerate 1-2 week slips without cascading
   - *Buffer*: 26 weeks includes ~20% slack

2. **Solo developer scenario**
   - *Timeline*: 72 person-weeks / 1 FTE = 18 months
   - *Recommendation*: Cut scope to core ledger only (Phases 1-5) = 12 months

---

## Solo Developer Alternative

If building alone, prioritize:

1. **Phase 1-3**: Foundation + Git adapter (9 weeks)
2. **Phase 4**: Skip extended adapter, focus on N12/N16/N21 (3 weeks)
3. **Phase 5**: Just N13/N14 (append/read), defer notes/tags (3 weeks)
4. **Basic tests**: N15 only (1 week)

**Total**: 16 weeks for minimal viable ledger

**Defer to post-1.0:**
- Crypto (N23, N24, N25)
- Indexing/query (N32, N33)
- CLI polish
- Windows support

---

## Next Steps

1. **Validate dependencies** - Review with team, confirm no missing edges
2. **Assign owners** - Match engineers to skill requirements
3. **Set up sprints** - Break phases into 2-week sprints
4. **Define "done"** - Acceptance criteria per task
5. **Track progress** - Weekly sync on critical path items

---

## Appendix: Execution Wave Mapping

For reference, here are the true antichains (tasks with no dependencies between them):

- **Wave 0**: N4, N6, N7, N8, N31, N37, N47, N51 (8 tasks)
- **Wave 1**: N9, N52 (2 tasks)
- **Wave 2**: N10, N17, N18, N22, N30, N50, N53, N54, N58, N59, N61, N62, N64 (13 tasks)
- **Wave 3**: N11, N55, N63, N65, N66, N68, N71, N72, N73 (9 tasks)
- **Wave 4**: N12, N16, N21, N23, N56, N57, N60, N67 (8 tasks)
- **Wave 5**: N13, N14, N24, N25, N26, N27, N69 (7 tasks)
- **Wave 6**: N15, N19, N28, N29, N32, N36, N70 (7 tasks)
- **Wave 7**: N20, N33 (2 tasks)
- **Wave 8**: N34, N35, N39 (3 tasks)
- **Wave 9**: N38 (1 task)

These waves represent the theoretical maximum parallelism. The phased roadmap above groups them into realistic work packages for a small team.
