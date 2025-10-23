# PROJECT PLAN

## Milestones → Features → Tasks + Tests

**Opinionated roadmap**: ship minimal core fast (M1–M2), then lock security (M3–M4), then UX features (M5–M6), then perf/indexing (M7).

---

## M0 — Repo Scaffolding & Tooling (1 day)

### Deliverables

- Repo skeleton
- build systems (CMake + Meson)
- CI smoke for both builders
- coding standards.

### Tasks (step‑by‑step)

#### 1. Create repo & structure

- [ ] `mkdir -p libgitledger/{include/gitledger,core/{domain,ports,adapters/libgit2,cache,policy_trust},adapters,tests,cli}`
- [ ] Add `LICENSE` (MIND-UCAL), `README.md`, `CONTRIBUTING.md`.

#### 2. Build systems

- [ ] **Author dual build files**: create root `CMakeLists.txt` *and* `meson.build`; ensure both produce targets `gitledger`, `gitledger_tests`, `git-ledger` (`release` + `dev` variants).
- [ ] Add shared warning and visibility flags (`-Wall`, `-Wextra`, `-Werror`, `-std=c11`, `-fvisibility=hidden`) to both configurations.

#### 3. Third‑party deps

- [ ] Add `libgit2` as a dependency (`pkg-config`/submodule); surface it in both build systems.
- [ ] Plan vendors for `CRoaring` and `BLAKE3` later; leave stubs/options in both `CMake` and `Meson` files.

#### 4. CI

- [ ] **Dockerfile + GitHub Actions**: matrix that builds and unit-tests via CMake/Ninja and Meson/Ninja (debug + release) on Ubuntu.

#### 5. Coding standard

- [x] `.clang-format`
- [x] `.clang-tidy`
- [x] `editorconfig`

#### Tests

- CI builds/tests both configurations (`debug` + `release`) and runs a dummy test target to keep pipelines green.

---

## M1 — Core Types, Errors, Allocator, Logger (1–2 days)

### Deliverables

- `gitledger.h` with error codes
- context/ledger handles
- allocator/logger

### Tasks

#### 1. Define error/result API

- Add `gitledger_code_t`, `gitledger_error_t` (code + message + cause chain).
- Implement `gitledger_error_str`, `gitledger_error_free`.

#### 2. Allocator hooks

- Define `gitledger_allocator_t`; implement `gitledger_set_allocator`.
- Replace all `malloc`/`free` in core with indirections.

#### 3. Logger hooks

- Define levels; implement `gitledger_set_logger`; stdio adapter in adapters.

#### 4. Context lifecycle

- [ ] `gitledger_init`/`shutdown` with allocator/logger defaults.
- [ ] Create header and source files; wire up both CMake and Meson; compile; run unit tests under each toolchain configuration.

#### Tests

- [ ] **Unit**: constructing/destructing context, error formatting, logger calls.

---

## M2 — Git Port + Minimal Append & Read (3–4 days)

### Deliverables

- Ports defined
- `libgit2` adapter
- ledger open/close
- append
- `get_latest`
- get message.

### Tasks

#### 1. Define git_repo_port

- **Functions**: open repo, read ref OID, write ref fast‑forward, create commit from message bytes, read object bytes, notes CRUD skeleton.
- No signing yet.

#### 2. Adapter: `libgit2`

- Implement all port functions using `libgit2`; hide it in `core/adapters/libgit2/`.

#### 3. Ledger lifecycle

- `gitledger_ledger_open`/`close`: validate or create journal ref.

#### 4. Append (no policy/signing)

- Build commit with empty tree; parent = tip of `refs/gitledger/journal/<L>` (if any); message = encoder output.
- Attempt ref update with expected old OID to enforce fast‑forward.
- Return `GL_ERR_CONFLICT` on mismatch.

#### 5. Read

- `gitledger_get_latest_entry` and `gitledger_get_entry_message`.
- Create core/ports/`git_repo_port.h`; write minimal adapter; unit‑test adapter with temp repos.
- Wire `gitledger_append` flow (domain “commit plan” is trivial in this milestone).

#### Tests

- **Unit**: mock port ensures append calls sequence correctly (plan → write).
- **Integration**: create temp repo; open ledger; append 2 entries; verify chain & messages; simulate concurrent writer to trigger conflict path (should fail with `GL_ERR_CONFLICT`).

