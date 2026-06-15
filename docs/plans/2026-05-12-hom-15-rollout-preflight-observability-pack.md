# HOM-15 Rollout Preflight Observability Pack for HOM-11

Date: 2026-05-12  
Issue: HOM-15  
Target rollout: HOM-11 (staged rollout path from HOM-14)

## 1. Purpose

Provide a copy/paste-ready observability preflight pack so HOM-11 rollout can be supervised with explicit go/no-go evidence and fast fault triage.

This pack is intentionally minimal and aligned to already-shipped control surfaces:
- `homeassistant/packages/chargectl_production.yaml`
- `homeassistant/packages/chargectl_tariff_sensor.yaml`
- Existing control topics and scripts (`chargectl/control/enabled`, `chargectl/control/max_amps`, emergency hold/stop scripts)

## 2. Preflight Signal Inventory (Must Be Visible Before Go)

Required entities/signals:
- `input_boolean.chargectl_enabled`
- `input_number.chargectl_max_amps`
- MQTT topic `chargectl/control/enabled` (retained)
- MQTT topic `chargectl/control/max_amps` (retained)
- `sensor.grid_tariff_eur_kwh` (for HOM-13 phase)
- `binary_sensor.grid_tariff_data_fresh` (for HOM-13 phase)

Required automations/scripts present in HA:
- Production package startup sync: `chargectl_sync_control_on_ha_start`
- Production package push automations: `chargectl_push_enable_toggle`, `chargectl_push_max_amps`
- Production package cheap-window toggles: `chargectl_night_window_enable`, `chargectl_day_window_disable`
- Production emergency script: `script.chargectl_emergency_stop`
- Tariff package decision automation: `chargectl_tariff_apply_signal`
- Tariff emergency script: `script.chargectl_tariff_emergency_hold`

## 3. Operator Dashboard / Lovelace Checklist

Before rollout, ensure the dashboard contains:
- Enable/disable control (`input_boolean.chargectl_enabled`)
- Max amps control (`input_number.chargectl_max_amps`)
- Current tariff (`sensor.grid_tariff_eur_kwh`) and freshness (`binary_sensor.grid_tariff_data_fresh`)
- Last-change timestamps for control helpers/entities (history graph or entities card)
- One-click emergency action card for `script.chargectl_emergency_stop`

Pass criterion:
- Every signal above can be observed without CLI access from the on-call/operator account.

## 4. Broker-Level Observability Preflight

Verify retained control topics from an MQTT client before enabling automation:

```bash
mosquitto_sub -h <broker_host> -t 'chargectl/control/#' -C 2 -v
```

Expected:
- Both topics appear:
  - `chargectl/control/enabled`
  - `chargectl/control/max_amps`
- Payloads are parseable and match HA helper state.

Failure action:
- Do not proceed with rollout gate execution until retained topics are healthy.

## 5. Preflight Gate Matrix for HOM-11

Gate P0: Safe baseline set
- Set `input_boolean.chargectl_enabled=off`, `input_number.chargectl_max_amps=0`.
- Verify retained MQTT topics reflect the safe baseline.

Gate P1: Manual control propagation
- Toggle enabled on/off and confirm topic + charger behavior align.
- Set max amps (e.g. 8A) and confirm topic + charger clamp align.

Gate P2: Restart durability
- Restart HA and verify startup sync republishes both control topics.
- Confirm post-restart state matches pre-restart helper values.

Gate P3: Package-path specific control logic
- HOM-10 phase: validate cheap-window trigger wiring in supervised run.
- HOM-13 phase: inject cheap/mid/expensive tariff states and verify branch behavior.
- HOM-13 phase: force freshness `off` and verify emergency hold (`enabled=off`, `max_amps=0`).

Go/No-Go rule:
- HOM-11 go requires all P0-P3 gates to pass in order. Any failed gate is automatic no-go and rollback.

## 6. Alerting Recommendations (Minimum)

Configure operator-facing alerts for:
- `binary_sensor.grid_tariff_data_fresh=off` lasting > 5 minutes (HOM-13 phase)
- Control mismatch condition: HA helper state differs from observed retained MQTT payload for > 2 minutes
- Unexpected disabled charging during cheap/normal tariff band (possible logic/config drift)

Severity suggestions:
- Critical: freshness stale during HOM-13 active automation
- Warning: helper/topic mismatch or repeated automation flapping

## 7. Incident Triage Runbook (Fast Path)

1. Immediate safety action:
- Execute `script.chargectl_emergency_stop`.

2. Determine fault domain:
- HA helper state wrong -> operator/config issue
- Helper state correct but MQTT retained payload wrong/missing -> broker/automation publish path
- MQTT retained payload correct but charger behavior wrong -> downstream `chargectl`/charger control path

3. Restore controlled baseline:
- Hold `enabled=off`, `max_amps=0` until root cause isolated.

## 8. Evidence Capturing Template (Attach to HOM-11 Rollout Execution)

For each gate, record:
- Timestamp (UTC/local)
- Operator
- Inputs changed
- Observed HA state
- Observed MQTT retained payload
- Charger observed behavior
- Pass/Fail
- If fail: rollback confirmation time

## 9. Verification Evidence (This Heartbeat)

Local checks executed in `/Users/wouterhermans/Developer/chargectl` on 2026-05-12:

1. Production package control observability wiring present:
- Startup sync + control push automation IDs verified in `homeassistant/packages/chargectl_production.yaml`.

2. Tariff package fault-observability wiring present:
- Freshness + tariff trigger coverage verified in `homeassistant/packages/chargectl_tariff_sensor.yaml`.

3. Automated structural tests available/passing for observability-critical automations:
- `test_gate_c_startup_resync_automation_wired`
- `test_gate_d_cheap_window_time_triggers_wired`
- `test_hom13_tariff_package_has_signal_trigger_wiring`
- `test_hom13_tariff_package_stale_data_uses_emergency_hold`

Command used:

```bash
.venv311/bin/python -m pytest tests/test_homeassistant_package.py -q
```

Result:
- `4 passed`
