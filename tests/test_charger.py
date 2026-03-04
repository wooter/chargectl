import time
from chargectl.charger import TWCSlave, SlaveState


def test_create_slave():
    slave = TWCSlave(twc_id=bytes([0x29, 0x19]), max_amps=32.0)
    assert slave.twc_id == bytes([0x29, 0x19])
    assert slave.max_amps == 32.0
    assert slave.amps_actual == 0.0
    assert slave.amps_offered == 0.0
    assert slave.state == SlaveState.READY
    assert slave.protocol_version == 1


def test_update_from_heartbeat_v1():
    slave = TWCSlave(twc_id=bytes([0x29, 0x19]), max_amps=32.0)
    heartbeat = bytes([0x01, 0x06, 0x40, 0x05, 0xDC, 0x00, 0x00])
    slave.update_from_heartbeat(heartbeat)
    assert slave.state == SlaveState.CHARGING
    assert slave.reported_amps_max == 16.0
    assert slave.amps_actual == 15.0


def test_update_from_heartbeat_v2():
    slave = TWCSlave(twc_id=bytes([0x29, 0x19]), max_amps=32.0)
    slave.protocol_version = 2
    heartbeat = bytes([0x01, 0x06, 0x40, 0x05, 0xDC, 0x00, 0x00, 0x00, 0x00])
    slave.update_from_heartbeat(heartbeat)
    assert slave.state == SlaveState.CHARGING
    assert slave.amps_actual == 15.0


def test_build_heartbeat_data_set_amps():
    slave = TWCSlave(twc_id=bytes([0x29, 0x19]), max_amps=32.0)
    slave.protocol_version = 2
    data = slave.build_master_heartbeat(desired_amps=16.0)
    assert data[0] == 0x09
    assert data[1] == 0x06
    assert data[2] == 0x40


def test_build_heartbeat_data_stop():
    slave = TWCSlave(twc_id=bytes([0x29, 0x19]), max_amps=32.0)
    slave.protocol_version = 2
    data = slave.build_master_heartbeat(desired_amps=0.0)
    assert data[0] == 0x05
    assert data[1] == 0x00
    assert data[2] == 0x00


def test_build_heartbeat_data_v1():
    slave = TWCSlave(twc_id=bytes([0x29, 0x19]), max_amps=32.0)
    slave.protocol_version = 1
    data = slave.build_master_heartbeat(desired_amps=12.0)
    assert data[0] == 0x05
    assert len(data) == 7


def test_is_stale():
    slave = TWCSlave(twc_id=bytes([0x29, 0x19]), max_amps=32.0)
    slave.last_heartbeat_time = time.time() - 30
    assert slave.is_stale(timeout=26)
    assert not slave.is_stale(timeout=60)
