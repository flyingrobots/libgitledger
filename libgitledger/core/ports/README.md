# Ports

Abstract interfaces consumed by the domain layer are defined here. Each port captures the behaviour required from external systems (Git, filesystem, logging, signing, etc.) and is implemented by concrete adapters under `core/adapters/`.
