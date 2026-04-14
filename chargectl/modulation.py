"""Power modulation engine for EV charging."""

from __future__ import annotations

import logging
import time

logger = logging.getLogger(__name__)

TWC_MIN_AMPS = 6
RATE_LIMIT_SECONDS = 5
WATCHDOG_TIMEOUT = 15


class ModulationEngine:
    """Calculates safe charging amps based on per-phase power measurements.

    `desired_amps` is the TOTAL allocation across all active chargers, not
    per-slave. Use `allocate(n)` to split it across n active slaves.
    """

    def __init__(self, max_amps: int, margin_amps: int):
        self.max_amps = max_amps
        self.margin_amps = margin_amps
        self.desired_amps = 0
        self.last_change_time = 0.0
        self.last_data_time = time.time()

    def allocate(self, n_charging: int, n_ready: int) -> tuple[list[int], list[int]]:
        """Split desired_amps across charging and plugged-ready slaves.

        Returns (charging_shares, ready_shares).

        Protocol constraint: a P2 TWC cannot be stopped via RS-485 once a car
        is drawing; forcing 0A repeatedly would fault the car. So every
        already-charging slave is guaranteed at least TWC_MIN_AMPS, even if
        that overshoots desired_amps. A plugged-ready slave is only started
        (given >=TWC_MIN_AMPS) if budget permits on top of charging cars.
        """
        charging_shares = [TWC_MIN_AMPS] * n_charging
        ready_shares = [0] * n_ready

        total = self.desired_amps
        remaining = total - TWC_MIN_AMPS * n_charging

        if remaining <= 0:
            return charging_shares, ready_shares

        n_starts = min(n_ready, remaining // TWC_MIN_AMPS)
        active = n_charging + n_starts
        if active == 0:
            return charging_shares, ready_shares

        per = max(TWC_MIN_AMPS, total // active)
        leftover = max(0, total - per * active)

        for i in range(n_charging):
            charging_shares[i] = per + (1 if i < leftover else 0)
        for i in range(n_starts):
            j = n_charging + i
            ready_shares[i] = per + (1 if j < leftover else 0)

        return charging_shares, ready_shares

    def calculate(
        self,
        power_per_phase: list[float | None],
        voltage_per_phase: list[float | None],
    ) -> int:
        """Calculate desired charging amps based on current power measurements.

        Returns the new desired amps value (0 or >= TWC_MIN_AMPS).
        """
        if any(v is None for v in power_per_phase) or any(
            v is None for v in voltage_per_phase
        ):
            if time.time() - self.last_data_time > WATCHDOG_TIMEOUT:
                logger.warning("No power data for %ds, stopping charging", WATCHDOG_TIMEOUT)
                self.desired_amps = 0
                return 0
            return self.desired_amps

        self.last_data_time = time.time()

        amps_per_phase = []
        for power, voltage in zip(power_per_phase, voltage_per_phase):
            if voltage > 0:
                amps_per_phase.append(power / voltage)
            else:
                amps_per_phase.append(0)

        worst_phase_amps = max(amps_per_phase)
        free_amps = self.max_amps - worst_phase_amps - self.margin_amps

        now = time.time()
        new_amps = self.desired_amps

        is_emergency = free_amps < 0

        if is_emergency:
            new_amps = max(0, int(self.desired_amps + free_amps))
        elif now - self.last_change_time < RATE_LIMIT_SECONDS:
            return self.desired_amps
        elif free_amps < 1:
            new_amps = self.desired_amps - 1
        elif free_amps > self.margin_amps:
            new_amps = self.desired_amps + 1
        else:
            return self.desired_amps

        if 0 < new_amps < TWC_MIN_AMPS:
            if self.desired_amps == 0:
                new_amps = TWC_MIN_AMPS
            else:
                new_amps = 0

        new_amps = max(0, min(new_amps, self.max_amps - self.margin_amps))

        if new_amps != self.desired_amps:
            self.last_change_time = now
            if is_emergency:
                logger.warning(
                    "Emergency ramp-down: worst_phase=%.1fA free=%.1fA -> %dA",
                    worst_phase_amps, free_amps, new_amps,
                )
            elif new_amps < self.desired_amps:
                logger.info("Ramp down: free=%.1fA -> %dA", free_amps, new_amps)
            else:
                logger.info("Ramp up: free=%.1fA -> %dA", free_amps, new_amps)

        self.desired_amps = new_amps
        return new_amps