This mirrors git‑mind’s “plan → execute via port” orchestration. ￼

---

## M3 — Policy (require_signed, allowed_authors) (3 days)

### Deliverables

- Policy JSON load/store; enforcement in append().

### Tasks

#### 1. Policy format & schema

- Define policy.json keys noted in §7.
- Implement `gitledger_policy_get`/`set` storing the doc in `refs/gitledger/policy/<L>`.

#### 2. Author capture

- Determine author identity (env port: `GIT_AUTHOR_NAME`/`EMAIL` or provided in API).

#### 3. Enforcement in append

- If `allowed_authors` present, enforce; if `require_signed` set, mark pending (actual sig verify in M4).
- Enforce max payload size if set.
- Choose lightweight JSON (e.g., `yyjson` vendor); implement strict parse; validate fields.
- Unit test parse + invalid cases; enforce paths with fake ports.

#### Tests

- Policy set/get round‑trip; append blocked for unknown author; append allowed for allow-list; `require_signed` toggles behavior (temporarily accept but mark `GL_ERR_NOSIG` if signature missing to be finalized in M4).

Grounded by shiplog’s policy‑as‑code. ￼

## M4 — Trust & Signatures (chain + attestation) (5–7 days)

### Deliverables

- Trust JSON, signature extraction, verification adapters, hard enforcement.

### Tasks

#### 1. Trust format

- `trust.json`: maintainers, threshold, `allowed_signers`, `signature_mode`. Store in `refs/gitledger/trust/<L>`.

#### 2. Signature capture paths

- **Chain mode**: commit signatures present in object (`gpgsig`).
- **Attestation mode**: detached signature stored as a note on the entry commit or in trust ref commit; include signer identity & fingerprint.

#### 3. Verification

- **Port**: `signing_port` with `verify_commit_signature(oid, &signer)` / `verify_detached_signature(oid, …)`.
- **Default adapter**: stub that returns “present but unverified” until a crypto backend is configured; log warnings.
- **Optional adapters**: GPGME, SSHSig (later).

#### 4. Enforcement

- When `require_signed` true, `append()` fails with `GL_ERR_NOSIG` if signature missing/invalid.
- Trust updates themselves require N‑of‑M cosign (enforce during gitledger_trust_set).

#### 5. Audit

- `verify_ledger_integrity(deep=1)` walks history, re‑verifies signatures & policy at each commit.
- Write trust parser; implement “present” checks using `libgit2`’s signature extraction; wire verification port; fail closed if policy demands it.
- Provide CLI demo to print signature status.

### Tests

- **Unit**: trust JSON parsing; threshold logic; invalid trust updates rejected.
- **Integration**: append unsigned (blocked), append signed (allowed when signer in `allowed_signers`); switch to attestation mode and verify with notes.

Modeled on shiplog trust model. ￼

## M5 — Notes & Tag Association (2–3 days)

### Deliverables

- `attach_note()`, tag ↔ entry associations via notes on tag objects.

### Tasks

#### 1. Notes

- Implement `gitledger_attach_note()` using `libgit2` notes API under `refs/gitledger/notes/<L>`.

#### 2. Tag association

- Resolve tag object OID (not the commit it points to).
- Add a note under `refs/gitledger/tag_notes` containing `entry_oid=<sha1/sha256>` (+optional metadata).
- Implement reverse lookup `gitledger_tag_get_associated_entries()` in later polish.
- Add helper to look up tag objects; write note create/read; include tests.

### Tests

- **Integration**: create tag; append entry; associate; read back association; multiple associations handled.

**Grounding**: generalizing shiplog’s “attach data via notes” pattern; new piece is linking tags to ledger entries by annotating the tag object.

## M6 — Indexer + Roaring Cache + Query API (5–7 days)

### Deliverables

- Indexer callback; cache build; boolean term queries.

### Tasks

#### 1. Indexer adapter

- Define `gitledger_indexer_v1_t` (see API).

#### 2. Cache schema

- Term dictionary → roaring bitmap of entry ordinals.
- Store under `refs/gitledger/cache/<L>` as a pack of serialized bitmaps + term table.

#### 3. Rebuild

- Stream the journal from root; for each entry: call indexer → add ordinal to bitmaps.

#### 4. Query

