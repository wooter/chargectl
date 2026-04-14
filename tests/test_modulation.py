import time
from chargectl.modulation import ModulationEngine


def test_initial_state_is_zero():
    engine = ModulationEngine(max_amps=20, margin_amps=1)
    assert engine.desired_amps == 0


def test_ramp_up_when_free_capacity():
    engine = ModulationEngine(max_amps=20, margin_amps=1)
    engine.last_change_time = 0
    # 1150/230 = 5A, free = 20-5-1 = 14 > margin(1), ramp up
    # From 0, +1 = 1, < 6 (TWC min), snap to 6
    result = engine.calculate(
        power_per_phase=[1150, 800, 900],
        voltage_per_phase=[230, 230, 230],
    )
    assert result == 6
    assert engine.desired_amps == 6


def test_ramp_down_when_tight():
    engine = ModulationEngine(max_amps=20, margin_amps=1)
    engine.desired_amps = 10
    engine.last_change_time = 0
    # 4370/230 = 19A, free = 20-19-1 = 0 < 1, ramp down
    result = engine.calculate(
        power_per_phase=[4370, 2000, 2000],
        voltage_per_phase=[230, 230, 230],
    )
    assert result == 9


def test_emergency_drop():
    engine = ModulationEngine(max_amps=20, margin_amps=1)
    engine.desired_amps = 12
    engine.last_change_time = 0
    # 5060/230 = 22A, free = 20-22-1 = -3, emergency drop by 3
    result = engine.calculate(
        power_per_phase=[5060, 2000, 2000],
        voltage_per_phase=[230, 230, 230],
    )
    assert result == 9


def test_emergency_drop_to_zero():
    engine = ModulationEngine(max_amps=20, margin_amps=1)
    engine.desired_amps = 8
    engine.last_change_time = 0
    # 6900/230 = 30A, free = -11, drop to 0
    result = engine.calculate(
        power_per_phase=[6900, 2000, 2000],
        voltage_per_phase=[230, 230, 230],
    )
    assert result == 0


def test_twc_minimum_floor():
    engine = ModulationEngine(max_amps=20, margin_amps=1)
    engine.desired_amps = 7
    engine.last_change_time = 0
    # 4370/230 = 19A, free = 0 < 1, ramp down to 6 (still >= 6, OK)
    result = engine.calculate(
        power_per_phase=[4370, 2000, 2000],
        voltage_per_phase=[230, 230, 230],
    )
    assert result == 6


def test_below_minimum_snaps_to_zero():
    engine = ModulationEngine(max_amps=20, margin_amps=1)
    engine.desired_amps = 6
    engine.last_change_time = 0
    # 4370/230 = 19A, free = 0 < 1, ramp down to 5, < 6 -> snap to 0
    result = engine.calculate(
        power_per_phase=[4370, 2000, 2000],
        voltage_per_phase=[230, 230, 230],
    )
    assert result == 0


def test_respects_rate_limit():
    engine = ModulationEngine(max_amps=20, margin_amps=1)
    engine.desired_amps = 10
    engine.last_change_time = time.time()
    result = engine.calculate(
        power_per_phase=[1150, 800, 900],
        voltage_per_phase=[230, 230, 230],
    )
    assert result == 10


def test_emergency_ignores_rate_limit():
    engine = ModulationEngine(max_amps=20, margin_amps=1)
    engine.desired_amps = 12
    engine.last_change_time = time.time()
    # 5060/230 = 22A, free = -3, emergency
    result = engine.calculate(
        power_per_phase=[5060, 2000, 2000],
        voltage_per_phase=[230, 230, 230],
    )
    assert result == 9


def test_watchdog_no_data():
    engine = ModulationEngine(max_amps=20, margin_amps=1)
    engine.desired_amps = 16
    engine.last_data_time = time.time() - 20
    result = engine.calculate(
        power_per_phase=[None, None, None],
        voltage_per_phase=[None, None, None],
    )
    assert result == 0


