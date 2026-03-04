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
    assert cfg.log_level == "info"
    assert cfg.chargers == {}


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
