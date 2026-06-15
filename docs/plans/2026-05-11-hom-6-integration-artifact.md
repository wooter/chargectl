# HOM-6 First-Pass Integration Artifact

Date: 2026-05-11
Issue: HOM-6 Integrate Charging Station Control With Power Monitoring Signals

## 1. Control Flow

1. `powerpi` publishes per-phase power and voltage measurements to MQTT topics (`RPICT4V3/RP1..RP3`, `RPICT4V3/Vrms1..Vrms3`).
2. `garagepi` runs `chargectl` and subscribes to those power topics.
3. Every control cycle, `chargectl` reads the latest measurements and computes available amps from worst phase utilization.
4. `chargectl` derives a total desired charging current and allocates per-charger offered current.
5. `chargectl` sends RS-485 heartbeat commands to TWC Gen 2 slaves (round-robin) with allocated amps.
6. `chargectl` publishes charger status and telemetry to MQTT (`chargectl/<slave_id>/status`).
7. Optional operator override path: Home Assistant or scripts publish to `chargectl/control/max_amps` and `chargectl/control/enabled`.
8. Safety path: if power telemetry becomes stale, watchdog forces `desired_amps=0`; if charging is disabled, modulation remains pinned to `0` until re-enabled.

## 2. Required Inputs / Entities

Runtime nodes
- `powerpi`: MQTT producer for phase power/voltage telemetry.
- `garagepi`: MQTT consumer + RS-485 charger controller host.
- `MQTT broker`: shared transport between telemetry and control.

Topics
- Telemetry in:
- `RPICT4V3/RP1`, `RPICT4V3/RP2`, `RPICT4V3/RP3` (W)
- `RPICT4V3/Vrms1`, `RPICT4V3/Vrms2`, `RPICT4V3/Vrms3` (V)
- Control in:
- `chargectl/control/max_amps` (integer per-phase cap)
- `chargectl/control/enabled` (disabled only for `false|0|off`, case-insensitive)
- Status out:
- `chargectl/<slave_id>/status` JSON
- Home Assistant discovery out:
- `homeassistant/sensor/chargectl_<slave_id>_<metric>/config` (retained)

Configuration entities
- Grid limits: `max_amps_per_phase`, `margin_amps`
- RS-485 serial settings: `port`, `baud`
- Charger calibration map (optional): `chargers.<id>.kwh_real`, `kwh_counter`

Internal control entities
- `ModulationEngine.desired_amps`
- `ModulationEngine.enabled` (sticky enable/disable gate)
- `last_data_time` watchdog timestamp
- Per-slave state (`CHARGING`, `STARTING`, `PLUGGED_READY`, etc.)

## 3. Automation / Scheduler Pseudocode

```python
# garagepi process loop (chargectl)
init_mqtt()
init_rs485_master()
engine = ModulationEngine(max_amps, margin_amps)

on_mqtt_control(command, value):
    if command == "max_amps":
        engine.max_amps = int(value)
    elif command == "enabled":
        engine.set_enabled(value not in ["false", "0", "off"])

while running:
    messages = rs485.read_and_process()
    update_slave_state(messages)
    publish_slave_status(messages)

    if cycle_start:
        power, voltage = mqtt.get_measurements()
        desired = engine.calculate(power, voltage)
        allocation = allocate_across_slaves(desired, slave_states)

    if heartbeat_due:
        send_heartbeat_to_next_slave(allocation)

    if power_poll_due:
        request_power_status_from_slaves()

    sleep(25ms)
```

Example `systemd` timer fallback (if process-level scheduling is split):

```ini
# /etc/systemd/system/chargectl.service
[Unit]
Description=Charge controller
After=network-online.target

[Service]
ExecStart=/usr/local/bin/chargectl --config /etc/chargectl/config.yaml
Restart=always
RestartSec=2

[Install]
WantedBy=multi-user.target
```

```ini
# Optional watchdog restart policy already handled by Restart=always;
# no extra cron needed for main control loop.
```

## 4. Minimal Simulated Verification Checklist

1. Telemetry ingest
- Publish simulated nominal telemetry (all three power + voltage topics).
- Confirm `chargectl` logs show modulation calculations and no missing-data warnings.

2. Ramp-up behavior
- Simulate low household load (high free amps).
- Confirm `desired_amps` ramps up gradually and TWC offered amps increase.

3. Ramp-down behavior
- Simulate high load on one phase only.
- Confirm worst phase drives down `desired_amps` and offered amps reduce.

4. Emergency clamp
- Simulate overload (`free_amps < 0`).
- Confirm immediate emergency drop in logs and lower offered current next heartbeat.

5. Disable/enable sticky control gate
- Publish `chargectl/control/enabled=off`.
- Confirm `desired_amps` stays at `0` even with favorable telemetry.
- Publish `chargectl/control/enabled=on`.
- Confirm ramp-up resumes from zero.

6. Watchdog safety
- Stop publishing telemetry for >15s.
- Confirm watchdog forces `desired_amps=0` and charging commands clamp accordingly.

7. Status publication
- Confirm `chargectl/<slave_id>/status` updates include `state`, `amps_actual`, `amps_offered`, `power_w`, and voltages.

## 5. Linked Sub-Deliverable

- HOM-7 entity/signal mapping table:
- `docs/plans/2026-05-11-hom-7-entity-signal-mapping.md`

## 6. Completion Traceability

Delivered against HOM-6 objective:
- Proposed control flow: Section 1
- Required entities/inputs: Section 2
- Automation/pseudocode/YAML: Section 3
- Minimal simulated verification checklist: Section 4
- Entity/signal mapping child artifact (HOM-7): Section 5

Implementation progress completed in code:
- Sticky charging enable/disable gate added in modulation engine.
- MQTT control path updated for explicit enable/disable behavior.
- Regression tests added for disable/reenable behavior.

Recommended issue transition:
- Move HOM-6 to `in_review` now.

## 7. Runtime Validation Result

Final gate command executed in local Python 3.11 venv:

```bash
.venv311/bin/python -m pytest tests/test_modulation.py -q
```

Outcome:
- `25 passed in 0.01s`

Closure recommendation:
- HOM-6 can move from `in_review` to `done`.
