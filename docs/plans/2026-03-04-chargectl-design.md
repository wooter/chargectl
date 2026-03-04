# chargectl — Design Document

## Problem

Three Raspberry Pis (powerpi, officepi, garagepi) running a fragile chain of RPICT4V3 CT clamps → MQTT → Node-RED → TWCManager to modulate EV charging on two Tesla Wall Connector Gen 2 units. The current system:

- Has a modulation algorithm too slow to prevent 20A main fuse trips
- Cannot reliably stop charging (Tesla API tokens are empty, chargeStopMode 1 is broken)
- Uses Node-RED for a single function node (overkill)
- Uses TWCManager for RS-485 heartbeats (overkill, 3400+ lines for what needs ~150)
- Has three points of failure across three networked devices
- A digital P1 meter is coming and needs to be a drop-in replacement for the CT clamps

## Solution

A single Python application (`chargectl`) running on garagepi that replaces both Node-RED and TWCManager. It handles RS-485 communication with TWC slaves, subscribes to MQTT for power measurements, and runs a modulation algorithm to keep per-phase amperage under the main fuse limit.

## Architecture

```
Power source (powerpi now, P1 meter later)
  → MQTT → chargectl (garagepi)
             ├── modulation engine (calculates safe amps)
             ├── RS-485 master (commands TWC slaves)
             └── MQTT status + HA discovery (sensors, controls)
```

## Configuration

Single YAML file at `/etc/chargectl/config.yaml`:

```yaml
mqtt:
  broker: localhost
  port: 1883

rs485:
  port: /dev/ttyUSB0
  baud: 9600

grid:
  max_amps_per_phase: 20
  margin_amps: 3

power_source:
  type: rpict4v3  # or "dsmr" when P1 arrives
  topics:
    power_phase1: "RPICT4V3/RP1"
    power_phase2: "RPICT4V3/RP2"
    power_phase3: "RPICT4V3/RP3"
    voltage_phase1: "RPICT4V3/Vrms1"
    voltage_phase2: "RPICT4V3/Vrms2"
    voltage_phase3: "RPICT4V3/Vrms3"

logging:
  level: info  # "debug" for raw RS-485 frames and MQTT messages
```

## RS-485 Protocol

- 9600 baud, 8N1, half-duplex
- SLIP framing (0xC0 delimiters, escape 0xC0/0xDB in body)
- 1-byte checksum (sum of bytes 1..N-1, & 0xFF)
- Master heartbeat (0xFBE0) sent every ~1 second per slave
- Slave heartbeat (0xFDE0) response contains state, max amps, actual amps
- Protocol v2: command 0x09 to set amps mid-charge, 0x05 with 0A to stop cleanly
- Min 5 seconds between amperage changes
- TWC hardware minimum: 6A (below that → set 0)

## Modulation Algorithm

- Tracks all 3 phases independently
- `free_amps = max_amps - worst_phase_amps - margin`
- Emergency: instant proportional drop when free < 0
- Normal: ramp down 1A when free < 2, ramp up 1A when free > 4
- Floor: either >= 6A or 0A
- Watchdog: no measurement data for 15 seconds → set 0A
- Start at 0A on boot, ramp up from there

## Home Assistant Integration

MQTT auto-discovery publishes config so HA sees:

- **Sensors**: per-TWC amps actual, amps offered, state, voltage per phase, total power
- **Number entity**: max charge amps (adjustable from HA)
- **Switch entity**: charging enabled/disabled per TWC

HomeKit access via HA's HomeKit bridge.

## Logging

Python `logging` module to stdout. `INFO` level by default (startup, connections, amp changes, errors). `DEBUG` for raw RS-485 frames and MQTT messages. No file logging — systemd journal handles storage and rotation.

## Project Structure

```
chargectl/
├── chargectl/
│   ├── __init__.py
│   ├── __main__.py        # entry point
│   ├── config.py          # YAML config loading
│   ├── rs485.py           # TWC RS-485 protocol (~150 lines)
│   ├── modulation.py      # power modulation algorithm (~50 lines)
│   ├── mqtt_client.py     # MQTT subscribe + publish + HA discovery
│   └── charger.py         # TWC slave state management
├── config.example.yaml
├── pyproject.toml
├── README.md
└── tests/
```

## Dependencies

- `paho-mqtt` — MQTT client
- `pyserial` — serial/RS-485 communication
- `pyyaml` — configuration

## Explicit Non-Goals

- No web UI (use HA dashboard)
- No Tesla API (controls physical charger via RS-485, works with any EV)
- No scheduling (use HA automations)
- No database (use HA history or external InfluxDB)
- No policy engine (single algorithm, configurable via YAML + MQTT)
