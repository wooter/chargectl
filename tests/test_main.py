from unittest.mock import patch, MagicMock
import tempfile
import os
from chargectl.__main__ import _calibrated_kwh

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


def test_calibrated_kwh_with_baseline():
    config = {"2919": {"kwh_real": 67522, "kwh_counter": 4793511}}
    # Counter hasn't changed -> return baseline
    assert _calibrated_kwh("2919", 4793511, config) == 67522
    # Counter increased by 100 -> baseline + 100
    assert _calibrated_kwh("2919", 4793611, config) == 67622


def test_calibrated_kwh_no_baseline():
    # No config -> return raw value
    assert _calibrated_kwh("2919", 4793511, {}) == 4793511


def test_calibrated_kwh_unknown_slave():
    config = {"6807": {"kwh_real": 5149, "kwh_counter": 2437}}
    # Unknown slave -> return raw value
    assert _calibrated_kwh("2919", 4793511, config) == 4793511
