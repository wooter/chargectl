# chargectl Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a standalone Python tool that controls Tesla Wall Connector Gen 2 units via RS-485, modulates charging based on MQTT power measurements, and integrates with Home Assistant via MQTT discovery.

**Architecture:** Single Python package with four modules: RS-485 protocol (SLIP framing + TWC heartbeats), modulation engine (per-phase amp calculation), MQTT client (subscribe to power data, publish status + HA discovery), and charger state management (track TWC slaves). One main loop ties them together.

**Tech Stack:** Python 3.11+, paho-mqtt, pyserial, pyyaml, pytest

---

### Task 1: Project scaffolding

**Files:**
- Create: `pyproject.toml`
- Create: `chargectl/__init__.py`
- Create: `config.example.yaml`
- Create: `.gitignore`

**Step 1: Create pyproject.toml**

```toml
[build-system]
requires = ["setuptools>=68.0"]
build-backend = "setuptools.backends._legacy:_Backend"

[project]
name = "chargectl"
version = "0.1.0"
description = "Lightweight EV charger controller for Tesla Wall Connector Gen 2 via RS-485"
readme = "README.md"
requires-python = ">=3.11"
license = "MIT"
dependencies = [
    "paho-mqtt>=2.0",
    "pyserial>=3.5",
    "pyyaml>=6.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-cov>=5.0",
]

[project.scripts]
chargectl = "chargectl.__main__:main"
```

**Step 2: Create chargectl/__init__.py**

```python
"""chargectl - Lightweight EV charger controller."""

__version__ = "0.1.0"
```

**Step 3: Create config.example.yaml**

```yaml
mqtt:
  broker: localhost
  port: 1883
  # username: ""
  # password: ""

rs485:
  port: /dev/ttyUSB0
  baud: 9600

grid:
  max_amps_per_phase: 20
  margin_amps: 3

power_source:
  # Supported types: rpict4v3, dsmr
  type: rpict4v3
  topics:
    power_phase1: "RPICT4V3/RP1"
    power_phase2: "RPICT4V3/RP2"
    power_phase3: "RPICT4V3/RP3"
    voltage_phase1: "RPICT4V3/Vrms1"
    voltage_phase2: "RPICT4V3/Vrms2"
    voltage_phase3: "RPICT4V3/Vrms3"

logging:
  level: info
```

**Step 4: Create .gitignore**

```
__pycache__/
*.pyc
*.egg-info/
dist/
build/
.venv/
*.log
config.yaml
```

**Step 5: Commit**

```bash
git add pyproject.toml chargectl/__init__.py config.example.yaml .gitignore
git commit -m "feat: project scaffolding with pyproject.toml and example config"
```

---

### Task 2: Config loading

**Files:**
- Create: `chargectl/config.py`
- Create: `tests/test_config.py`

**Step 1: Write the failing test**

```python
# tests/test_config.py
import tempfile
import os
import pytest
from chargectl.config import load_config

MINIMAL_CONFIG = """
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
  type: rpict4v3
  topics:
    power_phase1: "RPICT4V3/RP1"
    power_phase2: "RPICT4V3/RP2"
    power_phase3: "RPICT4V3/RP3"
    voltage_phase1: "RPICT4V3/Vrms1"
    voltage_phase2: "RPICT4V3/Vrms2"
    voltage_phase3: "RPICT4V3/Vrms3"
"""


def test_load_config_from_file():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(MINIMAL_CONFIG)
        f.flush()
        cfg = load_config(f.name)
    os.unlink(f.name)
    assert cfg.mqtt_broker == "localhost"
    assert cfg.mqtt_port == 1883
    assert cfg.rs485_port == "/dev/ttyUSB0"
    assert cfg.rs485_baud == 9600
    assert cfg.max_amps_per_phase == 20
    assert cfg.margin_amps == 3
    assert cfg.power_source_type == "rpict4v3"
    assert cfg.power_topics["power_phase1"] == "RPICT4V3/RP1"
    assert cfg.log_level == "info"  # default


def test_load_config_missing_file():
    with pytest.raises(FileNotFoundError):
        load_config("/nonexistent/config.yaml")


def test_load_config_with_logging():
    config_with_logging = MINIMAL_CONFIG + "\nlogging:\n  level: debug\n"
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(config_with_logging)
        f.flush()
        cfg = load_config(f.name)
    os.unlink(f.name)
    assert cfg.log_level == "debug"
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/wouterhermans/Developer/chargectl && python -m pytest tests/test_config.py -v`
Expected: FAIL with ModuleNotFoundError

**Step 3: Write minimal implementation**

```python
# chargectl/config.py
"""Configuration loading from YAML."""

from dataclasses import dataclass, field
from pathlib import Path
import yaml


@dataclass
class Config:
    mqtt_broker: str
    mqtt_port: int
    mqtt_username: str | None
    mqtt_password: str | None
    rs485_port: str
    rs485_baud: int
    max_amps_per_phase: int
    margin_amps: int
    power_source_type: str
    power_topics: dict[str, str]
    log_level: str


def load_config(path: str) -> Config:
    """Load configuration from a YAML file."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    with open(p) as f:
        raw = yaml.safe_load(f)

    mqtt = raw.get("mqtt", {})
    rs485 = raw.get("rs485", {})
    grid = raw.get("grid", {})
    power = raw.get("power_source", {})
    logging_cfg = raw.get("logging", {})

    return Config(
        mqtt_broker=mqtt.get("broker", "localhost"),
        mqtt_port=mqtt.get("port", 1883),
        mqtt_username=mqtt.get("username"),
        mqtt_password=mqtt.get("password"),
        rs485_port=rs485.get("port", "/dev/ttyUSB0"),
        rs485_baud=rs485.get("baud", 9600),
        max_amps_per_phase=grid.get("max_amps_per_phase", 20),
        margin_amps=grid.get("margin_amps", 3),
        power_source_type=power.get("type", "rpict4v3"),
        power_topics=power.get("topics", {}),
        log_level=logging_cfg.get("level", "info"),
    )
```

**Step 4: Run test to verify it passes**

Run: `cd /Users/wouterhermans/Developer/chargectl && python -m pytest tests/test_config.py -v`
Expected: 3 passed

**Step 5: Commit**

```bash
git add chargectl/config.py tests/test_config.py
git commit -m "feat: config loading from YAML with defaults"
```

---

### Task 3: RS-485 SLIP framing and checksum

This is the lowest layer — encode/decode messages with SLIP framing and checksum. No TWC-specific logic yet.

**Files:**
- Create: `chargectl/rs485.py`
- Create: `tests/test_rs485.py`

**Step 1: Write the failing tests**

