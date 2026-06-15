# HOM-14 Rollout Decision Matrix (HOM-10 vs HOM-13)

Date: 2026-05-12  
Issue: HOM-14  
Decision owner: CEO / project lead

## HOM-11 Copy/Paste Decision Input

**Recommended first rollout choice: HOM-10 first, HOM-13 second (staged).**

Rationale:
- **Operational risk:** HOM-10 has fewer external dependencies (no tariff-feed freshness dependency), so day-1 behavior is easier to predict and supervise.
- **Rollback simplicity:** HOM-10 rollback is straightforward to fixed windows and existing retained control topics; HOM-13 adds tariff freshness/threshold failure modes that complicate incident triage.
- **Execution safety:** sequencing HOM-10 before HOM-13 avoids validating new control logic and tariff data quality at the same time.

Decision statement:
- Approve staged rollout path: launch HOM-10 as production baseline, then promote HOM-13 only after tariff readiness gates pass.

## Weighted Comparison

Scoring: 1 = weak/high risk, 5 = strong/low risk.

| Criterion | Weight | HOM-10 | HOM-13 | Notes |
|---|---:|---:|---:|---|
| Operational simplicity (day-1) | 25% | 5 | 3 | HOM-13 adds freshness + threshold tuning. |
| External dependency risk | 20% | 5 | 2 | HOM-13 depends on tariff data quality. |
| Safety predictability under faults | 20% | 4 | 4 | Both fail-safe; HOM-13 fails closed on stale data. |
| Cost optimization potential | 20% | 2 | 5 | HOM-13 can react to real prices. |
| Tuning/maintenance overhead | 15% | 4 | 2 | HOM-13 needs threshold governance. |

Weighted total (max 5.0):
- **HOM-10: 4.10**
- **HOM-13: 3.20**

## Go/No-Go Gates

### HOM-10 Go
1. Supervised rollout gates passed in target HA environment.
2. Emergency stop and rollback runbook operator-verified.
3. No charging drift across HA restart and MQTT broker restart.

### HOM-13 Promotion (after HOM-10 baseline)
1. Tariff freshness signal is reliable and monitored.
2. Tariff values are stable (no frequent `unknown/unavailable` flapping).
3. Tariff decision and stale-data fail-closed gates pass.
4. Thresholds and amps profiles are documented and signed off.
