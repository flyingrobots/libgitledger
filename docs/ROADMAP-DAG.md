# Roadmap Task DAG

This diagram captures the dependency graph of the newly created roadmap issues.

```mermaid
flowchart TD
  %% Node legend: #num (short title)
  P50([#50 API v0.1])
  I51([#51 Doxygen+CMake])
  I52([#52 Annotate headers])
  I53([#53 CI upload docs])

  P54([#54 CLI scaffold])
  I55([#55 CLI framework])
  I56([#56 version cmd])
  I57([#57 error-demo cmd])

  P58([#58 Windows DLL build])
  P59([#59 Fuzz harness])
  P60([#60 libgit2 adapter])
  P61([#61 Symbol policy archives])

  %% Hard deps (solid)
  I51 --> I53
  I55 --> I56
  I55 --> I57

  %% Soft deps (dashed) parent tracking
  P50 -.-> I51
  P50 -.-> I52
  P50 -.-> I53

  P54 -.-> I55
  P54 -.-> I56
  P54 -.-> I57
```

Notes
- Solid arrows represent hard dependencies.
- Dashed arrows indicate grouping/soft tracking under a parent feature.
- Extend as more children are added under M4/M5.