```python
# tests/test_rs485.py
from chargectl.rs485 import slip_encode, slip_decode, checksum, build_message, parse_message

# SLIP framing
def test_slip_encode_no_escaping():
    data = bytes([0xFB, 0xE0, 0x77, 0x77])
    encoded = slip_encode(data)
    assert encoded == bytes([0xC0]) + data + bytes([0xC0])


def test_slip_encode_escapes_c0():
    data = bytes([0xFB, 0xC0, 0xE0])
    encoded = slip_encode(data)
    assert encoded == bytes([0xC0, 0xFB, 0xDB, 0xDC, 0xE0, 0xC0])


def test_slip_encode_escapes_db():
    data = bytes([0xFB, 0xDB, 0xE0])
    encoded = slip_encode(data)
    assert encoded == bytes([0xC0, 0xFB, 0xDB, 0xDD, 0xE0, 0xC0])


def test_slip_decode_roundtrip():
    original = bytes([0xFB, 0xE0, 0xC0, 0xDB, 0x01])
    encoded = slip_encode(original)
    # Strip the 0xC0 delimiters before decoding
    inner = encoded[1:-1]
    decoded = slip_decode(inner)
    assert decoded == original


# Checksum
def test_checksum():
    # Checksum is sum of bytes[1:] & 0xFF
    data = bytes([0xFB, 0xE0, 0x77, 0x77, 0x00, 0x00, 0x09, 0x06, 0x40, 0x00, 0x00, 0x00, 0x00])
    cs = checksum(data)
    expected = sum(data[1:]) & 0xFF
    assert cs == expected


# Build message (data -> framed with checksum)
def test_build_message():
    data = bytes([0xFB, 0xE0, 0x77, 0x77, 0x00, 0x01])
    msg = build_message(data)
    # Should be: C0 + data + checksum + C0
    assert msg[0] == 0xC0
    assert msg[-1] == 0xC0
    # Verify checksum is correct
    inner = slip_decode(msg[1:-1])
    assert checksum(inner[:-1]) == inner[-1]


# Parse message (framed bytes -> data without checksum, or None if invalid)
def test_parse_message_valid():
    data = bytes([0xFB, 0xE0, 0x77, 0x77, 0x00, 0x01])
    msg = build_message(data)
    parsed = parse_message(msg)
    assert parsed == data


def test_parse_message_bad_checksum():
    data = bytes([0xFB, 0xE0, 0x77, 0x77, 0x00, 0x01])
    msg = build_message(data)
    # Corrupt a byte
    corrupted = bytearray(msg)
    corrupted[3] = 0xFF
    parsed = parse_message(bytes(corrupted))
    assert parsed is None
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/wouterhermans/Developer/chargectl && python -m pytest tests/test_rs485.py -v`
Expected: FAIL with ImportError

**Step 3: Write minimal implementation**

```python
# chargectl/rs485.py
"""RS-485 SLIP framing and TWC protocol."""

import logging

logger = logging.getLogger(__name__)

SLIP_END = 0xC0
SLIP_ESC = 0xDB
SLIP_ESC_END = 0xDC
SLIP_ESC_ESC = 0xDD


def slip_encode(data: bytes) -> bytes:
    """SLIP-encode data and wrap in 0xC0 delimiters."""
    out = bytearray([SLIP_END])
    for b in data:
        if b == SLIP_END:
            out.extend([SLIP_ESC, SLIP_ESC_END])
        elif b == SLIP_ESC:
            out.extend([SLIP_ESC, SLIP_ESC_ESC])
        else:
            out.append(b)
    out.append(SLIP_END)
    return bytes(out)


def slip_decode(data: bytes) -> bytes:
    """SLIP-decode data (without 0xC0 delimiters)."""
    out = bytearray()
    i = 0
    while i < len(data):
        if data[i] == SLIP_ESC:
            i += 1
            if i < len(data):
                if data[i] == SLIP_ESC_END:
                    out.append(SLIP_END)
                elif data[i] == SLIP_ESC_ESC:
                    out.append(SLIP_ESC)
                else:
                    out.append(data[i])
        else:
            out.append(data[i])
        i += 1
    return bytes(out)


def checksum(data: bytes) -> int:
    """Calculate TWC checksum: sum of all bytes after the first, masked to 8 bits."""
    return sum(data[1:]) & 0xFF


def build_message(data: bytes) -> bytes:
    """Build a complete SLIP-framed message with checksum."""
    cs = checksum(data)
    return slip_encode(data + bytes([cs]))


def parse_message(raw: bytes) -> bytes | None:
    """Parse a SLIP-framed message. Returns data without checksum, or None if invalid."""
    if len(raw) < 4 or raw[0] != SLIP_END or raw[-1] != SLIP_END:
        return None
    inner = slip_decode(raw[1:-1])
    if len(inner) < 2:
        return None
    data, cs = inner[:-1], inner[-1]
    if checksum(data) != cs:
        logger.debug("Checksum mismatch: expected %02X, got %02X", checksum(data), cs)
        return None
    return data
```

**Step 4: Run test to verify it passes**

Run: `cd /Users/wouterhermans/Developer/chargectl && python -m pytest tests/test_rs485.py -v`
Expected: 8 passed

**Step 5: Commit**

```bash
git add chargectl/rs485.py tests/test_rs485.py
git commit -m "feat: RS-485 SLIP framing, checksum, message build/parse"
```

---

### Task 4: TWC charger state management

Track TWC slave state — ID, protocol version, amps offered, amps actual, voltages, state. This is a pure data class with methods, no I/O.

**Files:**
- Create: `chargectl/charger.py`
- Create: `tests/test_charger.py`

**Step 1: Write the failing tests**

```python
# tests/test_charger.py
import time
from chargectl.charger import TWCSlave, SlaveState


def test_create_slave():
    slave = TWCSlave(twc_id=bytes([0x29, 0x19]), max_amps=32.0)
    assert slave.twc_id == bytes([0x29, 0x19])
    assert slave.max_amps == 32.0
    assert slave.amps_actual == 0.0
    assert slave.amps_offered == 0.0
    assert slave.state == SlaveState.READY
    assert slave.protocol_version == 1


def test_update_from_heartbeat_v1():
    slave = TWCSlave(twc_id=bytes([0x29, 0x19]), max_amps=32.0)
    # Heartbeat data: state=01(charging), max_amps=0x0640(16.00A), actual=0x05DC(15.00A), pad
    heartbeat = bytes([0x01, 0x06, 0x40, 0x05, 0xDC, 0x00, 0x00])
    slave.update_from_heartbeat(heartbeat)
    assert slave.state == SlaveState.CHARGING
    assert slave.reported_amps_max == 16.0
    assert slave.amps_actual == 15.0


def test_update_from_heartbeat_v2():
    slave = TWCSlave(twc_id=bytes([0x29, 0x19]), max_amps=32.0)
    slave.protocol_version = 2
    heartbeat = bytes([0x01, 0x06, 0x40, 0x05, 0xDC, 0x00, 0x00, 0x00, 0x00])
    slave.update_from_heartbeat(heartbeat)
    assert slave.state == SlaveState.CHARGING
    assert slave.amps_actual == 15.0


def test_build_heartbeat_data_set_amps():
    slave = TWCSlave(twc_id=bytes([0x29, 0x19]), max_amps=32.0)
    slave.protocol_version = 2
    data = slave.build_master_heartbeat(desired_amps=16.0)
    # Command 0x09 for protocol v2, amps = 1600 = 0x0640
    assert data[0] == 0x09
    assert data[1] == 0x06
    assert data[2] == 0x40


def test_build_heartbeat_data_stop():
    slave = TWCSlave(twc_id=bytes([0x29, 0x19]), max_amps=32.0)
    slave.protocol_version = 2
    data = slave.build_master_heartbeat(desired_amps=0.0)
    # Command 0x05 when stopping (prevents relay click)
    assert data[0] == 0x05
    assert data[1] == 0x00
    assert data[2] == 0x00


def test_build_heartbeat_data_v1():
    slave = TWCSlave(twc_id=bytes([0x29, 0x19]), max_amps=32.0)
    slave.protocol_version = 1
    data = slave.build_master_heartbeat(desired_amps=12.0)
    # Command 0x05 for protocol v1
    assert data[0] == 0x05
    assert len(data) == 7


def test_is_stale():
    slave = TWCSlave(twc_id=bytes([0x29, 0x19]), max_amps=32.0)
    slave.last_heartbeat_time = time.time() - 30
    assert slave.is_stale(timeout=26)
    assert not slave.is_stale(timeout=60)
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/wouterhermans/Developer/chargectl && python -m pytest tests/test_charger.py -v`
Expected: FAIL with ImportError

