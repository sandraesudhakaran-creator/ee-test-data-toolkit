import pytest

from ee_toolkit.signals import Message, Signal


def test_roundtrip_unsigned_with_factor():
    s = Signal("v", 0, 16, factor=0.01)
    assert s.decode(s.to_raw(123.45).to_bytes(2, "little")) == pytest.approx(123.45)


def test_signed_negative_value():
    s = Signal("i", 0, 16, factor=0.1, signed=True)
    raw = s.to_raw(-12.3)
    assert s.decode(raw.to_bytes(2, "little")) == pytest.approx(-12.3)


def test_offset():
    s = Signal("t", 0, 8, offset=-40)
    assert s.decode(bytes([65])) == 25


def test_value_that_does_not_fit_raises():
    with pytest.raises(ValueError):
        Signal("x", 0, 8).to_raw(300)


def test_message_with_sub_byte_signal_does_not_clobber_neighbours(db):
    msg = db.messages[0x100]
    data = msg.encode({"VehSpeed": 80.0, "EngineRpm": 2500.0, "AliveCounter": 9})
    out = msg.decode(data)
    assert out["VehSpeed"] == pytest.approx(80.0)
    assert out["EngineRpm"] == pytest.approx(2500.0)
    assert out["AliveCounter"] == 9


def test_database_lookup(db):
    assert db.message_for_signal("BattTemp").name == "Battery"
    assert set(db.messages) == {0x100, 0x200}


def test_message_unknown_signal():
    with pytest.raises(KeyError):
        Message(1, "m", 1, 10).signal("nope")
