# Baseline Timing Study Tracking (T042)

**Status**: Pending — not started. Requires operations/brokerage involvement, not just engineering.

## Requirement

FR-019 (spec.md): "Before this feature is considered complete, the current fully-manual abstraction
time (baseline for SC-001) MUST be measured against a representative sample of recent leases, so
the improvement can be validated rather than assumed." This echoes README.md §7's own caution:
"Baseline metrics... should be measured before rollout. Without a baseline the improvement in §3.1
cannot be substantiated."

## Why this is tracked separately

`POST /v1/baseline-measurements` (T041) only builds the endpoint to *record* a measurement. Nothing
in this codebase can conduct the study itself — it requires timing real analysts abstracting real
leases by hand, which is an operations exercise, not a software task.

## What the study needs to produce

A call to `POST /v1/baseline-measurements` with:
- `sample_lease_ids`: which leases were used for the timing sample (recommend 15-30 for a
  reasonably stable median)
- `measured_median_minutes`: the median wall-clock time an analyst took to fully abstract a lease
  by hand, start to finish
- `method`: how the sample was selected and timed (e.g., "stopwatch timing, N analysts, leases
  drawn at random from Q3 2026 intake")

## Next step

Coordinate with brokerage operations to select a representative sample of upcoming or recent
leases and time the existing manual process before this feature's rollout, then record the result
via T041's endpoint. SC-001 ("time drops from baseline to ~10 minutes") cannot be validated until
this is done.