**Step 3: Write minimal implementation**

```python
# chargectl/charger.py
"""TWC slave state management."""

import time
from enum import IntEnum


class SlaveState(IntEnum):
    READY = 0x00
    CHARGING = 0x01
    ERROR = 0x02
    PLUGGED_NO_CHARGE = 0x03
    PLUGGED_READY = 0x04
    BUSY = 0x05
    STARTING = 0x08


class TWCSlave:
    """Tracks the state of a single TWC Gen 2 slave."""

    def __init__(self, twc_id: bytes, max_amps: float):
        self.twc_id = twc_id
        self.max_amps = max_amps
        self.protocol_version = 1
        self.state = SlaveState.READY
        self.reported_amps_max = 0.0
        self.amps_actual = 0.0
        self.amps_offered = 0.0
        self.volts_phase_a = 0
        self.volts_phase_b = 0
        self.volts_phase_c = 0
        self.lifetime_kwh = 0
        self.last_heartbeat_time = time.time()

    def update_from_heartbeat(self, data: bytes) -> None:
        """Update slave state from a heartbeat response.

        Heartbeat data layout:
          [0]   state code
          [1-2] reported max amps (hundredths)
          [3-4] actual amps (hundredths)
          [5-6] padding (v1) or [5-8] padding (v2)
        """
        self.last_heartbeat_time = time.time()
        try:
            self.state = SlaveState(data[0])
        except ValueError:
            self.state = SlaveState.READY
        self.reported_amps_max = ((data[1] << 8) + data[2]) / 100
        self.amps_actual = ((data[3] << 8) + data[4]) / 100

    def update_voltages(self, phase_a: int, phase_b: int, phase_c: int) -> None:
        """Update voltage readings from extended power status message."""
        self.volts_phase_a = phase_a
        self.volts_phase_b = phase_b
        self.volts_phase_c = phase_c

    def build_master_heartbeat(self, desired_amps: float) -> bytes:
        """Build the heartbeat data to send to this slave.

        Protocol v1: command 0x05, 7 bytes total
        Protocol v2: command 0x09 (or 0x05 for 0A stop), 9 bytes total
        """
        hundredths = int(desired_amps * 100)
        self.amps_offered = desired_amps

        if desired_amps == 0:
            # Always use 0x05 with 0A to prevent relay clicking on Gen 2
            command = 0x05
        elif self.protocol_version == 2:
            command = 0x09
        else:
            command = 0x05

        data = bytearray([
            command,
            (hundredths >> 8) & 0xFF,
            hundredths & 0xFF,
            0x00, 0x00, 0x00, 0x00,
        ])

        if self.protocol_version == 2:
            data.extend([0x00, 0x00])

        return bytes(data)

    def is_stale(self, timeout: float = 26.0) -> bool:
        """Check if we haven't heard from this slave in too long."""
        return (time.time() - self.last_heartbeat_time) > timeout
```

**Step 4: Run test to verify it passes**

Run: `cd /Users/wouterhermans/Developer/chargectl && python -m pytest tests/test_charger.py -v`
Expected: 7 passed

**Step 5: Commit**

```bash
git add chargectl/charger.py tests/test_charger.py
git commit -m "feat: TWC slave state management and heartbeat building"
```

---

### Task 5: Modulation engine

Pure calculation — no I/O. Takes power measurements and current state, returns desired amps.

**Files:**
- Create: `chargectl/modulation.py`
- Create: `tests/test_modulation.py`

**Step 1: Write the failing tests**

```python
# tests/test_modulation.py
import time
from chargectl.modulation import ModulationEngine


def test_initial_state_is_zero():
    engine = ModulationEngine(max_amps=20, margin_amps=3)
    assert engine.desired_amps == 0


def test_ramp_up_when_free_capacity():
    engine = ModulationEngine(max_amps=20, margin_amps=3)
    engine.last_change_time = 0  # allow immediate change
    # House using 5A on worst phase, voltage 230V
    # free = 20 - 5 - 3 = 12A, > 4 so ramp up by 1
    result = engine.calculate(
        power_per_phase=[1150, 800, 900],  # watts
        voltage_per_phase=[230, 230, 230],
    )
    assert result == 1  # from 0, up by 1... but floor is 6A
    # Actually: 1 < 6, so should snap to 6
    assert engine.desired_amps == 6


def test_ramp_down_when_tight():
    engine = ModulationEngine(max_amps=20, margin_amps=3)
    engine.desired_amps = 10
    engine.last_change_time = 0
    # House using 16A worst phase → free = 20 - 16 - 3 = 1A, < 2 so ramp down
    result = engine.calculate(
        power_per_phase=[3680, 2000, 2000],
        voltage_per_phase=[230, 230, 230],
    )
    assert result == 9


def test_emergency_drop():
    engine = ModulationEngine(max_amps=20, margin_amps=3)
    engine.desired_amps = 12
    engine.last_change_time = 0
    # House using 22A worst phase → free = 20 - 22 - 3 = -5A, emergency!
    result = engine.calculate(
        power_per_phase=[5060, 2000, 2000],
        voltage_per_phase=[230, 230, 230],
    )
    # Should drop by 5: 12 - 5 = 7
    assert result == 7


def test_emergency_drop_to_zero():
    engine = ModulationEngine(max_amps=20, margin_amps=3)
    engine.desired_amps = 8
    engine.last_change_time = 0
    # House using 30A → free = 20 - 30 - 3 = -13, drop by 13 → clamp to 0
    result = engine.calculate(
        power_per_phase=[6900, 2000, 2000],
        voltage_per_phase=[230, 230, 230],
    )
    assert result == 0


def test_twc_minimum_floor():
    engine = ModulationEngine(max_amps=20, margin_amps=3)
    engine.desired_amps = 7
    engine.last_change_time = 0
    # House using 16A → free = 1A, ramp down to 6A (still >= 6, OK)
    result = engine.calculate(
        power_per_phase=[3680, 2000, 2000],
        voltage_per_phase=[230, 230, 230],
    )
    assert result == 6


def test_below_minimum_snaps_to_zero():
    engine = ModulationEngine(max_amps=20, margin_amps=3)
    engine.desired_amps = 6
    engine.last_change_time = 0
    # House using 16A → free = 1A, ramp down to 5A → below 6 → snap to 0
    result = engine.calculate(
        power_per_phase=[3680, 2000, 2000],
        voltage_per_phase=[230, 230, 230],
    )
    assert result == 0


def test_respects_rate_limit():
    engine = ModulationEngine(max_amps=20, margin_amps=3)
    engine.desired_amps = 10
    engine.last_change_time = time.time()  # just changed
    result = engine.calculate(
        power_per_phase=[1150, 800, 900],
        voltage_per_phase=[230, 230, 230],
    )
    # Should not change because rate limit (5s) not elapsed
    assert result == 10


def test_emergency_ignores_rate_limit():
    engine = ModulationEngine(max_amps=20, margin_amps=3)
    engine.desired_amps = 12
    engine.last_change_time = time.time()  # just changed
    # Emergency: free < 0
    result = engine.calculate(
        power_per_phase=[5060, 2000, 2000],
        voltage_per_phase=[230, 230, 230],
    )
    # Emergency drop ignores rate limit
    assert result == 7


def test_watchdog_no_data():
    engine = ModulationEngine(max_amps=20, margin_amps=3)
    engine.desired_amps = 16
    engine.last_data_time = time.time() - 20  # 20s ago, > 15s timeout
    result = engine.calculate(
        power_per_phase=[None, None, None],
        voltage_per_phase=[None, None, None],
    )
    assert result == 0


def test_worst_phase_used():
    engine = ModulationEngine(max_amps=20, margin_amps=3)
    engine.desired_amps = 10
    engine.last_change_time = 0
    # Phase 2 is the worst at ~15.2A
    result = engine.calculate(
        power_per_phase=[1000, 3500, 2000],
        voltage_per_phase=[230, 230, 230],
    )
    # free = 20 - 15.2 - 3 = 1.8A, < 2 so ramp down
    assert result == 9
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/wouterhermans/Developer/chargectl && python -m pytest tests/test_modulation.py -v`
Expected: FAIL with ImportError

