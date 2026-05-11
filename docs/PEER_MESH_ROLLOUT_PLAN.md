# Akashic Peer Mesh Rollout Plan

This document defines the soft rollout path from registry-centered delivery to signed peer-to-peer gene exchange.

## Target

GitHub and the public registry remain useful as bootstrap, archive, and mirror channels, but they are no longer required for direct Agent-to-Agent exchange.

The target flow is:

```text
peer-add -> peer-discover -> peer-handshake -> peer-resolve -> hash verify -> Gatekeeper/Crucible review
```

## Phase A: Compatibility First

- Keep `.akashic_index.json` and `github_raw` hints working.
- Keep legacy string index entries accepted through normalization.
- Serve `/gene/{capability}` and `/gene/{content_sha256}` at the same time.
- Add protocol versions to `/hello` and `/manifest`, but do not reject peers only because they include extra future versions.

## Phase B: Signed Peer Mesh Default

- Prefer signed `/manifest` when a peer URL is known.
- Trust on first use stores `node_id`, `public_key_id`, and peer URL in the local trust store.
- Reject blocked peers before manifest or gene transfer.
- Reject trusted peers if their public key changes unexpectedly.

## Phase C: Registry Becomes Bootstrap

- Use registry only for initial discovery, mirrors, and cold-start recovery.
- Publish peer URLs as optional hints, not as required routes.
- Keep `release-check` validating registry health until peer mesh has equivalent network health coverage.

## Phase D: Network Discovery

- Add LAN UDP beacon scan as the first non-central discovery channel.
- Treat beacon results as candidates only; every discovered peer must still pass signed `/hello` and `/manifest`.
- Add peer exchange through signed manifests: peers may advertise `known_peers`, but imported peers remain candidates until their own signed handshake succeeds.
- Add bootstrap JSON import for relay files or URLs, so cross-network cold start does not depend on GitHub registry shape.
- Replace or extend manual peer list with relay nodes, DHT, or libp2p when the signed handshake layer is stable.
- Keep signed manifest and content hash verification unchanged.
- Route all downloaded genes through review before execution.

## Rollback Rule

If peer discovery or signed handshake fails, fall back to existing local registry and GitHub raw resolution. Never execute peer content without content hash verification and review.

## Debt Cleanup Rule

Compatibility exists only to prevent accidental breakage while the peer mesh is proving itself. Once a replacement path has tests and release-check coverage:

- Replace fake structure tests with real HTTP, signed manifest, beacon, and hash-transfer tests.
- Remove hard-coded gateway assumptions such as fixed `8080` when beacon ACK provides `gateway_port`.
- Keep legacy pull helpers only if they verify `expected_sha256`; unsigned, unchecked peer payloads are not acceptable.
- Keep GitHub/raw registry hints as bootstrap and archive channels until relay/DHT/libp2p discovery has equivalent health checks.
- Treat IPFS CIDs and GitHub raw URLs as transport hints, not as the primary identity of a gene. The primary content identity is `content_sha256`.
- Use `content_sha256`, `capability_name`, and `transport_hint` for Akashic ingestion APIs. Legacy `gene_cid` and `gene_name` aliases have been removed from these public ingestion entrypoints.
- Prefer internal wrappers named around transport/content, such as `_pull_via_transport_hint()` and `_land_content_before_ingest()`. Older CID-named helpers may remain underneath only as transport implementation details.
- Older receptor classes should delegate to the same transport/content wrappers instead of maintaining separate gateway-fetch or lysosome-write implementations.
- Remove a compatibility layer only after the new path is covered by unit tests, CLI smoke tests, and `release-check`.
