# libgitledger Source Layout

This directory contains the core library implementation, organised according to the hexagonal architecture described in docs/SPEC.md. Subdirectories intentionally mirror the ports, adapters, and domain layers so that each milestone can populate concrete code without reshuffling the tree.