**Step 3: Write minimal implementation**

```python
# chargectl/modulation.py
"""Power modulation engine for EV charging."""

import logging
import time

logger = logging.getLogger(__name__)

TWC_MIN_AMPS = 6
RATE_LIMIT_SECONDS = 5
WATCHDOG_TIMEOUT = 15


class ModulationEngine:
    """Calculates safe charging amps based on per-phase power measurements."""

    def __init__(self, max_amps: int, margin_amps: int):
        self.max_amps = max_amps
        self.margin_amps = margin_amps
        self.desired_amps = 0
        self.last_change_time = 0.0
        self.last_data_time = time.time()

    def calculate(
        self,
        power_per_phase: list[float | None],
        voltage_per_phase: list[float | None],
    ) -> int:
        """Calculate desired charging amps based on current power measurements.

        Returns the new desired amps value (0 or >= TWC_MIN_AMPS).
        """
        # Watchdog: if no valid data, stop charging
        if any(v is None for v in power_per_phase) or any(
            v is None for v in voltage_per_phase
        ):
            if time.time() - self.last_data_time > WATCHDOG_TIMEOUT:
                logger.warning("No power data for %ds, stopping charging", WATCHDOG_TIMEOUT)
                self.desired_amps = 0
                return 0
            return self.desired_amps

        self.last_data_time = time.time()

        # Calculate per-phase amperage
        amps_per_phase = []
        for power, voltage in zip(power_per_phase, voltage_per_phase):
            if voltage > 0:
                amps_per_phase.append(power / voltage)
            else:
                amps_per_phase.append(0)

        worst_phase_amps = max(amps_per_phase)
        free_amps = self.max_amps - worst_phase_amps - self.margin_amps

        now = time.time()
        new_amps = self.desired_amps

        if free_amps < 0:
            # EMERGENCY: instant proportional drop, ignores rate limit
            new_amps = max(0, self.desired_amps + free_amps)
            new_amps = int(new_amps)
            logger.warning(
                "Emergency ramp-down: worst_phase=%.1fA free=%.1fA -> %dA",
                worst_phase_amps, free_amps, new_amps,
            )
        elif now - self.last_change_time < RATE_LIMIT_SECONDS:
            # Rate limited, no change
            return self.desired_amps
        elif free_amps < 2:
            new_amps = self.desired_amps - 1
            logger.info("Ramp down: free=%.1fA -> %dA", free_amps, new_amps)
        elif free_amps > 4:
            new_amps = self.desired_amps + 1
            logger.info("Ramp up: free=%.1fA -> %dA", free_amps, new_amps)
        else:
            return self.desired_amps

        # Enforce TWC minimum: either >= 6A or 0
        if 0 < new_amps < TWC_MIN_AMPS:
            if self.desired_amps == 0:
                # Ramping up from 0: snap to minimum
                new_amps = TWC_MIN_AMPS
            else:
                # Ramping down below minimum: snap to 0
                new_amps = 0

        # Clamp to valid range
        new_amps = max(0, min(new_amps, self.max_amps - self.margin_amps))

        if new_amps != self.desired_amps:
            self.last_change_time = now

        self.desired_amps = new_amps
        return new_amps
```

**Step 4: Run test to verify it passes**

Run: `cd /Users/wouterhermans/Developer/chargectl && python -m pytest tests/test_modulation.py -v`
Expected: 11 passed

**Step 5: Commit**

```bash
git add chargectl/modulation.py tests/test_modulation.py
git commit -m "feat: power modulation engine with per-phase tracking and watchdog"
```

---

### Task 6: RS-485 TWC master (serial I/O)

Add the TWC-specific master logic on top of the SLIP layer: link ready, heartbeat send/receive, slave discovery, and the serial read/write loop.

**Files:**
- Modify: `chargectl/rs485.py` (add TWCMaster class)
- Create: `tests/test_twc_master.py`

**Step 1: Write the failing tests**

```python
# tests/test_twc_master.py
from unittest.mock import MagicMock
from chargectl.rs485 import TWCMaster, build_message, parse_message, FUNC_MASTER_HEARTBEAT, FUNC_SLAVE_HEARTBEAT, FUNC_SLAVE_LINKREADY


def test_build_master_heartbeat_message():
    master = TWCMaster.__new__(TWCMaster)
    master.master_id = bytes([0x77, 0x77])
    master.slaves = {}
    slave_id = bytes([0x29, 0x19])
    heartbeat_data = bytes([0x09, 0x06, 0x40, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])
    msg = master._build_heartbeat_message(slave_id, heartbeat_data)
    parsed = parse_message(msg)
    assert parsed is not None
    # Function code
    assert parsed[0:2] == bytes([0xFB, 0xE0])
    # Master ID
    assert parsed[2:4] == bytes([0x77, 0x77])
    # Slave ID
    assert parsed[4:6] == bytes([0x29, 0x19])
    # Heartbeat data
    assert parsed[6:15] == heartbeat_data


def test_parse_slave_linkready():
    master = TWCMaster.__new__(TWCMaster)
    master.master_id = bytes([0x77, 0x77])
    master.slaves = {}
    # Simulate a slave linkready: FDE2 + slaveID + sign + maxAmps(hundredths)
    data = bytes([
        0xFD, 0xE2,           # function code
        0x29, 0x19,           # slave ID
        0x77, 0x77,           # master ID (sign byte)
        0x0C, 0x80,           # max amps: 3200 = 32.00A
        0x00, 0x00, 0x00, 0x00, 0x00, 0x00,  # padding
    ])
    result = master._parse_incoming(data)
    assert result is not None
    assert result["type"] == "linkready"
    assert result["slave_id"] == bytes([0x29, 0x19])
    assert result["max_amps"] == 32.0


def test_parse_slave_heartbeat():
    master = TWCMaster.__new__(TWCMaster)
    master.master_id = bytes([0x77, 0x77])
    master.slaves = {}
    # Simulate slave heartbeat: FDE0 + slaveID + masterID + heartbeat data
    data = bytes([
        0xFD, 0xE0,           # function code
        0x29, 0x19,           # slave ID
        0x77, 0x77,           # master ID
        0x01,                 # state: charging
        0x06, 0x40,           # reported max amps: 1600 = 16.00A
        0x05, 0xDC,           # actual amps: 1500 = 15.00A
        0x00, 0x00, 0x00, 0x00,  # padding (v2)
    ])
    result = master._parse_incoming(data)
    assert result is not None
    assert result["type"] == "heartbeat"
    assert result["slave_id"] == bytes([0x29, 0x19])
    assert result["heartbeat_data"][0] == 0x01  # charging
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/wouterhermans/Developer/chargectl && python -m pytest tests/test_twc_master.py -v`
Expected: FAIL with ImportError

