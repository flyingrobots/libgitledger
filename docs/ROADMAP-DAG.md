# Roadmap Task DAG (Full)

This diagram captures the dependency graph across ALL issues in this repo (open set).

```mermaid
flowchart TD
  N4([#4 CI scaffolding])
  N6([#6 Error API])
  N7([#7 Allocator hooks])
  N8([#8 Logger hooks])
  N9([#9 Context lifecycle])
  N10([#10 Git repo port interface])
  N11([#11 libgit2 adapter])
  N12([#12 Ledger lifecycle])
  N13([#13 Append path])
  N14([#14 Read path])
  N15([#15 Append/read integration tests])
  N16([#16 Policy document storage])
  N17([#17 Policy parser])
  N18([#18 Author identity port])
  N19([#19 Append enforcement])
  N20([#20 Policy enforcement tests])
  N21([#21 Trust document storage])
  N22([#22 Signature port])
  N23([#23 Commit signature validation])
  N24([#24 Attestation support])
  N25([#25 Threshold enforcement])
  N26([#26 Notes API])
  N27([#27 Tag association])
  N28([#28 CLI enhancements])
  N29([#29 Notes and tags integration tests])
  N30([#30 Indexer interface])
  N31([#31 CRoaring integration])
  N32([#32 Cache writer])
  N33([#33 Query engine])
  N34([#34 CLI query commands])
  N35([#35 Query integration tests])
  N36([#36 Deep verify])
  N37([#37 BLAKE3 checksum option])
  N38([#38 Documentation and examples])
  N39([#39 End-to-end tests])
  N47([#47 [M2] Minimal Linux CRT shim (…])
  N50([#50 [M3] Public API v0.1 docs + v…])
  N51([#51 [M3][API] Add Doxygen config …])
  N52([#52 [M3][API] Annotate public hea…])
  N53([#53 [M3][API] CI job: build + upl…])
  N54([#54 [M3] CLI scaffold + examples])
  N55([#55 [M3][CLI] Subcommand framewor…])
  N56([#56 [M3][CLI] Implement 'version'…])
  N57([#57 [M3][CLI] Implement 'error-de…])
  N58([#58 [M3] Windows DLL export audit…])
  N59([#59 [M4] Fuzzing harness for erro…])
  N60([#60 [M4] libgit2 adapter (read-on…])
  N61([#61 [M5] Symbol-policy guard for …])
  N62([#62 [M3][Win] Audit GITLEDGER_API…])
  N63([#63 [M3][Win] Add MSVC shared bui…])
  N64([#64 [M3][Win] Fix printf/PRIuMAX …])
  N65([#65 [M4][Fuzz] error_json fuzzer])
  N66([#66 [M4][Fuzz] version_snprintf f…])
  N67([#67 [M4][Fuzz] CI lane (10s per t…])
  N68([#68 [M4][git2] Define adapter int…])
  N69([#69 [M4][git2] Implement open rep…])
  N70([#70 [M4][git2] List commits (iter…])
  N71([#71 [M5][sym] Linux archive polic…])
  N72([#72 [M5][sym] macOS archive polic…])
  N73([#73 [M5][sym] Windows archive pol…])
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
```

Notes
- Edges are hard dependencies (blocked by). Nodes show issue number and a shortened title.
- Use GitHub’s “Linked issues” section to view bidirectional metadata.
