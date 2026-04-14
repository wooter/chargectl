"""chargectl entry point."""

from __future__ import annotations

import argparse
import logging
import signal
import sys
import time

from chargectl import __version__
from chargectl.config import load_config
from chargectl.charger import SlaveState, TWCSlave
from chargectl.modulation import ModulationEngine
from chargectl.mqtt_client import ChargeMQTT
from chargectl.rs485 import TWCMaster

logger = logging.getLogger("chargectl")

_running = True


def _handle_signal(sig, frame):
    global _running
    logger.info("Received signal %d, shutting down...", sig)
    _running = False


def _calibrated_kwh(slave_id_hex: str, raw_kwh: int, chargers_config: dict) -> int:
    """Apply kWh baseline calibration if configured."""
    cal = chargers_config.get(slave_id_hex, {})
    if "kwh_real" in cal and "kwh_counter" in cal:
        return cal["kwh_real"] + (raw_kwh - cal["kwh_counter"])
    return raw_kwh


def run_loop(
    twc: TWCMaster,
    mqtt_client: ChargeMQTT,
    engine: ModulationEngine,
    chargers_config: dict | None = None,
) -> None:
    """Main control loop.

    Runs at ~1 iteration per second, matching TWCManager's proven cadence:
    1. Send heartbeat to one slave
    2. Wait for response
    3. Read and process all available messages
    4. Calculate modulation (once per full cycle through all slaves)
    """
    global _running

    if chargers_config is None:
        chargers_config = {}
    ha_discovery_sent: set[str] = set()
    last_power_poll_time = 0.0
    last_heartbeat_time = 0.0
    slave_index = 0
    allocation: dict[bytes, int] = {}

    logger.info("Sending link ready announcements...")
    twc.send_linkready()
    logger.info("Entering main loop")

    while _running:
        now = time.time()

        # 1. Read and process any available RS-485 messages
        messages = twc.read_and_process()
        for msg in messages:
            slave_id = msg["slave_id"]
            slave_id_hex = slave_id.hex()

            if msg["type"] == "linkready":
                if slave_id not in twc.slaves:
                    slave = TWCSlave(twc_id=slave_id, max_amps=msg["max_amps"])
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

                    if slave_id_hex not in ha_discovery_sent:
                        mqtt_client.publish_ha_discovery(slave_id_hex)
                        ha_discovery_sent.add(slave_id_hex)

                    status = {
                        "state": slave.state.name.lower(),
                        "amps_actual": round(slave.amps_actual, 2),
                        "amps_offered": round(slave.amps_offered, 2),
                        "power_w": round(slave.amps_actual * 230 * 3, 0),
                        "volts_phase_a": slave.volts_phase_a,
                        "volts_phase_b": slave.volts_phase_b,
                        "volts_phase_c": slave.volts_phase_c,
                    }
                    if slave.lifetime_kwh is not None:
                        status["lifetime_kwh"] = _calibrated_kwh(
                            slave_id_hex, slave.lifetime_kwh, chargers_config
                        )
                    mqtt_client.publish_status(slave_id_hex, status)

            elif msg["type"] == "power_status":
                slave = twc.slaves.get(slave_id)
                if slave:
                    slave.lifetime_kwh = msg["kwh"]
                    slave.update_voltages(*msg["volts"])

        # 2. If we have slaves, send heartbeat to ONE slave per second
        #    (round-robin, like TWCManager does)
        now = time.time()
        slave_list = list(twc.slaves.items())
        if slave_list and now - last_heartbeat_time >= 1.0:
            if slave_index >= len(slave_list):
                slave_index = 0

            slave_id, slave = slave_list[slave_index]
            slave_index += 1

            # Recompute total budget and per-slave allocation at start of cycle
            if slave_index == 1:
                power, voltage = mqtt_client.get_measurements()
                engine.calculate(power, voltage)

                active = [
                    sid for sid, s in slave_list
                    if s.state in (
                        SlaveState.CHARGING,
                        SlaveState.STARTING,
                        SlaveState.PLUGGED_READY,
                    )
                ]
                shares = engine.allocate(len(active))
                allocation = dict(zip(active, shares))

            offered = allocation.get(slave_id, 0)
            twc.send_heartbeat(slave, offered)
            last_heartbeat_time = now

            # Check for stale slaves
            if slave.is_stale():
                logger.warning("TWC slave %s is stale, removing", slave_id.hex())
                del twc.slaves[slave_id]
                slave_index = 0

        # 3. Poll kWh and voltages every 60 seconds
        if now - last_power_poll_time >= 60 and twc.slaves:
            for slave in twc.slaves.values():
                twc.request_power_status(slave)
            last_power_poll_time = now

        # 4. Brief sleep to prevent CPU spin when no data available
        #    The actual pacing is handled by read_and_process() which waits
        #    for serial data, and the 1-heartbeat-per-cycle cadence
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

    config = load_config(args.config)

    log_level = getattr(logging, config.log_level.upper(), logging.INFO)
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        datefmt="%H:%M:%S",
    )
    logger.info("chargectl %s starting", __version__)

    twc = TWCMaster(port=config.rs485_port, baud=config.rs485_baud)
    mqtt_client = ChargeMQTT(config)
    engine = ModulationEngine(
        max_amps=config.max_amps_per_phase,
        margin_amps=config.margin_amps,
    )

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

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    try:
        twc.open()
        mqtt_client.connect()
        run_loop(twc, mqtt_client, engine, config.chargers)
    except Exception:
        logger.exception("Fatal error")
        sys.exit(1)
    finally:
        logger.info("Shutting down...")
        for slave in twc.slaves.values():
            twc.send_heartbeat(slave, 0)
        time.sleep(0.5)
        mqtt_client.disconnect()
        twc.close()
        logger.info("Goodbye")


if __name__ == "__main__":
    main()