**Step 3: Add TWCMaster class to rs485.py**

Append to `chargectl/rs485.py`:

```python
import serial
import time
from chargectl.charger import TWCSlave

FUNC_MASTER_LINKREADY1 = bytes([0xFC, 0xE1])
FUNC_MASTER_LINKREADY2 = bytes([0xFB, 0xE2])
FUNC_MASTER_HEARTBEAT = bytes([0xFB, 0xE0])
FUNC_SLAVE_LINKREADY = bytes([0xFD, 0xE2])
FUNC_SLAVE_HEARTBEAT = bytes([0xFD, 0xE0])
FUNC_SLAVE_POWER_STATUS = bytes([0xFD, 0xEB])


class TWCMaster:
    """Fake TWC master that communicates with slave TWCs over RS-485."""

    def __init__(self, port: str, baud: int = 9600):
        self.master_id = bytes([0x77, 0x77])
        self.port = port
        self.baud = baud
        self.serial: serial.Serial | None = None
        self.slaves: dict[bytes, TWCSlave] = {}
        self._read_buffer = bytearray()

    def open(self) -> None:
        """Open the serial port."""
        self.serial = serial.Serial(self.port, self.baud, timeout=0)
        logger.info("RS-485 opened on %s at %d baud", self.port, self.baud)

    def close(self) -> None:
        """Close the serial port."""
        if self.serial:
            self.serial.close()
            logger.info("RS-485 closed")

    def send_linkready(self) -> None:
        """Send master link ready announcements (5 each type)."""
        for func in [FUNC_MASTER_LINKREADY1, FUNC_MASTER_LINKREADY2]:
            for _ in range(5):
                data = func + self.master_id + bytes(8 if func == FUNC_MASTER_LINKREADY1 else 8)
                msg = build_message(data)
                self._send_raw(msg)
                time.sleep(0.1)

    def send_heartbeat(self, slave: TWCSlave, desired_amps: float) -> None:
        """Send a master heartbeat to a slave with the desired amperage."""
        heartbeat_data = slave.build_master_heartbeat(desired_amps)
        msg = self._build_heartbeat_message(slave.twc_id, heartbeat_data)
        self._send_raw(msg)
        logger.debug(
            "TX heartbeat to %s: %.1fA (cmd=%02X)",
            slave.twc_id.hex(), desired_amps, heartbeat_data[0],
        )

    def read_and_process(self) -> list[dict]:
        """Read available data from serial and process complete messages.

        Returns a list of parsed message dicts.
        """
        results = []
        if not self.serial:
            return results

        data = self.serial.read(256)
        if data:
            self._read_buffer.extend(data)
            logger.debug("RX raw: %s", data.hex())

        # Extract complete SLIP frames
        while True:
            start = self._find_frame_start()
            if start is None:
                break
            end = self._find_frame_end(start + 1)
            if end is None:
                break
            frame = bytes(self._read_buffer[start : end + 1])
            self._read_buffer = self._read_buffer[end + 1 :]
            parsed_data = parse_message(frame)
            if parsed_data:
                result = self._parse_incoming(parsed_data)
                if result:
                    results.append(result)

        return results

    def _build_heartbeat_message(self, slave_id: bytes, heartbeat_data: bytes) -> bytes:
        """Build a complete master heartbeat message."""
        data = FUNC_MASTER_HEARTBEAT + self.master_id + slave_id + heartbeat_data
        return build_message(data)

    def _parse_incoming(self, data: bytes) -> dict | None:
        """Parse an incoming message from a slave."""
        if len(data) < 6:
            return None

        func = data[0:2]
        slave_id = bytes(data[2:4])

        if func == FUNC_SLAVE_LINKREADY:
            max_amps = ((data[6] << 8) + data[7]) / 100
            logger.info("Slave %s linked: max %.1fA", slave_id.hex(), max_amps)
            return {"type": "linkready", "slave_id": slave_id, "max_amps": max_amps}

        elif func == FUNC_SLAVE_HEARTBEAT:
            heartbeat_data = data[6:]
            return {"type": "heartbeat", "slave_id": slave_id, "heartbeat_data": heartbeat_data}

        elif func == FUNC_SLAVE_POWER_STATUS:
            # Extended power status with voltage info
            if len(data) >= 14:
                volts_a = ((data[6] << 8) + data[7])
                volts_b = ((data[8] << 8) + data[9])
                volts_c = ((data[10] << 8) + data[11])
                return {
                    "type": "power_status",
                    "slave_id": slave_id,
                    "volts": (volts_a, volts_b, volts_c),
                }
            return None

        return None

    def _send_raw(self, data: bytes) -> None:
        """Send raw bytes over serial."""
        if self.serial:
            self.serial.write(data)
            logger.debug("TX raw: %s", data.hex())

    def _find_frame_start(self) -> int | None:
        """Find the index of the next SLIP_END start byte."""
        try:
            return self._read_buffer.index(SLIP_END)
        except ValueError:
            return None

    def _find_frame_end(self, start: int) -> int | None:
        """Find the index of the closing SLIP_END byte after start."""
        try:
            return self._read_buffer.index(SLIP_END, start)
        except ValueError:
            return None
```

**Step 4: Run test to verify it passes**

Run: `cd /Users/wouterhermans/Developer/chargectl && python -m pytest tests/test_twc_master.py -v`
Expected: 3 passed

**Step 5: Run all tests**

Run: `cd /Users/wouterhermans/Developer/chargectl && python -m pytest -v`
Expected: all tests pass

**Step 6: Commit**

```bash
git add chargectl/rs485.py tests/test_twc_master.py
git commit -m "feat: TWC master RS-485 protocol with heartbeat, linkready, slave discovery"
```

---

### Task 7: MQTT client (subscribe + publish + HA discovery)

**Files:**
- Create: `chargectl/mqtt_client.py`
- Create: `tests/test_mqtt_client.py`

**Step 1: Write the failing tests**

