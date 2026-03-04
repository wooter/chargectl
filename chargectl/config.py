"""Configuration loading from YAML."""

from __future__ import annotations

from dataclasses import dataclass
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
    chargers: dict[str, dict]
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
        chargers=raw.get("chargers", {}),
        log_level=logging_cfg.get("level", "info"),
    )
