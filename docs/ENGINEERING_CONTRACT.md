# Progenitor Engineering Contract

This document translates the Progenitor biological language into engineering contracts. The mythology remains the public vocabulary; the engineering names below are the implementation surface used for review, testing, and maintenance.

## Design Position

Progenitor is an open authoring ecosystem, not a closed author whitelist. Human creators and AI agents are encouraged to contribute genes. The review system is therefore designed as verification and containment, not as gatekeeping by identity.

The Registry accepts many creators. The Protocol decides whether a specific payload can be ingested, executed, quarantined, reformed, or rejected.

## Vocabulary Layers

| Narrative term | Engineering term | Responsibility |
| --- | --- | --- |
| Gene | Capability payload | A reusable AI capability file with metadata and executable code. |
| Hatchery | Build system | Source files and compiler that produce the `.pgn` vessel. |
| PGN vessel | Self-bootstrap artifact | The single-file distributable produced by the hatchery. |
| Akashic Stargate | Registry resolver | Semantic name to `content_sha256` lookup and transport selection. |
| Crucible | Validator | Layered audit before ingestion, propagation, or execution. |
| Lysosome | Local quarantine/work area | Local landing zone for fetched or isolated payloads. |
| Spore | Propagation artifact | Shareable capability broadcast or file artifact. |
| TelomereGuard | Runtime guard | Time and memory boundary around dynamic execution. |
| Gene Cage | Process sandbox | Subprocess isolation for risky or external logic. |

## Open Authorship Contract

Creators are not rejected for being unknown. `creator` is metadata for attribution, conflict resolution, rate limiting, and audit history.

Open authorship is safe only when all of the following remain true:

- Registry submissions are content-addressed.
- Metadata is required and validated.
- Dangerous code patterns are blocked before registration.
- Runtime ingestion repeats validation before execution.
- Failed runtime audit moves payloads into quarantine.
- Reformable failures are separated from non-reformable malicious failures.

## Registry Review Contract

Registry Gatekeeper is the first public filter.

| Layer | Engineering rule | Current disposition |
| --- | --- | --- |
| L0 Rate Limit | Limit PR and creator submission volume. | Blocking |
| L1 Lineage Prefix | `life_id` must start with `PGN@`. | Blocking |
| L2 Content Address | Gene file should match SHA-256 content hash. | Implemented in DevKit precheck; should be explicit in Gatekeeper |
| L3 Creator Covenant | Any creator may contribute; missing creator becomes `Anonymous`. | Open, non-blocking |
| L4 Quality Gate | Require description, creator, life_id, and max size. | Warning in Gatekeeper |
| L5 Security Scan | Reject obvious dangerous calls and third-party dependencies. | Blocking |

## Runtime Review Contract

Protocol runtime audit is stricter than Registry review. A gene is not trusted simply because it exists in the Registry.

Runtime ingestion should follow this path:

1. Resolve semantic name through the Akashic index when possible.
2. Fetch bytes through gateway or local Kubo.
3. Write to the local lysosome.
4. Run `crucible_audit()`.
5. Compare `expected_sha256` when available.
6. Quarantine failed payloads.
7. Reform only metadata/lineage failures.
8. Reject integrity/signature/security failures.
9. Execute only through guarded paths when dynamic logic is involved.

## Trust Levels

| Level | Meaning | Allowed action |
| --- | --- | --- |
| `TRUSTED_CORE` | Core Protocol source and generated vessel. | Build, publish, ingest. |
| `VERIFIED_REGISTRY` | Gene passed Registry validation and has index metadata. | Fetch and runtime-audit. |
| `QUARANTINED_EXTERNAL` | Runtime audit failed but may be reformable. | Inspect, reform, never execute directly. |
| `LOCAL_EXPERIMENTAL` | Local candidate not yet registered. | Test locally, do not propagate. |
| `REJECTED` | Integrity, signature, or malicious-pattern failure. | Preserve audit log, do not reform automatically. |

## Current Implementation Assessment

Implemented:

- Registry open creator model.
- Registry L0, L1, L3, L4, L5 checks.
- DevKit SHA-256 filename precheck.
- Protocol `crucible_audit()` runtime validation.
- Protocol quarantine and reform paths.
- Process sandbox and `TelomereGuard` execution guards.
- Standard-library-only protocol hatchery.

Needs tightening:

- Make Registry L2 SHA-256 filename validation explicit in `.github/workflows/gatekeeper.py`.
- Decide whether Registry L4 quality failures should block or remain warning-level.
- Add structured audit records for every Registry rejection, matching Protocol quarantine logs.
- Prefer `content_sha256` or semantic-name ingestion over direct transport hints when integrity matters, because they carry hash verification.
- Keep regex L5 in Registry, but document that AST/process isolation is the stronger Protocol-side protection.

## Release Rule

No gene should move from "contributed" to "trusted execution" in one step. The required path is:

`contributed -> registry verified -> runtime audited -> guarded execution -> optional propagation`

This preserves the creative openness of the ecosystem while keeping malicious payloads isolated and explainable.
