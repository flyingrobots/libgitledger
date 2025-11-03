# Drift Report: libgitledger vs. Ledger‑Kernel Spec

Date: 2025-11-03T22:48:13Z

This report compares our current roadmap (issues + DAG) to the Ledger‑Kernel specification in `external/ledger-kernel`.

## Inputs

- Spec repository (submodule): `external/ledger-kernel`
  - Schemas: `schemas/`
  - Compliance: `docs/spec/compliance.md` (C‑1…C‑5 ↔ FS/M)
  - Formal spec: `docs/spec/*.md` (FS‑1…FS‑14, M‑1…M‑9)
- Roadmap DAG: `docs/ROADMAP-DAG.mmd` (grouped by milestones)

## Mapping Summary

- FS‑10 (Canonical wire format + ID): PARTIAL
  - Roadmap: No explicit issue yet; closest: [M4] libgit2 adapter (I/O), [M3] API docs.
  - Gap: Add issue “Wire format canonicalization + BLAKE3 id (FS‑10)” under M3/M4.

- FS‑7/FS‑8 (Append-only + ref fast‑forward): PARTIAL
  - Roadmap: Append path (#13), Append enforcement (#19), Policy enforcement tests (#20).
  - Gap: Add explicit non‑FF ref rejection test issue.

- FS‑11 (Temporal ordering): PARTIAL
  - Roadmap: Ledger lifecycle (#12) + Append/read integration tests (#15).
  - Gap: Add validation test “reject child timestamp < parent”.

- FS‑3/FS‑9 (Deterministic policy evaluation): N/A (engine not yet present)
  - Roadmap: Policy parser (#17), Policy storage (#16).
  - Gap: Add “Deterministic policy eval harness” issue and seed vectors.

- FS‑6 (Offline verify end‑to‑end): PARTIAL
  - Roadmap: End‑to‑end tests (#39).
  - Gap: Add small offline replay vector + verifier entrypoint.

## Risks / Assumptions

- BLAKE3 dependency: We will vendor or link a minimal BLAKE3 for FS‑10.
- WASM policy runtime: Not required for core, mark as N/A until available.

## Recommendations

1. Create the following issues and link under milestones:
   - [M3] FS‑10 Canonicalization + BLAKE3 id (core)
   - [M2] Non‑FF ref rejection tests (FS‑7/FS‑8)
   - [M2] Timestamp monotonicity validation (FS‑11)
   - [M4] Deterministic policy evaluation harness (FS‑3/FS‑9)
   - [M3] Offline verify minimal replay (FS‑6)
2. Add a compliance harness skeleton (report writer + CLI flag) and wire C‑1…C‑3 quickly; mark others N/A.
3. Add CI workflow `compliance.yml` in soft mode (artifact only); enable gating on core once C‑1…C‑3 are green.

## Next Steps (Implementation Plan)

- Include headers + source stubs under `include/ledger/` and `src/compliance/`.
- Add CLI flag `--compliance` (or a small utility) without impacting library ABI.
- Seed vectors in `tests/vectors/core/`.

