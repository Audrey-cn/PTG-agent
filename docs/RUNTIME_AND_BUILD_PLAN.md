# Runtime and Build Plan

This document records the P2 foundation while keeping the generated single-file engine entrypoints stable.

## Runtime directory

The protocol runtime now honors `PROGENITOR_RUNTIME_DIR`.

Default layout:

```text
~/.progenitor/runtime/
  lysosome/
  quarantine/
    pending/
    rejected/
    reformed/
  gene_index.json
```

Repository-local generated state should not be required for normal runtime behavior. Local development tools may set `PROGENITOR_RUNTIME_DIR=D:\trae\.runtime\progenitor`.

## Source modularization target

`hatchery/engine.py` remains the distributable single-file runtime. The next safe step is to introduce source modules under a future internal source tree and generate the single-file engine from them.

Initial module boundaries:

| Module | Responsibility |
|---|---|
| `audit` | Crucible checks, hash verification, structured audit records |
| `quarantine` | Pending/rejected/reformed storage and audit log writes |
| `akashic` | Registry index lookup and `content_sha256` resolution |
| `stargate_transport` | Kubo/gateway transport routes behind content-addressed ingestion |
| `sandbox` | AST checks and isolated execution |
| `manifest` | Manifest/YAML-subset parsing |
| `bootstrap` | Incubator/bootstrap packaging |

Exit criteria for the real split:

1. `python scripts/devkit.py release-check` passes before and after generation.
2. Generated `hatchery/engine.py` preserves public entrypoints in `docs/PROTOCOL_CONTRACT.json`.
3. `INGEST_ME_TO_EVOLVE_pgn-core.pgn` is regenerated from the built single-file runtime.
