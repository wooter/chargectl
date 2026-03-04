"""RS-485 SLIP framing and TWC protocol."""

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
