"""MQTT client for power measurement input and status/HA discovery output."""

import json
import logging
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
        """Get current power and voltage measurements per phase."""
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

        for phase in ["a", "b", "c"]:
            configs.append((
                f"homeassistant/sensor/chargectl_{slave_id}_volts_{phase}/config",
                {
                    "name": f"TWC {slave_id} Voltage Phase {phase.upper()}",
                    "unique_id": f"chargectl_{slave_id}_volts_{phase}",
                    "state_topic": status_topic,
                    "value_template": "{{ value_json.volts_phase_" + phase + " }}",
                    "unit_of_measurement": "V",
                    "device_class": "voltage",
                    "device": device,
                },
            ))

        return configs

    def set_on_control(self, callback) -> None:
        """Set callback for incoming control messages."""
        self._on_control_callback = callback
        if self._client:
            self._client.subscribe(f"{TOPIC_PREFIX}/control/#")

    def _on_connect(self, client, userdata, flags, rc, properties=None):
        logger.info("MQTT connected (rc=%s)", rc)
        for topic in self.get_subscribe_topics():
            client.subscribe(topic)
            logger.debug("Subscribed to %s", topic)
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
