from chargectl.rs485 import slip_encode, slip_decode, checksum, build_message, parse_message


def test_slip_encode_no_escaping():
    data = bytes([0xFB, 0xE0, 0x77, 0x77])
    encoded = slip_encode(data)
    assert encoded == bytes([0xC0]) + data + bytes([0xC0])


def test_slip_encode_escapes_c0():
    data = bytes([0xFB, 0xC0, 0xE0])
    encoded = slip_encode(data)
    assert encoded == bytes([0xC0, 0xFB, 0xDB, 0xDC, 0xE0, 0xC0])


def test_slip_encode_escapes_db():
    data = bytes([0xFB, 0xDB, 0xE0])
    encoded = slip_encode(data)
    assert encoded == bytes([0xC0, 0xFB, 0xDB, 0xDD, 0xE0, 0xC0])


def test_slip_decode_roundtrip():
    original = bytes([0xFB, 0xE0, 0xC0, 0xDB, 0x01])
    encoded = slip_encode(original)
    inner = encoded[1:-1]
    decoded = slip_decode(inner)
    assert decoded == original


def test_checksum():
    data = bytes([0xFB, 0xE0, 0x77, 0x77, 0x00, 0x00, 0x09, 0x06, 0x40, 0x00, 0x00, 0x00, 0x00])
    cs = checksum(data)
    expected = sum(data[1:]) & 0xFF
    assert cs == expected


def test_build_message():
    data = bytes([0xFB, 0xE0, 0x77, 0x77, 0x00, 0x01])
    msg = build_message(data)
    assert msg[0] == 0xC0
    assert msg[-1] == 0xC0
    inner = slip_decode(msg[1:-1])
    assert checksum(inner[:-1]) == inner[-1]


def test_parse_message_valid():
    data = bytes([0xFB, 0xE0, 0x77, 0x77, 0x00, 0x01])
    msg = build_message(data)
    parsed = parse_message(msg)
    assert parsed == data


def test_parse_message_bad_checksum():
    data = bytes([0xFB, 0xE0, 0x77, 0x77, 0x00, 0x01])
    msg = build_message(data)
    corrupted = bytearray(msg)
    corrupted[3] = 0xFF
    parsed = parse_message(bytes(corrupted))
    assert parsed is None