def test_allocate_no_slaves():
    engine = ModulationEngine(max_amps=20, margin_amps=1)
    engine.desired_amps = 12
    assert engine.allocate(0, 0) == ([], [])


def test_allocate_one_ready_enough_budget():
    engine = ModulationEngine(max_amps=20, margin_amps=1)
    engine.desired_amps = 11
    assert engine.allocate(0, 1) == ([], [11])


def test_allocate_one_ready_below_min_does_not_start():
    engine = ModulationEngine(max_amps=20, margin_amps=1)
    engine.desired_amps = 5
    assert engine.allocate(0, 1) == ([], [0])


def test_allocate_two_ready_splits_evenly():
    engine = ModulationEngine(max_amps=20, margin_amps=1)
    engine.desired_amps = 14
    assert engine.allocate(0, 2) == ([], [7, 7])


def test_allocate_two_ready_tight_budget_starts_one():
    # 11A total, 2 ready: starting both would give 5A each (<6A),
    # so only one gets started at 11A, other stays at 0
    engine = ModulationEngine(max_amps=20, margin_amps=1)
    engine.desired_amps = 11
    assert engine.allocate(0, 2) == ([], [11, 0])


def test_allocate_charging_always_gets_min_even_over_budget():
    # Two cars already charging, budget says 10A but we can't stop them.
    # Each must get at least 6A; total draw will overshoot budget.
    engine = ModulationEngine(max_amps=20, margin_amps=1)
    engine.desired_amps = 10
    assert engine.allocate(2, 0) == ([6, 6], [])


def test_allocate_charging_at_zero_budget():
    # Emergency: desired=0, but one car already charging — hold at 6A
    engine = ModulationEngine(max_amps=20, margin_amps=1)
    engine.desired_amps = 0
    assert engine.allocate(1, 0) == ([6], [])


def test_allocate_charging_plus_ready_enough_budget():
    engine = ModulationEngine(max_amps=20, margin_amps=1)
    engine.desired_amps = 14
    # 14 across 2: 7 each
    assert engine.allocate(1, 1) == ([7], [7])


def test_allocate_charging_plus_ready_no_budget_to_start_ready():
    # One charging at min, 6A budget left after floor → not enough for ready
    engine = ModulationEngine(max_amps=20, margin_amps=1)
    engine.desired_amps = 10
    # remaining = 10-6 = 4 < 6 → don't start ready; charging gets 10
    assert engine.allocate(1, 1) == ([10], [0])


def test_allocate_charging_plus_ready_exactly_enough():
    engine = ModulationEngine(max_amps=20, margin_amps=1)
    engine.desired_amps = 12
    # remaining = 6 → can start ready at 6A, charging at 6A
    assert engine.allocate(1, 1) == ([6], [6])


def test_allocate_two_charging_plus_one_ready_starts_third():
    engine = ModulationEngine(max_amps=20, margin_amps=1)
    engine.desired_amps = 18
    assert engine.allocate(2, 1) == ([6, 6], [6])


def test_allocate_split_remainder_goes_to_charging_first():
    engine = ModulationEngine(max_amps=20, margin_amps=1)
    engine.desired_amps = 13
    # per = 6, leftover = 1 → first slot gets +1
    assert engine.allocate(1, 1) == ([7], [6])


def test_worst_phase_used():
    engine = ModulationEngine(max_amps=20, margin_amps=1)
    engine.desired_amps = 10
    engine.last_change_time = 0
    # Phase 2: 4140/230 = 18A, free = 20-18-1 = 1 > margin(1)? No, not >, equal → no change
    # Phase 2: 4370/230 = 19A, free = 20-19-1 = 0 < 1 → ramp down
    result = engine.calculate(
        power_per_phase=[1000, 4370, 2000],
        voltage_per_phase=[230, 230, 230],
    )
    assert result == 9
