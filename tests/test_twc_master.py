from chargectl.rs485 import TWCMaster, build_message, parse_message, FUNC_MASTER_HEARTBEAT, FUNC_SLAVE_HEARTBEAT, FUNC_SLAVE_LINKREADY


def test_build_master_heartbeat_message():
    master = TWCMaster.__new__(TWCMaster)
    master.master_id = bytes([0x77, 0x77])
    master.slaves = {}
    slave_id = bytes([0x29, 0x19])
    heartbeat_data = bytes([0x09, 0x06, 0x40, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])
    msg = master._build_heartbeat_message(slave_id, heartbeat_data)
    parsed = parse_message(msg)
    assert parsed is not None
    assert parsed[0:2] == bytes([0xFB, 0xE0])
    assert parsed[2:4] == bytes([0x77, 0x77])
    assert parsed[4:6] == bytes([0x29, 0x19])
    assert parsed[6:15] == heartbeat_data


def test_parse_slave_linkready():
    master = TWCMaster.__new__(TWCMaster)
    master.master_id = bytes([0x77, 0x77])
    master.slaves = {}
    data = bytes([
        0xFD, 0xE2,
        0x29, 0x19,
        0x77, 0x77,
        0x0C, 0x80,
        0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    ])
    result = master._parse_incoming(data)
    assert result is not None
    assert result["type"] == "linkready"
    assert result["slave_id"] == bytes([0x29, 0x19])
    assert result["max_amps"] == 32.0


def test_parse_slave_heartbeat():
    master = TWCMaster.__new__(TWCMaster)
    master.master_id = bytes([0x77, 0x77])
    master.slaves = {}
    data = bytes([
        0xFD, 0xE0,
        0x29, 0x19,
        0x77, 0x77,
        0x01,
        0x06, 0x40,
        0x05, 0xDC,
        0x00, 0x00, 0x00, 0x00,
    ])
    result = master._parse_incoming(data)
    assert result is not None
    assert result["type"] == "heartbeat"
    assert result["slave_id"] == bytes([0x29, 0x19])
    assert result["heartbeat_data"][0] == 0x01
