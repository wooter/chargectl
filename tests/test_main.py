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