```python
# tests/test_mqtt_client.py
import json
from unittest.mock import MagicMock, patch, call
from chargectl.mqtt_client import ChargeMQTT
from chargectl.config import Config


def make_config(**overrides):
    defaults = dict(
        mqtt_broker="localhost", mqtt_port=1883,
        mqtt_username=None, mqtt_password=None,
        rs485_port="/dev/ttyUSB0", rs485_baud=9600,
        max_amps_per_phase=20, margin_amps=3,
        power_source_type="rpict4v3",
        power_topics={
            "power_phase1": "RPICT4V3/RP1",
            "power_phase2": "RPICT4V3/RP2",
            "power_phase3": "RPICT4V3/RP3",
            "voltage_phase1": "RPICT4V3/Vrms1",
            "voltage_phase2": "RPICT4V3/Vrms2",
            "voltage_phase3": "RPICT4V3/Vrms3",
        },
        log_level="info",
    )
    defaults.update(overrides)
    return Config(**defaults)


def test_power_topics_subscribed():
    cfg = make_config()
    mqtt = ChargeMQTT(cfg)
    topics = mqtt.get_subscribe_topics()
    assert "RPICT4V3/RP1" in topics
    assert "RPICT4V3/Vrms1" in topics
    assert len(topics) == 6


def test_power_data_parsing():
    cfg = make_config()
    mqtt = ChargeMQTT(cfg)
    # Simulate incoming power message
    mqtt.on_power_message("RPICT4V3/RP1", b"1500.5")
    assert mqtt.power_data["power_phase1"] == 1500.5


def test_voltage_data_parsing():
    cfg = make_config()
    mqtt = ChargeMQTT(cfg)
    mqtt.on_power_message("RPICT4V3/Vrms1", b"232.1")
    assert mqtt.power_data["voltage_phase1"] == 232.1


def test_get_measurements_complete():
    cfg = make_config()
    mqtt = ChargeMQTT(cfg)
    mqtt.power_data = {
        "power_phase1": 1000, "power_phase2": 1200, "power_phase3": 900,
        "voltage_phase1": 230, "voltage_phase2": 231, "voltage_phase3": 229,
    }
    power, voltage = mqtt.get_measurements()
    assert power == [1000, 1200, 900]
    assert voltage == [230, 231, 229]


def test_get_measurements_incomplete():
    cfg = make_config()
    mqtt = ChargeMQTT(cfg)
    # Missing data
    power, voltage = mqtt.get_measurements()
    assert None in power


def test_ha_discovery_payload():
    cfg = make_config()
    mqtt = ChargeMQTT(cfg)
    payloads = mqtt.build_ha_discovery("2919")
    # Should have sensor configs
    assert any("amps_actual" in json.dumps(p) for _, p in payloads)
    # Each payload should have device info
    for topic, payload in payloads:
        assert "device" in payload
        assert payload["device"]["name"] == "chargectl"
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/wouterhermans/Developer/chargectl && python -m pytest tests/test_mqtt_client.py -v`
Expected: FAIL with ImportError

**Step 3: Write implementation**

```python
# chargectl/mqtt_client.py
"""MQTT client for power measurement input and status/HA discovery output."""

import json
import logging
import time
import paho.mqtt.client as mqtt
from chargectl.config import Config

logger = logging.getLogger(__name__)

TOPIC_PREFIX = "chargectl"


class ChargeMQTT:
    """Handles MQTT communication for power data and charger status."""

    def __init__(self, config: Config):
        self.config = config
        self.power_data: dict[str, float] = {}
        self._topic_to_key: dict[str, str] = {}
        self._client: mqtt.Client | None = None
        self._on_control_callback = None

        # Build topic-to-key mapping
        for key, topic in config.power_topics.items():
            self._topic_to_key[topic] = key

    def get_subscribe_topics(self) -> list[str]:
        """Return list of MQTT topics to subscribe to."""
        return list(self._topic_to_key.keys())

    def on_power_message(self, topic: str, payload: bytes) -> None:
        """Process an incoming power measurement message."""
        key = self._topic_to_key.get(topic)
        if key is None:
            return
        try:
            value = float(payload.decode("utf-8").strip())
            self.power_data[key] = value
        except (ValueError, UnicodeDecodeError):
            logger.warning("Invalid payload on %s: %s", topic, payload)

    def get_measurements(self) -> tuple[list[float | None], list[float | None]]:
        """Get current power and voltage measurements per phase.

        Returns (power_per_phase, voltage_per_phase) with None for missing data.
        """
        power = [
            self.power_data.get("power_phase1"),
            self.power_data.get("power_phase2"),
            self.power_data.get("power_phase3"),
        ]
        voltage = [
            self.power_data.get("voltage_phase1"),
            self.power_data.get("voltage_phase2"),
            self.power_data.get("voltage_phase3"),
        ]
        return power, voltage

    def connect(self) -> None:
        """Connect to the MQTT broker and subscribe to topics."""
        self._client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2, client_id="chargectl"
        )
        if self.config.mqtt_username:
            self._client.username_pw_set(
                self.config.mqtt_username, self.config.mqtt_password
            )
        self._client.on_connect = self._on_connect
        self._client.on_message = self._on_message
        self._client.connect(self.config.mqtt_broker, self.config.mqtt_port)
        self._client.loop_start()
        logger.info("MQTT connecting to %s:%d", self.config.mqtt_broker, self.config.mqtt_port)

    def disconnect(self) -> None:
        """Disconnect from the MQTT broker."""
        if self._client:
            self._client.loop_stop()
            self._client.disconnect()

    def publish_status(self, slave_id: str, data: dict) -> None:
        """Publish charger status to MQTT."""
        if not self._client:
            return
        topic = f"{TOPIC_PREFIX}/{slave_id}/status"
        self._client.publish(topic, json.dumps(data), retain=True)

    def publish_ha_discovery(self, slave_id: str) -> None:
        """Publish Home Assistant MQTT discovery config for a TWC slave."""
        if not self._client:
            return
        for topic, payload in self.build_ha_discovery(slave_id):
            self._client.publish(topic, json.dumps(payload), retain=True)
        logger.info("Published HA discovery for TWC %s", slave_id)

    def build_ha_discovery(self, slave_id: str) -> list[tuple[str, dict]]:
        """Build Home Assistant MQTT auto-discovery payloads."""
        device = {
            "identifiers": [f"chargectl_{slave_id}"],
            "name": "chargectl",
            "model": "TWC Gen 2",
            "manufacturer": "chargectl",
        }
        status_topic = f"{TOPIC_PREFIX}/{slave_id}/status"
        configs = []

        # Sensor: amps actual
        configs.append((
            f"homeassistant/sensor/chargectl_{slave_id}_amps/config",
            {
                "name": f"TWC {slave_id} Amps",
                "unique_id": f"chargectl_{slave_id}_amps_actual",
                "state_topic": status_topic,
                "value_template": "{{ value_json.amps_actual }}",
                "unit_of_measurement": "A",
                "device_class": "current",
                "device": device,
            },
        ))

        # Sensor: amps offered
        configs.append((
            f"homeassistant/sensor/chargectl_{slave_id}_offered/config",
            {
                "name": f"TWC {slave_id} Amps Offered",
                "unique_id": f"chargectl_{slave_id}_amps_offered",
                "state_topic": status_topic,
                "value_template": "{{ value_json.amps_offered }}",
                "unit_of_measurement": "A",
                "device_class": "current",
                "device": device,
            },
        ))

        # Sensor: power
        configs.append((
            f"homeassistant/sensor/chargectl_{slave_id}_power/config",
            {
                "name": f"TWC {slave_id} Power",
                "unique_id": f"chargectl_{slave_id}_power",
                "state_topic": status_topic,
                "value_template": "{{ value_json.power_w }}",
                "unit_of_measurement": "W",
                "device_class": "power",
                "device": device,
            },
        ))

        # Sensor: state
        configs.append((
            f"homeassistant/sensor/chargectl_{slave_id}_state/config",
            {
                "name": f"TWC {slave_id} State",
                "unique_id": f"chargectl_{slave_id}_state",
                "state_topic": status_topic,
                "value_template": "{{ value_json.state }}",
                "device": device,
            },
        ))

        # Sensor: voltage per phase
        for phase in ["a", "b", "c"]:
            configs.append((
                f"homeassistant/sensor/chargectl_{slave_id}_volts_{phase}/config",
                {
                    "name": f"TWC {slave_id} Voltage Phase {phase.upper()}",
                    "unique_id": f"chargectl_{slave_id}_volts_{phase}",
                    "state_topic": status_topic,
                    "value_template": f"{{{{ value_json.volts_phase_{phase} }}}}",
                    "unit_of_measurement": "V",
                    "device_class": "voltage",
                    "device": device,
                },
            ))

        return configs

    def set_on_control(self, callback) -> None:
        """Set callback for incoming control messages (max_amps, enable/disable)."""
        self._on_control_callback = callback
        if self._client:
            self._client.subscribe(f"{TOPIC_PREFIX}/control/#")

    def _on_connect(self, client, userdata, flags, rc, properties=None):
        logger.info("MQTT connected (rc=%s)", rc)
        for topic in self.get_subscribe_topics():
            client.subscribe(topic)
            logger.debug("Subscribed to %s", topic)
        # Subscribe to control topics
        client.subscribe(f"{TOPIC_PREFIX}/control/#")

    def _on_message(self, client, userdata, message):
        if message.topic in self._topic_to_key:
            self.on_power_message(message.topic, message.payload)
        elif message.topic.startswith(f"{TOPIC_PREFIX}/control/"):
            self._handle_control(message.topic, message.payload)

    def _handle_control(self, topic: str, payload: bytes) -> None:
        """Handle incoming control messages."""
        command = topic.split("/")[-1]
        try:
            value = payload.decode("utf-8").strip()
        except UnicodeDecodeError:
            return

        logger.info("Control message: %s = %s", command, value)
        if self._on_control_callback:
            self._on_control_callback(command, value)
```

