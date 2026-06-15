# HOM-16 Pre-Authored Execution Branches for HOM-14 Outcomes

Date: 2026-05-12  
Issue: HOM-16  
Purpose: enable immediate HOM-11 execution once HOM-14 rollout path decision is approved.

## 1. How To Use This

1. Copy the branch that matches the approved HOM-14 decision.
2. Paste it into HOM-11 as the active rollout path.
3. Execute gates in order; any failed gate is automatic no-go with rollback.

## 2. Branch A (Recommended): HOM-10 First, HOM-13 Second

Decision trigger:
- HOM-14 approved with staged path: launch HOM-10 baseline first.

Execution steps:
1. Apply HOM-10 package: `homeassistant/packages/chargectl_production.yaml`.
2. Run preflight observability checks from HOM-15 before enabling automation.
3. Execute HOM-10 supervised gates (A-D) and capture evidence per gate.
4. Keep HOM-10 as production baseline for soak period.
5. In parallel, validate tariff feed quality/freshness monitoring for HOM-13 readiness.
6. Promote to HOM-13 only after all promotion gates pass.

Go criteria:
- HOM-10 gates pass with no state drift across HA/broker restarts.
- Emergency stop path operator-verified.

No-go/rollback criteria:
- Any gate failure, retained-topic mismatch, or unstable control behavior.
- Roll back to safe baseline: `enabled=off`, `max_amps=0`.

Owner decision checkpoint after soak:
- Confirm HOM-13 promotion readiness based on tariff stability evidence.

## 3. Branch B: Direct HOM-13 Rollout

Decision trigger:
- HOM-14 approved for direct tariff-sensor rollout.

Execution steps:
1. Apply HOM-13 package: `homeassistant/packages/chargectl_tariff_sensor.yaml`.
2. Run HOM-15 preflight plus tariff-specific checks:
- freshness sensor health,
- low `unknown/unavailable` rate,
- threshold profile sign-off.
3. Execute supervised tariff decision tests:
- cheap tariff branch,
- mid tariff branch,
- expensive tariff branch,
- stale-data fail-closed branch.
4. Monitor for oscillation/flapping during controlled window.

Go criteria:
- All tariff branch behaviors match expected outputs.
- Stale data always forces emergency hold (`enabled=off`, `max_amps=0`).

No-go/rollback criteria:
- Freshness dropouts, threshold ambiguity, or oscillating control behavior.
- Immediate rollback to safe baseline and suspend tariff autonomy.

## 4. Shared Safety Rules (Both Branches)

- Emergency action is always available: `script.chargectl_emergency_stop`.
- Retained MQTT control topics must remain authoritative and in sync:
- `chargectl/control/enabled`
- `chargectl/control/max_amps`
- Any helper/topic mismatch persisting over 2 minutes is a no-go signal.
- Do not continue rollout when safe baseline cannot be re-established quickly.

## 5. HOM-11 Copy/Paste Branch Selector

Use exactly one of the following in HOM-11 execution notes:

- `Selected branch: A (HOM-10 first, HOM-13 second)`
- `Selected branch: B (Direct HOM-13 rollout)`

Required fields to record:
- Decision approver
- Decision timestamp
- Selected branch
- Gate-by-gate pass/fail evidence
- Rollback actions (if any)

## 6. Deliverable

This document pre-authors both execution branches so HOM-11 can proceed immediately after HOM-14 approval without additional planning delay.