- **Parse terms**: default `OR`; `+` = MUST, `-` = MUST_NOT; compute result bitmap; return iterator over matching ordinals → OIDs.
- Vendor `CRoaring`; write serializers; implement rebuild command; add CLI git-ledger query.
- Use memory‑mapped files in temp during build to avoid RAM blowup; write back atomically to cache ref.

### Tests

- **Unit**: add/remove ordinals; serialize/deserialize; boolean algebra correctness.
- **Integration**: build cache; query known terms; mutate journal → rebuild → query results reflect changes.

Pattern borrowed from git‑mind’s roaring cache. ￼

## M7 — Integrity, Self‑Audit, Hardening (2–3 days)

### Deliverables

- Deep audit tool, `BLAKE3` ref checksums (optional), docs, examples.

### Tasks

#### 1. Audit

- **Implement `verify_ledger_integrity(deep=1)`**: parent pointer checks, ref consistency, policy/trust per entry, signature verification.

#### 2. Self‑audit hooks

- Optional `BLAKE3` checksum note on ref tip; verify on open (warn/fail configurable).

#### 3. Docs + Examples

- **Ship sample encoders**: shiplog‑style (header + JSON trailer) and git‑mind‑style (base64‑CBOR) to demonstrate both worlds.

### Tests

- Corrupt commit message → detect.
- Rewritten ref → fail audit.
- Mismatched checksum → warn/fail per policy.

`BLAKE3` hook was explicitly in an earlier plan. ￼

---

## A) Add `libgit2` adapter (M2.T2)

1. `git submodule add https://github.com/libgit2/libgit2 external/libgit2` (or use system package; pick one and stick to it).
2. In build configuration files (`CMakeLists.txt`, `meson.build`):
   - Add the vendored/system `libgit2` target (e.g., `add_subdirectory(external/libgit2)` / `subdir('external/libgit2')`).
   - Link `gitledger` against `git2` in both toolchains.
3. Create `core/ports/git_repo_port.h` with function pointers for:
   - `open`
   - `read_ref`
   - `write_ref_ff`
   - `write_commit_message`
   - `read_object`
   - `note_add`/`get`
   - `tag_lookup_object`
4. Implement `core/adapters/libgit2/repo_port.c`:
   - Wrap `git_repository_open_bare` (prefer bare for tests).
   - **Read ref**: `git_reference_name_to_id`.
   - **Write ref fast‑forward**: `git_reference_lookup` → ensure old OID matches → `git_reference_set_target`.
   - **Create commit**: build empty tree (`git_treebuilder` → write empty tree), `git_commit_create`.
   - **Notes**: `git_note_create` / `git_note_read` with custom refs.
   - **Tags**: resolve annotated tag object via `git_tag_lookup`.
5. Add error translation helper: `libgit2` error → `gitledger_error_t`.
6. Build; run unit tests.

### Tests for A)

- Setup temp repo under `/tmp` with `git_repository_init`.
- Create ledger; append message “one”; assert ref updated; read back message equals input bytes.
- Simulate concurrent append by moving ref between read and write; must return `GL_ERR_CONFLICT`.

## B) Policy enforcement (M3)

1. Vendor `yyjson` (or alternative); expose targets/includes in both CMake and Meson (header-only or static lib).
2. Implement `gitledger_policy_get`/`set`:
   - Store JSON bytes as a blob in a commit pointed by `refs/gitledger/policy/<L>` (same mechanism you used in shiplog, but via libgit2). ￼
3. Parse on `append()`; enforce `allowed_authors` and max size.
4. Add environment/identity port (get author email).

### Tests

- Set `allowed_authors` to `[ "me@example.com" ]`; attempt with other author → `GL_ERR_POLICY`.
- **Missing policy**: default to permissive or deny per config (test both).

## C) Trust + signature (M4)

1. Implement `gitledger_trust_get`/`set` the same way as policy (dedicated ref). ￼
2. Add `signing_port`:
  - `extract_commit_sig(oid, &algo, &signer_fpr)`.
  - `verify_commit_sig(oid, expected_fpr)` → bool.
  - `verify_detached_sig(oid, sig_blob)` → bool.
3. For chain mode:
  - Use `libgit2` to extract signature fields; check that signer fingerprint ∈ `allowed_signers`.
4. For attestation mode:
  - Write/read signature note and verify via adapter.
5. Enforce `require_signed` at `append()` (hard fail if invalid).