**Step 4: Run test to verify it passes**

Run: `cd /Users/wouterhermans/Developer/chargectl && python -m pytest tests/test_mqtt_client.py -v`
Expected: 6 passed

**Step 5: Run all tests**

Run: `cd /Users/wouterhermans/Developer/chargectl && python -m pytest -v`
Expected: all tests pass

**Step 6: Commit**

```bash
git add chargectl/mqtt_client.py tests/test_mqtt_client.py
git commit -m "feat: MQTT client with power subscription, status publish, and HA discovery"
```

---

### Task 8: Main loop (entry point)

Ties everything together: config → MQTT → modulation → RS-485 heartbeat loop.

**Files:**
- Create: `chargectl/__main__.py`
- Create: `tests/test_main.py`

**Step 1: Write the failing test**

```python
# tests/test_main.py
from unittest.mock import patch, MagicMock
import tempfile
import os

VALID_CONFIG = """
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
  type: rpict4v3
  topics:
    power_phase1: "RPICT4V3/RP1"
    power_phase2: "RPICT4V3/RP2"
    power_phase3: "RPICT4V3/RP3"
    voltage_phase1: "RPICT4V3/Vrms1"
    voltage_phase2: "RPICT4V3/Vrms2"
    voltage_phase3: "RPICT4V3/Vrms3"
logging:
  level: debug
"""


def test_main_loads_config_and_starts():
    """Test that main() loads config and initializes components."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(VALID_CONFIG)
        path = f.name

    with patch("chargectl.__main__.TWCMaster") as mock_master, \
         patch("chargectl.__main__.ChargeMQTT") as mock_mqtt, \
         patch("chargectl.__main__.run_loop") as mock_loop:
        from chargectl.__main__ import main
        main(["--config", path])
        mock_master.assert_called_once()
        mock_mqtt.assert_called_once()
        mock_loop.assert_called_once()

    os.unlink(path)
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/wouterhermans/Developer/chargectl && python -m pytest tests/test_main.py -v`
Expected: FAIL with ImportError

**Step 3: Write implementation**

```python
# chargectl/__main__.py
"""chargectl entry point."""

import argparse
import logging
import signal
import sys
import time

from chargectl import __version__
from chargectl.config import load_config
from chargectl.charger import TWCSlave
from chargectl.modulation import ModulationEngine
from chargectl.mqtt_client import ChargeMQTT
from chargectl.rs485 import TWCMaster

logger = logging.getLogger("chargectl")

_running = True


def _handle_signal(sig, frame):
    global _running
    logger.info("Received signal %d, shutting down...", sig)
    _running = False


def run_loop(
    twc: TWCMaster,
    mqtt_client: ChargeMQTT,
    engine: ModulationEngine,
) -> None:
    """Main control loop."""
    global _running

    last_heartbeat_time: dict[bytes, float] = {}
    ha_discovery_sent: set[str] = set()

    logger.info("Sending link ready announcements...")
    twc.send_linkready()
    logger.info("Entering main loop")

    while _running:
        # 1. Read and process RS-485 messages
        messages = twc.read_and_process()
        for msg in messages:
            slave_id = msg["slave_id"]
            slave_id_hex = slave_id.hex()

            if msg["type"] == "linkready":
                if slave_id not in twc.slaves:
                    slave = TWCSlave(twc_id=slave_id, max_amps=msg["max_amps"])
                    # Detect protocol v2 based on message length hints
                    slave.protocol_version = 2
                    twc.slaves[slave_id] = slave
                    logger.info(
                        "Discovered TWC slave %s (max %.0fA)",
                        slave_id_hex, msg["max_amps"],
                    )

            elif msg["type"] == "heartbeat":
                slave = twc.slaves.get(slave_id)
                if slave:
                    slave.update_from_heartbeat(msg["heartbeat_data"])

                    # Publish HA discovery once per slave
                    if slave_id_hex not in ha_discovery_sent:
                        mqtt_client.publish_ha_discovery(slave_id_hex)
                        ha_discovery_sent.add(slave_id_hex)

                    # Publish status
                    mqtt_client.publish_status(slave_id_hex, {
                        "state": slave.state.name.lower(),
                        "amps_actual": round(slave.amps_actual, 2),
                        "amps_offered": round(slave.amps_offered, 2),
                        "power_w": round(slave.amps_actual * 230 * 3, 0),  # approximate
                        "volts_phase_a": slave.volts_phase_a,
                        "volts_phase_b": slave.volts_phase_b,
                        "volts_phase_c": slave.volts_phase_c,
                    })

            elif msg["type"] == "power_status":
                slave = twc.slaves.get(slave_id)
                if slave:
                    slave.update_voltages(*msg["volts"])

        # 2. Get power measurements and calculate desired amps
        power, voltage = mqtt_client.get_measurements()
        desired_amps = engine.calculate(power, voltage)

        # 3. Send heartbeats to each slave (~1 per second per slave)
        now = time.time()
        for slave_id, slave in twc.slaves.items():
            last = last_heartbeat_time.get(slave_id, 0)
            if now - last >= 1.0:
                twc.send_heartbeat(slave, desired_amps)
                last_heartbeat_time[slave_id] = now

            # Check for stale slaves
            if slave.is_stale():
                logger.warning("TWC slave %s is stale, removing", slave_id.hex())
                del twc.slaves[slave_id]
                break  # dict changed during iteration

        # Sleep to avoid busy-looping (~25ms as per TWCManager)
        time.sleep(0.025)


def main(argv: list[str] | None = None) -> None:
    """Entry point for chargectl."""
    parser = argparse.ArgumentParser(
        prog="chargectl",
        description="Lightweight EV charger controller for TWC Gen 2",
    )
    parser.add_argument(
        "--config", "-c",
        default="/etc/chargectl/config.yaml",
        help="Path to config file (default: /etc/chargectl/config.yaml)",
    )
    parser.add_argument(
        "--version", "-v",
        action="version",
        version=f"chargectl {__version__}",
    )
    args = parser.parse_args(argv)

    # Load config
    config = load_config(args.config)

    # Setup logging
    log_level = getattr(logging, config.log_level.upper(), logging.INFO)
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        datefmt="%H:%M:%S",
    )
    logger.info("chargectl %s starting", __version__)

    # Initialize components
    twc = TWCMaster(port=config.rs485_port, baud=config.rs485_baud)
    mqtt_client = ChargeMQTT(config)
    engine = ModulationEngine(
        max_amps=config.max_amps_per_phase,
        margin_amps=config.margin_amps,
    )

    # Handle control messages from MQTT
    def on_control(command: str, value: str):
        if command == "max_amps":
            try:
                engine.max_amps = int(value)
                logger.info("Max amps set to %d via MQTT", engine.max_amps)
            except ValueError:
                pass
        elif command == "enabled":
            if value.lower() in ("false", "0", "off"):
                engine.desired_amps = 0
                logger.info("Charging disabled via MQTT")

    mqtt_client.set_on_control(on_control)

    # Setup signal handlers
    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    # Connect and run
    try:
        twc.open()
        mqtt_client.connect()
        run_loop(twc, mqtt_client, engine)
    except Exception:
        logger.exception("Fatal error")
        sys.exit(1)
    finally:
        logger.info("Shutting down...")
        # Set all slaves to 0A before exiting
        for slave in twc.slaves.values():
            twc.send_heartbeat(slave, 0)
        time.sleep(0.5)
        mqtt_client.disconnect()
        twc.close()
        logger.info("Goodbye")


if __name__ == "__main__":
    main()
```

