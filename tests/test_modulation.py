import time
from chargectl.modulation import ModulationEngine


def test_initial_state_is_zero():
    engine = ModulationEngine(max_amps=20, margin_amps=3)
    assert engine.desired_amps == 0


def test_ramp_up_when_free_capacity():
    engine = ModulationEngine(max_amps=20, margin_amps=3)
    engine.last_change_time = 0
    # House using 5A on worst phase (1150W/230V=5A), free = 20-5-3 = 12 > 4, ramp up
    # From 0, +1 = 1 which is < 6 (TWC min), so snaps to 6
    result = engine.calculate(
        power_per_phase=[1150, 800, 900],
        voltage_per_phase=[230, 230, 230],
    )
    assert result == 6
    assert engine.desired_amps == 6


def test_ramp_down_when_tight():
    engine = ModulationEngine(max_amps=20, margin_amps=3)
    engine.desired_amps = 10
    engine.last_change_time = 0
    # 3680/230 = 16A, free = 20-16-3 = 1 < 2, ramp down
    result = engine.calculate(
        power_per_phase=[3680, 2000, 2000],
        voltage_per_phase=[230, 230, 230],
    )
    assert result == 9


def test_emergency_drop():
    engine = ModulationEngine(max_amps=20, margin_amps=3)
    engine.desired_amps = 12
    engine.last_change_time = 0
    # 5060/230 = 22A, free = 20-22-3 = -5, emergency drop by 5
    result = engine.calculate(
        power_per_phase=[5060, 2000, 2000],
        voltage_per_phase=[230, 230, 230],
    )
    assert result == 7


def test_emergency_drop_to_zero():
    engine = ModulationEngine(max_amps=20, margin_amps=3)
    engine.desired_amps = 8
    engine.last_change_time = 0
    # 6900/230 = 30A, free = -13, drop clamps to 0
    result = engine.calculate(
        power_per_phase=[6900, 2000, 2000],
        voltage_per_phase=[230, 230, 230],
    )
    assert result == 0


def test_twc_minimum_floor():
    engine = ModulationEngine(max_amps=20, margin_amps=3)
    engine.desired_amps = 7
    engine.last_change_time = 0
    # free = 1, ramp down to 6 (still >= 6, OK)
    result = engine.calculate(
        power_per_phase=[3680, 2000, 2000],
        voltage_per_phase=[230, 230, 230],
    )
    assert result == 6


def test_below_minimum_snaps_to_zero():
    engine = ModulationEngine(max_amps=20, margin_amps=3)
    engine.desired_amps = 6
    engine.last_change_time = 0
    # free = 1, ramp down to 5, < 6 -> snap to 0
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
    assert result == 10  # no change, rate limited


def test_emergency_ignores_rate_limit():
    engine = ModulationEngine(max_amps=20, margin_amps=3)
    engine.desired_amps = 12
    engine.last_change_time = time.time()  # just changed
    result = engine.calculate(
        power_per_phase=[5060, 2000, 2000],
        voltage_per_phase=[230, 230, 230],
    )
    assert result == 7  # emergency ignores rate limit


def test_watchdog_no_data():
    engine = ModulationEngine(max_amps=20, margin_amps=3)
    engine.desired_amps = 16
    engine.last_data_time = time.time() - 20  # > 15s timeout
    result = engine.calculate(
        power_per_phase=[None, None, None],
        voltage_per_phase=[None, None, None],
    )
    assert result == 0


def test_worst_phase_used():
    engine = ModulationEngine(max_amps=20, margin_amps=3)
    engine.desired_amps = 10
    engine.last_change_time = 0
    # Phase 2 worst: 3500/230 = 15.2A, free = 1.8 < 2, ramp down
    result = engine.calculate(
        power_per_phase=[1000, 3500, 2000],
        voltage_per_phase=[230, 230, 230],
    )
    assert result == 9
