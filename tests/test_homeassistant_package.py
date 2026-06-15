from pathlib import Path

import yaml


PACKAGE_PATH = (
    Path(__file__).resolve().parents[1]
    / "homeassistant"
    / "packages"
    / "chargectl_production.yaml"
)
TARIFF_PACKAGE_PATH = (
    Path(__file__).resolve().parents[1]
    / "homeassistant"
    / "packages"
    / "chargectl_tariff_sensor.yaml"
)


def _load_package():
    with PACKAGE_PATH.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _load_tariff_package():
    with TARIFF_PACKAGE_PATH.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _automation_by_id(package, automation_id):
    for automation in package.get("automation", []):
        if automation.get("id") == automation_id:
            return automation
    return None


def test_gate_c_startup_resync_automation_wired():
    package = _load_package()
    startup = _automation_by_id(package, "chargectl_sync_control_on_ha_start")
    assert startup is not None

    triggers = startup.get("trigger", [])
    assert {"platform": "homeassistant", "event": "start"} in triggers

    topics = {
        step.get("data", {}).get("topic")
        for step in startup.get("action", [])
        if isinstance(step, dict)
    }
    assert "chargectl/control/max_amps" in topics
    assert "chargectl/control/enabled" in topics


def test_gate_d_cheap_window_time_triggers_wired():
    package = _load_package()

    enable_window = _automation_by_id(package, "chargectl_night_window_enable")
    disable_window = _automation_by_id(package, "chargectl_day_window_disable")

    assert enable_window is not None
    assert disable_window is not None

    enable_triggers = enable_window.get("trigger", [])
    disable_triggers = disable_window.get("trigger", [])

    assert {
        "platform": "time",
        "at": "input_datetime.chargectl_cheap_start",
    } in enable_triggers
    assert {
        "platform": "time",
        "at": "input_datetime.chargectl_cheap_end",
    } in disable_triggers


def test_hom13_tariff_package_has_signal_trigger_wiring():
    package = _load_tariff_package()
    tariff_apply = _automation_by_id(package, "chargectl_tariff_apply_signal")
    assert tariff_apply is not None

    triggers = tariff_apply.get("trigger", [])
    state_triggers = [
        trigger
        for trigger in triggers
        if isinstance(trigger, dict) and trigger.get("platform") == "state"
    ]
    assert len(state_triggers) == 1

    tracked_entities = set(state_triggers[0].get("entity_id", []))
    assert "sensor.grid_tariff_eur_kwh" in tracked_entities
    assert "binary_sensor.grid_tariff_data_fresh" in tracked_entities
    assert "input_boolean.chargectl_tariff_automation_enabled" in tracked_entities


def test_hom13_tariff_package_stale_data_uses_emergency_hold():
    package = _load_tariff_package()
    tariff_apply = _automation_by_id(package, "chargectl_tariff_apply_signal")
    assert tariff_apply is not None

    action = tariff_apply.get("action", [])
    assert action
    choose_block = action[0].get("choose", [])
    sequence_steps = []
    for branch in choose_block:
        sequence_steps.extend(branch.get("sequence", []))

    services = {
        step.get("service")
        for step in sequence_steps
        if isinstance(step, dict) and step.get("service")
    }
    assert "script.chargectl_tariff_emergency_hold" in services
