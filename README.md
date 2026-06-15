# chargectl

Lightweight EV charger controller for Tesla Wall Connector Gen 2 units.

Controls TWC Gen 2 chargers via RS-485, modulates charging power based on real-time grid measurements (per phase), and integrates with Home Assistant via MQTT auto-discovery.

## Features

- **RS-485 control** — directly commands TWC Gen 2 slaves, no cloud API needed
- **Per-phase power modulation** — prevents main fuse trips by tracking all 3 phases
- **Emergency ramp-down** — instant proportional drop when any phase is overloaded
- **MQTT integration** — subscribes to power measurements, publishes charger status
- **Home Assistant discovery** — auto-creates sensors and controls in HA
- **Watchdog** — stops charging if power measurement data goes stale
- **Works with any EV** — controls the charger hardware, not the car

## How It Works

```
Power meter (CT clamps or P1/DSMR)
  → MQTT → chargectl
             ├── modulation engine (calculates safe amps per phase)
             ├── RS-485 master (sets amperage on TWC slaves)
             └── MQTT status + HA discovery
```

1. Power measurements arrive via MQTT (voltage + power per phase)
2. Modulation engine calculates how many amps are safe to offer
3. RS-485 heartbeats command TWC slaves at the calculated amperage
4. Status is published back to MQTT for monitoring and HA integration

## Quick Start

```bash
pip install .
sudo mkdir -p /etc/chargectl
sudo cp config.example.yaml /etc/chargectl/config.yaml
sudo nano /etc/chargectl/config.yaml
chargectl --config /etc/chargectl/config.yaml
```

See [INSTALL.md](INSTALL.md) for full setup instructions including systemd service.

## Testing (Canonical Path)

Use a local Python 3.11 virtualenv and run the modulation test through the venv interpreter.

```bash
python3.11 -m venv .venv311
.venv311/bin/python -m pip install --upgrade pip
.venv311/bin/python -m pip install -e ".[dev]"
.venv311/bin/python -m pytest tests/test_modulation.py -q
```

Equivalent `make` targets:

```bash
make dev-install
make test-modulation
```

CI mapping:

- GitHub Actions workflow: `.github/workflows/test-modulation.yml`
- CI command: `make ci-test-modulation`

## Configuration

See [config.example.yaml](config.example.yaml) for all options.

Key settings:

| Setting | Description | Default |
|---------|-------------|---------|
| `grid.max_amps_per_phase` | Main fuse rating per phase | 20 |
| `grid.margin_amps` | Safety margin below fuse limit | 3 |
| `rs485.port` | Serial port for RS-485 adapter | /dev/ttyUSB0 |
| `power_source.type` | `rpict4v3` or `dsmr` | rpict4v3 |
| `logging.level` | `info` or `debug` | info |

## MQTT Topics

### Subscribed (power measurements)
Configurable via `power_source.topics` in config.

### Published

| Topic | Description |
|-------|-------------|
| `chargectl/{twc_id}/status` | JSON with amps_actual, amps_offered, state, power_w, voltages |

### Control

| Topic | Payload | Description |
|-------|---------|-------------|
| `chargectl/control/max_amps` | integer | Override max amps per phase |
| `chargectl/control/enabled` | `on`/`off` | Enable or disable charging |

## Home Assistant

chargectl publishes MQTT auto-discovery messages. After starting, HA will automatically show:

- **Sensors**: amps actual, amps offered, power, state, voltage per phase (per TWC)
- **Controls**: max amps (number), charging enabled (via MQTT)

Production automation package for scheduler/control hardening:

- Package file: `homeassistant/packages/chargectl_production.yaml`
- Deployment/validation runbook: `docs/plans/2026-05-12-hom-10-ha-automation-package.md`
- Includes HA-side `script.chargectl_emergency_stop` for one-action disable + `max_amps=0`

Tariff-sensor-driven variant (live price feed, fail-safe on stale data):

- Package file: `homeassistant/packages/chargectl_tariff_sensor.yaml`
- Deployment/validation runbook: `docs/plans/2026-05-12-hom-13-tariff-sensor-ha-automation-package.md`

## Hardware Requirements

- Raspberry Pi (or any Linux box)
- USB-to-RS-485 adapter (CP2102 or similar, ~$5)
- TWC Gen 2 set to position F (slave mode)
- RS-485 wiring: D+ to D+, D- to D-
- MQTT broker (Mosquitto)
- Power measurement source publishing to MQTT

## License

MIT
