# HOM-10 Production HA Automation Package

Date: 2026-05-12
Issue: HOM-10 Implement production-ready HA automation package from HOM-6/HOM-7 artifacts
Dependencies: HOM-6 integration artifact, HOM-7 entity/signal mapping table

## 1. Deliverable

Production-ready Home Assistant package file:
- `homeassistant/packages/chargectl_production.yaml`

What it provides:
- Persistent HA-side control helpers for `max_amps` and `enabled`
- MQTT publish automations to `chargectl/control/max_amps` and `chargectl/control/enabled`
- Start-up resync automation (HA restart re-pushes the last known control state)
- Cheap-tariff window toggles (time-based enable/disable)
- Small operator script for one-call eco cap changes
- Emergency-stop operator script (`script.chargectl_emergency_stop`)

## 2. Mapping Back to HOM-6/HOM-7

Directly uses mapped control topics from HOM-7:
- `chargectl/control/max_amps`
- `chargectl/control/enabled`

Respects HOM-6 control semantics:
- `enabled=off` acts as sticky disable gate
- Operator override is explicit and retained in MQTT
- No scheduler embedded in `chargectl`; HA owns schedule logic

## 3. Installation

1. Ensure HA packages are enabled in `configuration.yaml`:

```yaml
homeassistant:
  packages: !include_dir_named packages
```

2. Copy package:

```bash
cp homeassistant/packages/chargectl_production.yaml \
  /config/packages/chargectl_production.yaml
```

3. In HA UI, set helper defaults:
- `input_number.chargectl_max_amps`: your safe day baseline (example `12`)
- `input_boolean.chargectl_enabled`: desired startup state
- `input_datetime.chargectl_cheap_start`: cheap-window start
- `input_datetime.chargectl_cheap_end`: cheap-window end

4. Reload package/restart HA.

## 4. Supervised Rollout Guardrails

Preflight (before enabling automations):
1. Confirm chargectl process is healthy and receiving fresh power telemetry.
2. Confirm physical/electrical limits in `/etc/chargectl/config.yaml` remain conservative:
   - `grid.max_amps_per_phase` matches main breaker/fuse rating
   - `grid.margin_amps` keeps a safety headroom (non-zero)
3. In HA, set:
   - `input_boolean.chargectl_enabled` = `off`
   - `input_number.chargectl_max_amps` = conservative baseline (example `8`)
4. Confirm both retained MQTT control topics exist and are writable.

Rollout gates (must pass in order):
1. Gate A: manual disable/enable works and charger obeys within normal control latency.
2. Gate B: low max-amps clamp works at conservative value.
3. Gate C: HA restart resync restores intended control state.
4. Gate D: cheap-window automation toggles as configured.

If any gate fails, execute rollback in Section 6 before continuing.

## 5. Minimal Production Validation

1. Manual disable safety gate
- Turn `input_boolean.chargectl_enabled` off.
- Verify MQTT publish to `chargectl/control/enabled` payload `off`.
- Verify charger current drops to zero/min-safe behavior as defined by TWC protocol.

2. Manual re-enable
- Turn `input_boolean.chargectl_enabled` on.
- Verify payload `on` and normal ramp-up resumes.

3. Max-amps override
- Set `input_number.chargectl_max_amps` to a low value (example `8`).
- Verify payload appears on `chargectl/control/max_amps`.
- Confirm offered current clamps accordingly.

4. HA restart resync
- Restart HA.
- Verify both retained control messages are republished on startup.
- Confirm `chargectl` behavior remains aligned with helper states.

5. Window automation
- Temporarily set cheap start/end near current time.
- Verify enable at start and disable at end.

## 6. Rollback Procedure

Immediate safe rollback (operator action):
1. Run `script.chargectl_emergency_stop` in HA.
2. Verify:
   - `input_boolean.chargectl_enabled` is `off`
   - `input_number.chargectl_max_amps` is `0`
   - MQTT retained control messages reflect that safe state.

Package rollback:
1. Remove or rename `/config/packages/chargectl_production.yaml`.
2. Reload HA automations/scripts or restart HA.
3. Ensure no `chargectl:` package automations/scripts remain loaded.

Control-plane fallback:
1. Keep `chargectl` running with built-in physical guardrails.
2. If needed, publish a fixed safe control baseline to control topics from your existing operator tooling.

## 7. Operational Notes

- Keep `retain: true` on control topics to avoid state drift across HA or broker restarts.
- Keep safe physical guardrails in `chargectl` config (`max_amps_per_phase`, `margin_amps`) even when HA automations are active.
- If tariff integration is available later, replace fixed time triggers with tariff-state triggers while reusing the same control helpers.

## 8. Execution Evidence (This Heartbeat)

Executed on 2026-05-12 in local dev environment (`/Users/wouterhermans/Developer/chargectl`):

1. Gate A (manual disable/enable semantics) executed in simulation:
   - Test: `test_hom10_gate_manual_disable_enable_semantics`
   - Result: pass (`enabled=off` forces `desired_amps=0`; `enabled=on` re-enables control)
2. Gate B (max-amps override semantics) executed in simulation:
   - Test: `test_hom10_gate_max_amps_override_semantics`
   - Result: pass (`max_amps=8` accepted; invalid payload rejected)
3. Package syntax check:
   - Command: `ruby -ryaml -e 'YAML.load_file("homeassistant/packages/chargectl_production.yaml")'`
   - Result: pass
4. Gate C (HA startup resync wiring) executed in simulation:
   - Test: `test_gate_c_startup_resync_automation_wired`
   - Result: pass (startup trigger and both control-topic republishes present)
5. Gate D (cheap-window time trigger wiring) executed in simulation:
   - Test: `test_gate_d_cheap_window_time_triggers_wired`
   - Result: pass (start/end time triggers mapped to enable/disable automations)

Command transcript summary:
- `.venv311/bin/python -m pytest tests/test_main.py tests/test_homeassistant_package.py -q` -> `8 passed`
- YAML parse -> `YAML OK`

Live HA execution remains a deployment-time confirmation step on target environment; simulation gates for C/D are now covered by automated package-structure tests.