**Step 4: Run test to verify it passes**

Run: `cd /Users/wouterhermans/Developer/chargectl && python -m pytest tests/test_main.py -v`
Expected: 1 passed

**Step 5: Run all tests**

Run: `cd /Users/wouterhermans/Developer/chargectl && python -m pytest -v`
Expected: all tests pass

**Step 6: Commit**

```bash
git add chargectl/__main__.py tests/test_main.py
git commit -m "feat: main entry point with control loop, signal handling, graceful shutdown"
```

---

### Task 9: Documentation (README.md + INSTALL.md)

**Files:**
- Create: `README.md`
- Create: `INSTALL.md`

**Step 1: Write README.md**

```markdown
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
# Install
pip install .

# Copy and edit config
sudo mkdir -p /etc/chargectl
sudo cp config.example.yaml /etc/chargectl/config.yaml
sudo nano /etc/chargectl/config.yaml

# Run
chargectl --config /etc/chargectl/config.yaml
```

See [INSTALL.md](INSTALL.md) for full setup instructions including systemd service.

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

## Hardware Requirements

- Raspberry Pi (or any Linux box)
- USB-to-RS-485 adapter (CP2102 or similar, ~$5)
- TWC Gen 2 set to position F (slave mode)
- RS-485 wiring: D+ to D+, D- to D-
- MQTT broker (Mosquitto)
- Power measurement source publishing to MQTT

## License

MIT
```

**Step 2: Write INSTALL.md**

```markdown
# Installing chargectl on a Raspberry Pi

## Prerequisites

- Raspberry Pi running Raspbian/Raspberry Pi OS (64-bit recommended)
- Python 3.11 or later
- USB-to-RS-485 adapter connected (shows up as `/dev/ttyUSB0`)
- Mosquitto MQTT broker running (locally or on network)
- Power measurement data being published to MQTT

## 1. Install Python and pip

```bash
sudo apt update
sudo apt install -y python3 python3-pip python3-venv
```

## 2. Install chargectl

```bash
# Clone the repo
cd /home/wouter
git clone https://github.com/wooter/chargectl.git
cd chargectl

# Create a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install
pip install .
```

## 3. Configure

```bash
sudo mkdir -p /etc/chargectl
sudo cp config.example.yaml /etc/chargectl/config.yaml
sudo nano /etc/chargectl/config.yaml
```

Edit the config for your setup:

- `mqtt.broker` — IP of your MQTT broker (use `localhost` if running on the same Pi)
- `rs485.port` — usually `/dev/ttyUSB0`, check with `ls /dev/ttyUSB*`
- `grid.max_amps_per_phase` — your main fuse rating (e.g., 20)
- `grid.margin_amps` — safety margin (3 recommended)
- `power_source.topics` — match the MQTT topics your power meter publishes

## 4. Test manually

```bash
# Run in foreground with debug logging
source /home/wouter/chargectl/.venv/bin/activate
chargectl --config /etc/chargectl/config.yaml
```

You should see:
- `RS-485 opened on /dev/ttyUSB0 at 9600 baud`
- `MQTT connecting to ...`
- `Discovered TWC slave XXXX` (within ~10 seconds if TWCs are powered on)

Press Ctrl+C to stop. chargectl will set all chargers to 0A before exiting.

## 5. Set up serial port permissions

```bash
# Add your user to the dialout group (required for serial port access)
sudo usermod -a -G dialout wouter

# Log out and back in, or:
newgrp dialout
```

## 6. Install as systemd service

```bash
sudo tee /etc/systemd/system/chargectl.service << 'EOF'
[Unit]
Description=chargectl - EV charger controller
After=network.target mosquitto.service

[Service]
Type=simple
User=wouter
ExecStart=/home/wouter/chargectl/.venv/bin/chargectl --config /etc/chargectl/config.yaml
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable chargectl
sudo systemctl start chargectl
```

## 7. Check it's running

```bash
# View logs
journalctl -u chargectl -f

# Check status
systemctl status chargectl
```

## 8. TWC hardware setup

1. Set each TWC Gen 2 rotary switch to position **F** (slave mode)
2. Connect RS-485 wiring: D+ to D+, D- to D- between the USB adapter and TWC terminals
3. If you have 2 TWCs, daisy-chain them on the same RS-485 bus

## Migrating from TWCManager

1. Stop TWCManager: `sudo systemctl stop twcmanager && sudo systemctl disable twcmanager`
2. Start chargectl: `sudo systemctl start chargectl`
3. If something goes wrong: `sudo systemctl stop chargectl && sudo systemctl enable twcmanager && sudo systemctl start twcmanager`

TWCManager and chargectl cannot run simultaneously (they'd both try to be the RS-485 master).

## Updating

```bash
cd /home/wouter/chargectl
git pull
source .venv/bin/activate
pip install .
sudo systemctl restart chargectl
```

## Troubleshooting

**No TWC slaves discovered:**
- Check RS-485 wiring (D+/D- not swapped)
- Check TWC rotary switch is on F
- Check serial port: `ls -la /dev/ttyUSB0`
- Run with `logging.level: debug` to see raw RS-485 frames

**Fuse still trips:**
- Increase `grid.margin_amps` (try 4 or 5)
- Check that power measurement topics are correct and data is flowing
- Run with debug logging to see the modulation decisions

**MQTT connection fails:**
- Check broker is running: `systemctl status mosquitto`
- Check broker IP in config
- Test manually: `mosquitto_sub -h localhost -t '#' -v`
```

**Step 3: Commit**

```bash
git add README.md INSTALL.md
git commit -m "docs: add README and installation guide for Raspberry Pi"
```

---

### Task 10: Create GitHub repo and push

**Step 1: Create the GitHub repo**

```bash
cd /Users/wouterhermans/Developer/chargectl
gh repo create wooter/chargectl --public --description "Lightweight EV charger controller for Tesla Wall Connector Gen 2 via RS-485" --source . --push
```

**Step 2: Verify**

```bash
gh repo view wooter/chargectl --web
```
