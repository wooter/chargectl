"""RS-485 SLIP framing and TWC protocol."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

SLIP_END = 0xC0
SLIP_ESC = 0xDB
SLIP_ESC_END = 0xDC
SLIP_ESC_ESC = 0xDD


def slip_encode(data: bytes) -> bytes:
    """SLIP-encode data and wrap in 0xC0 delimiters."""
    out = bytearray([SLIP_END])
    for b in data:
        if b == SLIP_END:
            out.extend([SLIP_ESC, SLIP_ESC_END])
        elif b == SLIP_ESC:
            out.extend([SLIP_ESC, SLIP_ESC_ESC])
        else:
            out.append(b)
    out.append(SLIP_END)
    return bytes(out)


def slip_decode(data: bytes) -> bytes:
    """SLIP-decode data (without 0xC0 delimiters)."""
    out = bytearray()
    i = 0
    while i < len(data):
        if data[i] == SLIP_ESC:
            i += 1
            if i < len(data):
                if data[i] == SLIP_ESC_END:
                    out.append(SLIP_END)
                elif data[i] == SLIP_ESC_ESC:
                    out.append(SLIP_ESC)
                else:
                    out.append(data[i])
        else:
            out.append(data[i])
        i += 1
    return bytes(out)


def checksum(data: bytes) -> int:
    """Calculate TWC checksum: sum of all bytes after the first, masked to 8 bits."""
    return sum(data[1:]) & 0xFF


def build_message(data: bytes) -> bytes:
    """Build a complete SLIP-framed message with checksum."""
    cs = checksum(data)
    return slip_encode(data + bytes([cs]))


def parse_message(raw: bytes) -> bytes | None:
    """Parse a SLIP-framed message. Returns data without checksum, or None if invalid."""
    if len(raw) < 4 or raw[0] != SLIP_END or raw[-1] != SLIP_END:
        return None
    inner = slip_decode(raw[1:-1])
    if len(inner) < 2:
        return None
    data, cs = inner[:-1], inner[-1]
    if checksum(data) != cs:
        logger.debug("Checksum mismatch: expected %02X, got %02X", checksum(data), cs)
        return None
    return data


import serial
import time
from chargectl.charger import TWCSlave

FUNC_MASTER_LINKREADY1 = bytes([0xFC, 0xE1])
FUNC_MASTER_LINKREADY2 = bytes([0xFB, 0xE2])
FUNC_MASTER_HEARTBEAT = bytes([0xFB, 0xE0])
FUNC_SLAVE_LINKREADY = bytes([0xFD, 0xE2])
FUNC_SLAVE_HEARTBEAT = bytes([0xFD, 0xE0])
FUNC_SLAVE_POWER_STATUS = bytes([0xFD, 0xEB])


class TWCMaster:
    """Fake TWC master that communicates with slave TWCs over RS-485."""

    def __init__(self, port: str, baud: int = 9600):
        self.master_id = bytes([0x77, 0x77])
        self.port = port
        self.baud = baud
        self.serial: serial.Serial | None = None
        self.slaves: dict[bytes, TWCSlave] = {}
        self._read_buffer = bytearray()

    def open(self) -> None:
        """Open the serial port."""
        self.serial = serial.Serial(self.port, self.baud, timeout=0)
        logger.info("RS-485 opened on %s at %d baud", self.port, self.baud)

    def close(self) -> None:
        """Close the serial port."""
        if self.serial:
            self.serial.close()
            logger.info("RS-485 closed")

    def send_linkready(self) -> None:
        """Send master link ready announcements (5 each type)."""
        for func in [FUNC_MASTER_LINKREADY1, FUNC_MASTER_LINKREADY2]:
            for _ in range(5):
                data = func + self.master_id + bytes(8)
                msg = build_message(data)
                self._send_raw(msg)
                time.sleep(0.1)

    def send_heartbeat(self, slave: TWCSlave, desired_amps: float) -> None:
        """Send a master heartbeat to a slave with the desired amperage."""
        heartbeat_data = slave.build_master_heartbeat(desired_amps)
        msg = self._build_heartbeat_message(slave.twc_id, heartbeat_data)
        self._send_raw(msg)
        logger.debug(
            "TX heartbeat to %s: %.1fA (cmd=%02X)",
            slave.twc_id.hex(), desired_amps, heartbeat_data[0],
        )

    def read_and_process(self) -> list[dict]:
        """Read available data from serial and process complete messages."""
        results = []
        if not self.serial:
            return results

        data = self.serial.read(256)
        if data:
            self._read_buffer.extend(data)
            logger.debug("RX raw: %s", data.hex())

        while True:
            start = self._find_frame_start()
            if start is None:
                break
            end = self._find_frame_end(start + 1)
            if end is None:
                break
            frame = bytes(self._read_buffer[start : end + 1])
            self._read_buffer = self._read_buffer[end + 1 :]
            parsed_data = parse_message(frame)
            if parsed_data:
                result = self._parse_incoming(parsed_data)
                if result:
                    results.append(result)

        return results

    def _build_heartbeat_message(self, slave_id: bytes, heartbeat_data: bytes) -> bytes:
        """Build a complete master heartbeat message."""
        data = FUNC_MASTER_HEARTBEAT + self.master_id + slave_id + heartbeat_data
        return build_message(data)

    def _parse_incoming(self, data: bytes) -> dict | None:
        """Parse an incoming message from a slave."""
        if len(data) < 6:
            return None

        func = data[0:2]
        slave_id = bytes(data[2:4])

        if func == FUNC_SLAVE_LINKREADY:
            max_amps = ((data[6] << 8) + data[7]) / 100
            logger.info("Slave %s linked: max %.1fA", slave_id.hex(), max_amps)
            return {"type": "linkready", "slave_id": slave_id, "max_amps": max_amps}

        elif func == FUNC_SLAVE_HEARTBEAT:
            heartbeat_data = data[6:]
            return {"type": "heartbeat", "slave_id": slave_id, "heartbeat_data": heartbeat_data}

        elif func == FUNC_SLAVE_POWER_STATUS:
            if len(data) >= 14:
                volts_a = ((data[6] << 8) + data[7])
                volts_b = ((data[8] << 8) + data[9])
                volts_c = ((data[10] << 8) + data[11])
                return {
                    "type": "power_status",
                    "slave_id": slave_id,
                    "volts": (volts_a, volts_b, volts_c),
                }
            return None

        return None

    def _send_raw(self, data: bytes) -> None:
        """Send raw bytes over serial."""
        if self.serial:
            self.serial.write(data)
            logger.debug("TX raw: %s", data.hex())

    def _find_frame_start(self) -> int | None:
        """Find the index of the next SLIP_END start byte."""
        try:
            return self._read_buffer.index(SLIP_END)
        except ValueError:
            return None

    def _find_frame_end(self, start: int) -> int | None:
        """Find the index of the closing SLIP_END byte after start."""
        try:
            return self._read_buffer.index(SLIP_END, start)
        except ValueError:
            return None
