"""TWC slave state management."""

import time
from enum import IntEnum


class SlaveState(IntEnum):
    READY = 0x00
    CHARGING = 0x01
    ERROR = 0x02
    PLUGGED_NO_CHARGE = 0x03
    PLUGGED_READY = 0x04
    BUSY = 0x05
    STARTING = 0x08


class TWCSlave:
    """Tracks the state of a single TWC Gen 2 slave."""

    def __init__(self, twc_id: bytes, max_amps: float):
        self.twc_id = twc_id
        self.max_amps = max_amps
        self.protocol_version = 1
        self.state = SlaveState.READY
        self.reported_amps_max = 0.0
        self.amps_actual = 0.0
        self.amps_offered = 0.0
        self.volts_phase_a = 0
        self.volts_phase_b = 0
        self.volts_phase_c = 0
        self.lifetime_kwh = 0
        self.last_heartbeat_time = time.time()

    def update_from_heartbeat(self, data: bytes) -> None:
        """Update slave state from a heartbeat response."""
        self.last_heartbeat_time = time.time()
        try:
            self.state = SlaveState(data[0])
        except ValueError:
            self.state = SlaveState.READY
        self.reported_amps_max = ((data[1] << 8) + data[2]) / 100
        self.amps_actual = ((data[3] << 8) + data[4]) / 100

    def update_voltages(self, phase_a: int, phase_b: int, phase_c: int) -> None:
        """Update voltage readings from extended power status message."""
        self.volts_phase_a = phase_a
        self.volts_phase_b = phase_b
        self.volts_phase_c = phase_c

    def build_master_heartbeat(self, desired_amps: float) -> bytes:
        """Build the heartbeat data to send to this slave."""
        hundredths = int(desired_amps * 100)
        self.amps_offered = desired_amps

        if desired_amps == 0:
            command = 0x05
        elif self.protocol_version == 2:
            command = 0x09
        else:
            command = 0x05

        data = bytearray([
            command,
            (hundredths >> 8) & 0xFF,
            hundredths & 0xFF,
            0x00, 0x00, 0x00, 0x00,
        ])

        if self.protocol_version == 2:
            data.extend([0x00, 0x00])

        return bytes(data)

    def is_stale(self, timeout: float = 26.0) -> bool:
        """Check if we haven't heard from this slave in too long."""
        return (time.time() - self.last_heartbeat_time) > timeout
