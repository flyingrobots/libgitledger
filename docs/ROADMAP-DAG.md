# Roadmap Task DAG (Full)

This diagram captures the dependency graph across ALL open issues, grouped by milestone.


```mermaid
%%{init: { 'theme': 'base', 'flowchart': { 'useMaxWidth': false, 'nodeSpacing': 40, 'rankSpacing': 50, 'curve': 'basis' } }}%%
flowchart TD
  %% Node class definitions (milestones)
  classDef M0Node stroke:#8e44ad,stroke-width:2px,fill:#ffffff,color:#111;
  classDef M1Node stroke:#2c3e50,stroke-width:2px,fill:#ffffff,color:#111;
  classDef M2Node stroke:#16a085,stroke-width:2px,fill:#ffffff,color:#111;
  classDef M3Node stroke:#2980b9,stroke-width:2px,fill:#ffffff,color:#111;
  classDef M4Node stroke:#27ae60,stroke-width:2px,fill:#ffffff,color:#111;
  classDef M5Node stroke:#e67e22,stroke-width:2px,fill:#ffffff,color:#111;
  classDef M6Node stroke:#c0392b,stroke-width:2px,fill:#ffffff,color:#111;
  classDef M7Node stroke:#7f8c8d,stroke-width:2px,fill:#ffffff,color:#111;
  %% Root nodes (no incoming edges)
  classDef root fill:#eaffea,stroke:#2ecc40,stroke-width:3px,color:#111;
  subgraph "M0 — Repo Scaffolding & Tooling"
    N4["#4 CI scaffolding"]
  end

  subgraph "M1 — Core Types & Plumbing"
    N6["#6 Error API"]
    N7["#7 Allocator hooks"]
    N8["#8 Logger hooks"]
    N9["#9 Context lifecycle"]
  end

  subgraph "M2 — Git Port & Minimal Ledger"
    N10["#10 Git repo port interface"]
    N11["#11 libgit2 adapter"]
    N12["#12 Ledger lifecycle"]
    N13["#13 Append path"]
    N14["#14 Read path"]
    N15["#15 Append/read integration tests"]
    N47["#47 Minimal Linux CRT shim (_start) and f..."]
  end

  subgraph "M3 — Public API, CLI, Windows"
    N16["#16 Policy document storage"]
    N17["#17 Policy parser"]
    N18["#18 Author identity port"]
    N19["#19 Append enforcement"]
    N20["#20 Policy enforcement tests"]
    N50["#50 Public API v0.1 docs + visibility"]
    N51["#51 Add Doxygen config + CMake target"]
    N52["#52 Annotate public headers with brief/group"]
    N53["#53 CI job: build + upload API docs artifact"]
    N54["#54 CLI scaffold + examples"]
    N55["#55 Subcommand framework + help"]
    N56["#56 Implement 'version' command"]
    N57["#57 Implement 'error-demo' command"]
    N58["#58 Windows DLL export audit + shared bui..."]
    N62["#62 Audit GITLEDGER_API exports for DLL"]
    N63["#63 Add MSVC shared build + test job"]
    N64["#64 Fix printf/PRIuMAX and headers for MSVC"]
  end

  subgraph "M4 — Fuzzing + libgit2 adapter"
    N21["#21 Trust document storage"]
    N22["#22 Signature port"]
    N23["#23 Commit signature validation"]
    N24["#24 Attestation support"]
    N25["#25 Threshold enforcement"]
    N59["#59 Fuzzing harness for errors/version"]
    N60["#60 libgit2 adapter (read-only) skeleton"]
    N65["#65 error_json fuzzer"]
    N66["#66 version_snprintf fuzzer"]
    N67["#67 CI lane (10s per target)"]
    N68["#68 Define adapter interface header"]
    N69["#69 Implement open repository + fixtures"]
    N70["#70 List commits (iterator)"]
  end

  subgraph "M5 — Cross-platform symbol policy"
    N26["#26 Notes API"]
    N27["#27 Tag association"]
    N28["#28 CLI enhancements"]
    N29["#29 Notes and tags integration tests"]
    N61["#61 Symbol-policy guard for archives (cro..."]
    N71["#71 Linux archive policy (nm)"]
    N72["#72 macOS archive policy (nm -U)"]
    N73["#73 Windows archive policy (.lib)"]
  end

  subgraph "M6 — Query + Index"
    N30["#30 Indexer interface"]
    N31["#31 CRoaring integration"]
    N32["#32 Cache writer"]
    N33["#33 Query engine"]
    N34["#34 CLI query commands"]
    N35["#35 Query integration tests"]
  end

  subgraph "M7 — Validation & Docs"
    N36["#36 Deep verify"]
    N37["#37 BLAKE3 checksum option"]
    N38["#38 Documentation and examples"]
    N39["#39 End-to-end tests"]
  end
  %% Soft relationships (epic/parent -> child)
  N50 -.-> N51
  N50 -.-> N52
  N50 -.-> N53
  N54 -.-> N55
  N54 -.-> N56
  N54 -.-> N57
  N58 -.-> N62
  N58 -.-> N63
  N58 -.-> N64
  N59 -.-> N65
  N59 -.-> N66
  N59 -.-> N67
  N60 -.-> N68
  N60 -.-> N69
  N60 -.-> N70
  N61 -.-> N71
  N61 -.-> N72
  N61 -.-> N73

  %% Hard dependencies (task -> prerequisite)
  N53 ==> N51
  N56 ==> N55
  N57 ==> N55
This diagram captures the dependency graph across ALL open issues.


```mermaid
flowchart TD
  N4["#4 CI scaffolding"]
  N6["#6 Error API"]
  N7["#7 Allocator hooks"]
  N8["#8 Logger hooks"]
  N9["#9 Context lifecycle"]
  N10["#10 Git repo port interface"]
  N11["#11 libgit2 adapter"]
  N12["#12 Ledger lifecycle"]
  N13["#13 Append path"]
  N14["#14 Read path"]
  N15["#15 Append/read integration tests"]
  N16["#16 Policy document storage"]
  N17["#17 Policy parser"]
  N18["#18 Author identity port"]
  N19["#19 Append enforcement"]
  N20["#20 Policy enforcement tests"]
  N21["#21 Trust document storage"]
  N22["#22 Signature port"]
  N23["#23 Commit signature validation"]
  N24["#24 Attestation support"]
  N25["#25 Threshold enforcement"]
  N26["#26 Notes API"]
  N27["#27 Tag association"]
  N28["#28 CLI enhancements"]
  N29["#29 Notes and tags integration tests"]
  N30["#30 Indexer interface"]
  N31["#31 CRoaring integration"]
  N32["#32 Cache writer"]
  N33["#33 Query engine"]
  N34["#34 CLI query commands"]
  N35["#35 Query integration tests"]
  N36["#36 Deep verify"]
  N37["#37 BLAKE3 checksum option"]
  N38["#38 Documentation and examples"]
  N39["#39 End-to-end tests"]
  N47["#47 Minimal Linux CRT shim (_start) and f..."]
  N50["#50 Public API v0.1 docs + visibility"]
  N51["#51 Add Doxygen config + CMake target"]
  N52["#52 Annotate public headers with brief/group"]
  N53["#53 CI job: build + upload API docs artifact"]
  N54["#54 CLI scaffold + examples"]
  N55["#55 Subcommand framework + help"]
  N56["#56 Implement 'version' command"]
  N57["#57 Implement 'error-demo' command"]
  N58["#58 Windows DLL export audit + shared bui..."]
  N59["#59 Fuzzing harness for errors/version"]
  N60["#60 libgit2 adapter (read-only) skeleton"]
  N61["#61 Symbol-policy guard for archives (cro..."]
  N62["#62 Audit GITLEDGER_API exports for DLL"]
  N63["#63 Add MSVC shared build + test job"]
  N64["#64 Fix printf/PRIuMAX and headers for MSVC"]
  N65["#65 error_json fuzzer"]
  N66["#66 version_snprintf fuzzer"]
  N67["#67 CI lane (10s per target)"]
  N68["#68 Define adapter interface header"]
  N69["#69 Implement open repository + fixtures"]
  N70["#70 List commits (iterator)"]
  N71["#71 Linux archive policy (nm)"]
  N72["#72 macOS archive policy (nm -U)"]
  N73["#73 Windows archive policy (.lib)"]
  N53 --> N51
  N56 --> N55
  N57 --> N55
  N50 --> N51
  N50 --> N52
  N50 --> N53
  N54 --> N55
  N54 --> N56
  N54 --> N57
  N58 --> N62
  N58 --> N63
  N58 --> N64
  N59 --> N65
  N59 --> N66
  N59 --> N67
  N60 --> N68
  N60 --> N69
  N60 --> N70
  N61 --> N71
  N61 --> N72
  N61 --> N73
  N13 --> N12
  N14 --> N10
  N15 --> N13
  N15 --> N14
  N11 --> N10
  N32 --> N30
  N33 --> N30
  N33 --> N31
  N33 --> N32
  N34 --> N33
  N35 --> N33
  N35 --> N34
  N36 --> N37
  N36 --> N33
  N39 --> N33
  N39 --> N34
  N39 --> N60
  N23 --> N22
  N24 --> N23
  N25 --> N17
  N25 --> N16
  N20 --> N17
  N20 --> N25
  N29 --> N26
  N29 --> N27

  %% Assign milestone classes to nodes
  class N4 M0Node;
  class N6,N7,N8,N9 M1Node;
  class N10,N11,N12,N13,N14,N15,N47 M2Node;
  class N16,N17,N18,N19,N20,N50,N51,N52,N53,N54,N55,N56,N57,N58,N62,N63,N64 M3Node;
  class N21,N22,N23,N24,N25,N59,N60,N65,N66,N67,N68,N69,N70 M4Node;
  class N26,N27,N28,N29,N61,N71,N72,N73 M5Node;
  class N30,N31,N32,N33,N34,N35 M6Node;
  class N36,N37,N38,N39 M7Node;

  %% Highlight root nodes
  style N4 fill:#eaffea,stroke:#2ecc40,stroke-width:3px;
  style N6 fill:#eaffea,stroke:#2ecc40,stroke-width:3px;
  style N7 fill:#eaffea,stroke:#2ecc40,stroke-width:3px;
  style N8 fill:#eaffea,stroke:#2ecc40,stroke-width:3px;
  style N9 fill:#eaffea,stroke:#2ecc40,stroke-width:3px;
  style N11 fill:#eaffea,stroke:#2ecc40,stroke-width:3px;
  style N15 fill:#eaffea,stroke:#2ecc40,stroke-width:3px;
  style N18 fill:#eaffea,stroke:#2ecc40,stroke-width:3px;
  style N19 fill:#eaffea,stroke:#2ecc40,stroke-width:3px;
  style N21 fill:#eaffea,stroke:#2ecc40,stroke-width:3px;
  style N24 fill:#eaffea,stroke:#2ecc40,stroke-width:3px;
  style N28 fill:#eaffea,stroke:#2ecc40,stroke-width:3px;
  style N29 fill:#eaffea,stroke:#2ecc40,stroke-width:3px;
  style N35 fill:#eaffea,stroke:#2ecc40,stroke-width:3px;
  style N36 fill:#eaffea,stroke:#2ecc40,stroke-width:3px;
  style N38 fill:#eaffea,stroke:#2ecc40,stroke-width:3px;
  style N39 fill:#eaffea,stroke:#2ecc40,stroke-width:3px;
  style N47 fill:#eaffea,stroke:#2ecc40,stroke-width:3px;
  style N50 fill:#eaffea,stroke:#2ecc40,stroke-width:3px;
  style N54 fill:#eaffea,stroke:#2ecc40,stroke-width:3px;
  style N58 fill:#eaffea,stroke:#2ecc40,stroke-width:3px;
  style N59 fill:#eaffea,stroke:#2ecc40,stroke-width:3px;
  style N61 fill:#eaffea,stroke:#2ecc40,stroke-width:3px;
```

```
