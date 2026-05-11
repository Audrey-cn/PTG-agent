# Next-Phase Plan: Open Authorship + Verified Execution

This plan captures the remaining collection points and turns them into an execution backlog for the Akashic Stargate review model.

## Scope

- Keep contributor model open for humans and AI agents.
- Strengthen verification and containment instead of identity-based gating.
- Make migration safe for existing historical genes.

## What We Collected

1. Registry Gatekeeper accepted open creators, but lacked explicit L2 content-address enforcement in its main loop.
2. Daily scan invoked `--scan-only`, but Gatekeeper had no explicit scan-only branch.
3. Quality gate (L4) was warning-only; no strict-mode toggle existed.
4. Registry had no structured rejection log for failed checks.
5. Historical `genes/` entries include filename/hash mismatches, so hard-enforcing L2 immediately would break existing data.

## What We Implemented In This Iteration

1. Added explicit L2 content-address validator in Gatekeeper main flow.
2. Added `--scan-only` parser and branch to avoid writes in scan-only mode.
3. Added strictness toggle for L2:
   - `GATEKEEPER_STRICT_L2=0` (default): warning mode for migration.
   - `GATEKEEPER_STRICT_L2=1`: blocking mode.
4. Added strictness toggle for L4:
   - `GATEKEEPER_STRICT_L4=0` (default): warning mode.
   - `GATEKEEPER_STRICT_L4=1`: blocking mode.
5. Added structured rejection logs to `.gatekeeper_rejections.jsonl`.

## New To-do List

1. Backfill historical gene hash alignment.
   - Goal: bring all existing `genes/*` filenames in sync with actual SHA-256 content hashes.
   - Output: migration report + remap plan for impacted capability names/CIDs.
   - Exit criteria: L2 warnings count reaches zero in scan-only.

2. Turn on strict L2 in CI after migration.
   - Goal: enforce content-address integrity for all new and existing genes.
   - Action: set `GATEKEEPER_STRICT_L2=1` in `gatekeeper.yml`.
   - Exit criteria: PR with filename/hash mismatch is blocked.

3. Decide strictness policy for L4 quality gate.
   - Goal: choose between permissive onboarding and quality-first blocking.
   - Action: run a 2-week shadow period with warning metrics.
   - Exit criteria: written decision and CI setting (`GATEKEEPER_STRICT_L4`).

4. Integrate rejection log review into daily scan summary.
   - Goal: make `daily_scan.yml` include latest `.gatekeeper_rejections.jsonl` entries.
   - Exit criteria: summary shows top rejection reasons by layer.

5. Add Registry trust-state field in index entries.
   - Goal: annotate each gene with `trust_state`:
     - `VERIFIED_REGISTRY`
     - `QUARANTINED_EXTERNAL`
     - `REJECTED`
   - Exit criteria: `.akashic_index.json` schema includes and populates trust state.

6. Align README layer naming with executable semantics.
   - Goal: keep docs and implementation synchronized for L1/L2 wording.
   - Exit criteria: README + README_CN terminology matches Gatekeeper code paths.

## Suggested Execution Order

1. Hash backfill and migration report.
2. Enable strict L2 in CI.
3. Decide and apply strict L4 policy.
4. Add rejection analytics to daily scan.
5. Add trust-state schema in index.
6. Final doc wording alignment pass.

## Acceptance Commands

```powershell
cd D:\trae\progenitor-registry
python .github\workflows\gatekeeper.py --scan-only
$env:GATEKEEPER_STRICT_L2='1'; python .github\workflows\gatekeeper.py --scan-only; Remove-Item Env:GATEKEEPER_STRICT_L2
```

```powershell
cd D:\trae\Git
python scripts\contract_check.py
python scripts\boundary_check.py
python scripts\encoding_check.py
python scripts\dependency_check.py
python -m pytest tests -q
```
