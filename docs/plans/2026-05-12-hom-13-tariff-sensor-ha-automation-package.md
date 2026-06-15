# HOM-13 Tariff-Sensor HA Automation Package

Date: 2026-05-12  
Issue: HOM-13 Build tariff-sensor-driven variant of HA charging automation package  
Safety model: aligned with HOM-10 rollout gates and emergency-stop posture

## 1. Deliverable

New package variant:
- `homeassistant/packages/chargectl_tariff_sensor.yaml`

This variant keeps the same control topics and guardrails as HOM-10 but replaces fixed clock windows with live tariff signals.

## 2. Required Sensor Semantics

This package expects these entities to exist in HA:
- `sensor.grid_tariff_eur_kwh`
  - Current tariff as numeric EUR/kWh (stringified numeric HA state is fine).
- `binary_sensor.grid_tariff_data_fresh`
  - `on` when tariff feed is fresh and trustworthy.
  - `off` when stale/missing/downstream feed unhealthy.

Control helpers used by package:
- `input_boolean.chargectl_tariff_automation_enabled`
- `input_number.chargectl_tariff_cheap_threshold`
- `input_number.chargectl_tariff_expensive_threshold`
- `input_number.chargectl_tariff_cheap_amps`
- `input_number.chargectl_tariff_normal_amps`
- existing `input_boolean.chargectl_enabled` and `input_number.chargectl_max_amps`

## 3. Behavior + Guardrails

When automation is enabled:
1. If tariff freshness is not `on`: force emergency hold (`enabled=off`, `max_amps=0`).
2. If tariff sensor state is `unknown`/`unavailable`/empty: force emergency hold.
3. If tariff `<= cheap_threshold`: enable charging and set cheap amps.
4. If tariff `>= expensive_threshold`: force emergency hold.
5. Else (mid band): keep charging enabled and set normal amps.

Guardrail notes:
- MQTT `retain: true` is preserved for `chargectl/control/enabled` and `chargectl/control/max_amps`.
- HA restart resync automation is retained.
- Emergency hold script remains available for operator/manual invocations.

## 4. Installation

1. Ensure HA packages support is configured:

```yaml
homeassistant:
  packages: !include_dir_named packages
```

2. Copy package:

```bash
cp homeassistant/packages/chargectl_tariff_sensor.yaml \
  /config/packages/chargectl_tariff_sensor.yaml
```

3. Configure initial values in HA UI:
- `input_boolean.chargectl_tariff_automation_enabled`: `off` initially
- `input_number.chargectl_tariff_cheap_threshold`: e.g. `0.18`
- `input_number.chargectl_tariff_expensive_threshold`: e.g. `0.35`
- `input_number.chargectl_tariff_cheap_amps`: conservative e.g. `12`
- `input_number.chargectl_tariff_normal_amps`: conservative e.g. `8`

4. Reload packages/restart HA, verify entities, then enable tariff automation.

## 5. Verification Checklist (HOM-10 Safety Aligned)

1. Gate A equivalent: toggle `input_boolean.chargectl_enabled` manually and confirm MQTT control topic follows.
2. Gate B equivalent: set `input_number.chargectl_max_amps` manually and verify clamp behavior.
3. Gate C equivalent: restart HA and verify control state republish on startup.
4. Tariff decision gate:
- Feed cheap tariff value and verify enable + cheap amps.
- Feed mid tariff value and verify enable + normal amps.
- Feed expensive tariff value and verify emergency hold.
5. Freshness fault gate:
- Set `binary_sensor.grid_tariff_data_fresh` to `off` and confirm emergency hold.
- Restore freshness and confirm normal tariff-driven control resumes.

## 6. Fallback Behavior

Fallback is fail-safe: missing/stale tariff data always drives the system to disabled charging with `max_amps=0` until valid fresh data returns.

## 7. Execution Evidence (This Heartbeat)

- Added package: `homeassistant/packages/chargectl_tariff_sensor.yaml`.
- Added package tests in `tests/test_homeassistant_package.py` for tariff trigger and stale-data guardrails.
- Ran targeted tests for package structure and wiring.