### Tests

- **Trust threshold**: attempt to update trust.json without N‑of‑M cosign → rejected.
- Append signed entry with allowed signer → OK; same with unlisted signer → `GL_ERR_TRUST`.

## D) Notes + Tags (M5)

1. Implement `gitledger_attach_note()` using `git_note_create` under `refs/gitledger/notes/<L>`.
2. `gitledger_tag_associate()`:
   - Resolve tag object (`git_tag_lookup`); add note under `refs/gitledger/tag_notes` with payload: `entry_oid=<sha>` (and JSON metadata optionally).
3. Provide helper to list associations (stretch).

### Tests

- Attach note; read it; binary content round‑trips.
- **Tag association**: read note from tag object; verify entry OID.

## E) Indexer & cache (M6)

1. Vendor `CRoaring`; surface it through both build systems.
2. Implement serializer for: term -> bitmap map.
3. `cache_rebuild`:
   - Iterate journal commits oldest→newest; `ordinal++`.
   - Call indexer; for each term add ordinal to bitmap.
   - Serialize; write to blob; move `refs/gitledger/cache/<L>` to new commit.
4. `query_terms`:
   - Load cache; for each term, get bitmap; compute boolean ops; translate ordinals → OIDs.

### Tests

- Fake indexer that emits: `service:api` for 1st & 3rd; query returns those two OIDs.
- Negative term (`-status:fail`) excludes failing entries.

## F) Integrity & self‑audit (M7)

1. Implement deep verify:
   - **For each commit in ledger**: parent chain, policy at commit time, trust at commit time (resolve docs as of that commit), signature validity.
2. Optional `BLAKE3` checksum:
   - Compute on head OID + refs (policy/trust/cache heads) → store note on `journal/<L>` tip; verify on open. ￼

### Tests

- Manually corrupt note payload → verify fails.
- Rewrite ref (simulate malicious) → audit detects non‑fast‑forward.

---

## Acceptance Criteria per Milestone

- **M1**: compile on CI; context/allocator/logger tests pass.
- **M2**: append + read work; conflict path observable; no shell exec.
- **M3**: policy blocks/permits as configured; JSON strictness tested.
- **M4**: `require_signed` enforced; trust threshold enforced; audit verifies.
- **M5**: notes round‑trip; tags link to entries and can be enumerated.
- **M6**: cache rebuild & queries return correct sets across boolean ops.
- **M7**: full audit catches tampering; optional `BLAKE3` works.

---

## CLI Demo: `git-ledger` (reference only)

Minimal CLI to prove library flows:

- [ ] `git-ledger open <path> -L <name>`
- [ ] `git-ledger append -L <name> --file payload.json --encoder shiplog`
- [ ] `git-ledger note add -L <name> <oid> --file out.log`
- [ ] `git-ledger tag-assoc -L <name> v1.2.3 <oid>`
- [ ] `git-ledger policy set -L <name> policy.json`
- [ ] `git-ledger trust set -L <name> trust.json`
- [ ] `git-ledger cache rebuild -L <name>`
- [ ] `git-ledger query -L <name> +service:api -status:fail`
- [ ] `git-ledger verify -L <name> --deep`

---

## Risks & Mitigations

- **Signature verification complexity**: start with presence/identity checks; add GPGME/SSHsig adapters later.
- **Cache corruption**: cache is rebuildable; never source of truth.
- **Bindings ABI drift**: freeze public structs; opaque handles; versioned symbols.
- **Performance**: use `mmap` during cache rebuild; stream commits; avoid loading full history into RAM.

---

## Future Work (selected)

