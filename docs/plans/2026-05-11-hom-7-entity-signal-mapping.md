# HOM-7 Entity/Signal Mapping Table

Date: 2026-05-11
Parent: HOM-6 Integrate Charging Station Control With Power Monitoring Signals
Child: HOM-7 Entity/signal mapping artifact

## Mapping Table

| Source Entity | Source Signal / Topic | Type | Unit | Direction | Target Entity | Target Field / Effect | Validation Rule | Fallback / Failure Behavior |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `powerpi` RPICT4V3 | `RPICT4V3/RP1` | float | W | MQTT -> `garagepi` | `ChargeMQTT.power_data` | `power_phase1` | parse as float | keep previous value; watchdog may stop charging when data stale |
| `powerpi` RPICT4V3 | `RPICT4V3/RP2` | float | W | MQTT -> `garagepi` | `ChargeMQTT.power_data` | `power_phase2` | parse as float | keep previous value; watchdog may stop charging when data stale |
| `powerpi` RPICT4V3 | `RPICT4V3/RP3` | float | W | MQTT -> `garagepi` | `ChargeMQTT.power_data` | `power_phase3` | parse as float | keep previous value; watchdog may stop charging when data stale |
| `powerpi` RPICT4V3 | `RPICT4V3/Vrms1` | float | V | MQTT -> `garagepi` | `ChargeMQTT.power_data` | `voltage_phase1` | parse as float, `>0` preferred | zero/invalid voltage treated as 0A contribution for that phase |
| `powerpi` RPICT4V3 | `RPICT4V3/Vrms2` | float | V | MQTT -> `garagepi` | `ChargeMQTT.power_data` | `voltage_phase2` | parse as float, `>0` preferred | zero/invalid voltage treated as 0A contribution for that phase |
| `powerpi` RPICT4V3 | `RPICT4V3/Vrms3` | float | V | MQTT -> `garagepi` | `ChargeMQTT.power_data` | `voltage_phase3` | parse as float, `>0` preferred | zero/invalid voltage treated as 0A contribution for that phase |
| Operator (HA/script) | `chargectl/control/max_amps` | int | A | MQTT -> `garagepi` | `ModulationEngine` | update `max_amps` cap | `int(value)` must succeed | invalid payload ignored |
| Operator (HA/script) | `chargectl/control/enabled` | string bool-ish (`on/off`, `true/false`, `1/0`) | n/a | MQTT -> `garagepi` | `ModulationEngine` | `set_enabled(bool)` sticky gate | lowercased; only `false`, `0`, `off` map to disabled | when disabled, modulation is pinned to `desired_amps=0` until re-enabled |
| `ModulationEngine` | `desired_amps` | int | A total | in-process | allocation routine | per-slave offered amps | clamp `0..(max_amps-margin)` with TWC min semantics | if no telemetry for watchdog window, forced `0` |
| `TWCMaster` / TWC slave heartbeat | RS-485 heartbeat frame | binary | encoded amps | `garagepi` -> chargers | TWC Gen 2 slave | offered current command | protocol framing + checksum | stale/unresponsive slave removed from rotation |
| TWC Gen 2 slave | heartbeat response | binary decoded | A, state | chargers -> `garagepi` | `TWCSlave` state | `state`, `amps_actual`, `amps_offered` | decode by protocol parser | ignore malformed frames |
| TWC Gen 2 slave | power status response | binary decoded | kWh, V | chargers -> `garagepi` | status publisher | `lifetime_kwh`, `volts_phase_*` | decode by protocol parser | keep previous telemetry if missing |
| `garagepi` (`chargectl`) | `chargectl/<slave_id>/status` | JSON | mixed | MQTT out | Home Assistant / observability | charger telemetry + state | valid JSON payload | last retained value remains until next publish |
| `garagepi` (`chargectl`) | `homeassistant/sensor/chargectl_<slave_id>_{metric}/config` | JSON | mixed | MQTT out | Home Assistant MQTT discovery | sensor registration (`amps_actual`, `amps_offered`, `power_w`, `state`, `volts_phase_[a|b|c]`) | valid JSON payload with `state_topic` + `value_template` | retained discovery state stays until replaced/cleared |

## Notes

- Control is driven by worst-phase current (`max(power/voltage)`), not average phase load.
- `enabled=off` is sticky by design and cannot be overridden by favorable power telemetry.
- Existing charging sessions may continue at protocol-safe minimum current where required by TWC Gen 2 behavior.
- Status and HA discovery MQTT publishes are retained, so Home Assistant can restore entities and latest state after restart.

## Code Verification Pointers

- Control message parse and command semantics: `chargectl/__main__.py` (`on_control`) + `chargectl/mqtt_client.py` (`_handle_control`).
- Discovery topic shape and value templates: `chargectl/mqtt_client.py` (`build_ha_discovery`).
- Status topic payload shape and retained publish: `chargectl/__main__.py` (`status` dict) + `chargectl/mqtt_client.py` (`publish_status`).
- Watchdog and worst-phase modulation behavior: `chargectl/modulation.py` (`calculate`, `WATCHDOG_TIMEOUT`).
