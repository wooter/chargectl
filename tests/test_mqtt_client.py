import json
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
    power, voltage = mqtt.get_measurements()
    assert None in power


def test_ha_discovery_payload():
    cfg = make_config()
    mqtt = ChargeMQTT(cfg)
    payloads = mqtt.build_ha_discovery("2919")
    assert any("amps_actual" in json.dumps(p) for _, p in payloads)
    for topic, payload in payloads:
        assert "device" in payload
        assert payload["device"]["name"] == "chargectl"