- Zero‑copy bundle format for prebuilt cache and quick hydration. ￼
- Multi‑ledger causal graphs ([MetaGraph](https://github.com/meta-graph/core)), cross‑ledger queries. ￼
- RPC/GraphQL microservice around `libgitledger` for remote querying. ￼

---

## Appendix A — Mapping to Prior Art (why this will work)

- **git‑mind → architecture & cache**: the clean separation of domain, ports, and adapters, plus roaring bitmap cache, are directly adopted. We’re keeping the “plan a commit in the domain, execute via git port” pattern. ￼
- **shiplog → features & governance**: human‑readable + JSON trailers, notes for logs/artifacts, policy as code, multi‑sig trust, and server‑side enforcement patterns inform our spec and APIs. ￼
- **`libgitledger` draft → final polish**: ref namespaces, roadmap phases, encoder/indexer typedefs, dir tree, and `BLAKE3` self‑audit are incorporated verbatim in spirit. ￼

---

## Appendix B — Example Encoders

1. Shiplog‑style (human header + JSON trailers) — immediate readability for operators. ￼
2. git‑mind‑style (base64‑CBOR line) — compact, binary‑safe, no whitespace ambiguity. ￼

---

## Appendix C — Server‑Side Integration

- Provide a sample `pre‑receive` hook (documented) that rejects non‑FF pushes or pushes that violate policy/trust (central enforcement), borrowing shiplog’s approach. ￼

---

## Final Notes (tone check)

- **Strong opinion**: `libgit2` is the correct choice; shelling out in a library is a booby trap.
- **Corrections**: don’t collapse ports into the adapter “for speed”; it kills testability. Don’t punt policy/trust to “apps later”; it’s core to the value prop. Don’t skip the roaring cache; query latency kills adoption.
- **Forward‑looking**: freeze ABI early; ship minimal encoders; then get one rock‑solid binding (Go or JS) to validate ergonomics.

## TL;DR — Top Risk Areas

1. **Signature & Trust semantics (time‑travel rules)**. Verifying who could write then, not who can write now. Hard because keys rotate, trust changes, and signatures come in two flavors (chain vs attestation). ￼

2. **Distributed append‑only in Git’s world**. Local FF‑only is easy; networked FF‑only is political theatre without server hooks and detection/audit. ￼

3. **Ordinal mapping for the Roaring cache**. You want fast term queries tied to “entry #N”, but ordinals must stay correct under conflicts, partial clones, and reorgs. ￼

4. **Notes & tag association correctness**. Annotated vs lightweight tags, moved tags, and notes living on object IDs (not names) make associations fragile. ￼

5. **API/ABI stability for bindings**. Ownership, lifetimes, and thread‑safety across FFI without leaks or UB. (The part future‑you curses present‑you for.) ￼

6. **Binary‑safe payloads vs human‑readable encoders**. Git wants “bytes”, tools assume “text”. Mixing shiplog’s trailers and git‑mind’s CBOR safely is subtle.

7. **Policy as Code enforcement points**. Where exactly policy applies (pre‑append, post‑append audit, server‑side hook) and how to version policy across history. ￼

8. **Garbage collection, reachability, and cache durability**. Cache must be rebuildable; notes must remain reachable; nothing should vanish under git gc.

9. **Hash‑algorithm transition (SHA‑1 ⇄ SHA‑256)**. OID sizes, signature formats, and mixed repos—plan for it now or get cut later. ￼

10. **Concurrency & ref‑transactions**. Multi‑writer fast‑forward without lost updates; clean conflict signaling and retry loops. ￼

11. **Large attachments via notes**. Size limits, performance, and replication; you’ll need policy caps and a “blob‑by‑hash” indirection path. ￼

12. **Cross‑platform realities (Windows/WSL/macOS)**. Path rules, file locking, and `libgit2` behavioral edges—our tests must be mean. ￼

## What makes each one hard — and how to handle it

### 1) Signatures, Trust, and “as‑of” semantics

**Why hard**: Shiplog’s model is powerful (N‑of‑M, chain/attestation), but correctness hinges on as‑of verification: an entry is valid if it met the policy+trust in force when it was written, not what’s current today. Add key rotation, expiry, revocation, and detached attestations and you’ve got a swamp. ￼

#### Decisions to bake in now

- **Snapshot evaluation**: `verify_ledger_integrity(deep=1)` must evaluate each entry against the policy/trust at that commit’s point in history. Store policy/trust on dedicated refs, but embed the OID of the policy/trust tips used at append time in the entry’s trailers to anchor verification. ￼
- **Two modes, one contract**: Support chain (commit signatures) and attestation (detached; note‑stored) behind a single `signing_port` so backends (GPGME/SSHsig) can vary. ￼
- **Threshold edits to trust**: Updates to trust.json require N‑of‑M maintainer cosignatures, enforced in `gitledger_trust_set()`. ￼

#### Tests that catch regressions

- Historical trust change invalidates future entries correctly but not past ones; deep verify must pass pre‑change entries and fail post‑change violators.
- Rotate a signer key; ensure mapping by fingerprint not email; revocation respected only from revocation time forward.

### 2) Distributed append‑only (you don’t control the internet)

**Why hard**: Locally you can update-ref with an expected old OID and call it a day; remotely anyone can force‑push unless the server refuses. The library can’t police GitHub/GitLab policy—but consumers will expect “append‑only.” ￼

#### Mitigations

- **Fail closed locally**: `gitledger_append()` must always use expected‑old‑OID fast‑forward semantics and return `GL_ERR_CONFLICT` on drift. ￼
- **Server‑side recipe**: Ship a pre‑receive example hook that rejects non‑FF and policy violations (documented, not enforced by the lib). ￼
- **Tamper detection**: Deep verify should flag gaps, non‑linear parents, or tip rewinds since last audit; offer a “last‑known‑good” watermark.

#### Tests

- Simulate a remote force‑push (move the ref backwards) and confirm audit fails loudly; confirm hook script would have blocked it.

### 3) Ordinals & the Roaring cache

**Why hard**: git‑mind’s cache uses ordinals (entry #0, #1, …) as bitmap positions. That’s blazing fast—but only if ordinals are stable and consistent across rebuilds and clones. Conflicts, partial clones, or history repair can desync mapping. ￼

#### Mitigations

- **Canonical ordinal**: Ordinal = position by parent chain from the ledger root, not by timestamp. Recompute deterministically on rebuild. ￼
- **Cache is rebuildable**: Treat cache as derivative under `refs/gitledger/cache/<L>`; never source of truth. If mismatch → rebuild. ￼
- **Atomic publish**: Write new cache snapshot as a blob/commit and fast‑forward cache ref in one transaction.

#### Tests

- Inject out‑of‑order timestamps; confirm ordinals identical after rebuild.
- Corrupt cache; verify query falls back or forces rebuild and returns correct results.

### 4) Notes & tag association correctness

**Why hard**: Notes attach to object IDs. Lightweight vs annotated tags differ; moving a tag creates a new object, leaving the old note behind. Association semantics must be explicit. ￼

#### Mitigations

- **Annotate tag objects only**: Define API to resolve annotated tag OID; if lightweight, offer to create an annotated tag or store an association record elsewhere.
- **Staleness policy**: If a tag moves, previous association becomes historical; provide `tag_associations(tagName, --as-of)` to show history.
- **Cap note sizes & prefer blob links**: Store large data as blobs; note contains a small JSON with blob OIDs.

#### Tests

- Convert a lightweight tag to annotated; verify association creation path.
- Move a tag; ensure old association remains discoverable as historical.

### 5) Stable C ABI & FFI ergonomics

**Why hard**: You want Go/JS/Python bindings. That means opaque handles, no struct layout leaks, clear ownership, and predictable threading. If you expose the wrong thing now, you’re stuck forever. ￼

#### Mitigations

- Opaque types only; all allocation through `gitledger_*_new()`/`*_free()`.
- Error objects are heap‑owned; callers must free; never return borrowed pointers that can dangle.
- **No global state; ctx carries all configuration. Thread‑safety doc**: ledger handles not thread‑safe; reads in parallel are fine with separate handles. ￼

#### Tests

- Valgrind/ASan in CI; fuzz decoders/indexers; run language binding smoke tests that hammer create/free cycles.

### 6) Encoders: bytes vs text

**Why hard**: shiplog wants human‑readable with trailers; git‑mind wants binary CBOR. Git will store arbitrary bytes in commit messages, but many tools assume UTF‑8. Don’t lose data; don’t break pretty logs.

#### Mitigations

- **Encoder contract = bytes; library never interprets encoding. Provide example encoders**: “shiplog‑style (UTF‑8+trailers)” and “git‑mind‑style (base64 CBOR)”.
- **Size & content policy**: `max_entry_size_bytes`; forbid NUL in human‑mode; recommend base64 for binary.

#### Tests

- Round‑trip random binary payload via base64 encoder; ensure exact match.
- Verify trailer parser ignores binary lines safely.

### 7) Policy enforcement points

**Why hard**: If you only check policy in `append()`, remote pushes can bypass it; if you only check server‑side, local dev flows are confusing. Also: which policy applies to which commit? ￼

#### Mitigations

- **Triple guard**: enforce in `append()`, re‑check in `verify_ledger_integrity()`, and provide a server hook template. ￼
- **As‑of policy**: embed policy/trust tip OIDs used at append time in the entry trailers. Audits use those, not “latest”. ￼

#### Tests

- Change policy to disallow an author; ensure old entries remain valid, new ones blocked; deep verify behaves.

### 8) GC, reachability, and durability

**Why hard**: `git gc` prunes unreachable objects. Notes and cache commits must remain reachable via refs you control; otherwise you silently lose data.

#### Mitigations

- Keep dedicated refs for notes (`refs/gitledger/notes/<L>`), cache, policy, trust, and tag notes; never leave data floating as loose objects. ￼
- Cache is rebuildable by design; never treat it as canonical. ￼

#### Tests

- Run `git gc --aggressive` on test repo; confirm notes & cache persist; purge cache ref and confirm rebuild restores query behavior.

### 9) Hash‑algorithm transition (SHA‑1 ⇄ SHA‑256)

**Why hard**: OIDs change width; signature formats differ; some repos will be dual‑mode for a while. If the public API assumes 40‑char hex forever, future you cries. ￼

#### Mitigations

- Binary OID API internally; hex is rendering. Accept variable‑length hex (40/64).
- **Avoid hard‑coding “41 including NUL”; define constants from `libgit2` capabilities and expose helpers**: `gitledger_oid_to_hex()`.

#### Tests

- Compile‑time tests that `OID_HEX_MAX` isn’t assumed 41; fuzz with 20‑byte and 32‑byte synthetic OIDs.

### 10)  Concurrency & ref transactions

**Why hard**: Two writers race → one must lose gracefully; the loser must detect, reload, and retry without corrupting ordinals or cache. ￼

#### Mitigations

- Always update refs with expected‑old OID; map `libgit2`’s error to `GL_ERR_CONFLICT`.
- Retry loop backoff in CLI; library stays pure and returns conflict.

#### Tests

- Multi‑process appends; ensure exactly one winner, no dupes, cache stays consistent (or rebuilds).

### 11)  “Run”‑style large attachments via notes

`Why hard`: Logs/artifacts can be huge; notes weren’t meant to be a package registry. Shiplog does it, but you need sane limits and guidance. ￼

#### Mitigations

- Policy caps for note sizes; enforce in `attach_note()`.
- **Prefer blob indirection**: write artifact as blob; note holds small JSON pointing to blob OID(s).

#### Tests

- Attach 10MB blob via indirection; ensure replication and retrieval are fast; direct huge note should be rejected per policy.

### 12)  Cross‑platform reality check

**Why hard**: `libgit2` smooths a lot, but Windows path rules/locks and macOS filesystem oddities still surface. CI must prove portability. ￼

#### Mitigations

- Dockerized CI matrix; run tests on Linux + macOS + Windows.
- Avoid temp file shenanigans; use the planned `fs_temp_port` and test it hard. ￼

#### Tests

- Stress create/close cycles; concurrent readers on Windows; long‑path opt‑in.

---

## “Make it real” checklists to add to `SPEC.md` (fast wins)

- Embed policy/trust tip OIDs in every entry’s trailers at append time. (Locks “as‑of” behavior.) ￼
- Binary‑first OID API; provide safe hex helpers; never bake “41”. ￼
- **Cache is derivative**: atomic publish, easy nuke & rebuild; ordinals are chain‑position from root. ￼
- Server‑side enforcement kit (`pre‑receive` example) shipped next to the library docs. ￼
- Two sample encoders (shiplog‑style trailers; git‑mind base64‑CBOR) with end‑to‑end tests.

---

## If timelines get tight, here’s what to cut (without hurting the core)

- Defer attestation (detached) and ship chain signatures first—keep the `signing_port` so you can add it later. ￼
- Ship cache rebuild before incremental update; rebuild on demand post‑append. ￼
- Start with annotated tags only for associations; warn (don’t auto‑convert) on lightweight tags. ￼

---

## Final opinionated guidance

- Do not collapse ports into the `libgit2` adapter “for speed.” Testability is the moat. (This is why git‑mind felt so clean.) ￼
- Do treat policy/trust as first‑class or you’ll reinvent it badly in each consumer. (Shiplog taught you this.) ￼
- Do freeze the API surface early; everything else can iterate behind it. (The `SPEC` already leans this way.) ￼
