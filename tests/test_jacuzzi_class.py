"""Checks that JacuzziRS485 copies the decoded status onto its attributes."""

import asyncio

import jacuzziRS485
from frames import JACUZZI_STATUS_0x16


def make_spa():
    return jacuzziRS485.JacuzziRS485("127.0.0.1")


def feed(spa, raw):
    asyncio.run(spa.parse_status_update(bytearray(raw)))


def test_status_update_populates_attributes():
    spa = make_spa()
    feed(spa, bytes.fromhex(JACUZZI_STATUS_0x16))
    assert spa.get_spatime() == "16:18"
    assert spa.get_spadate() == "11/7/2022"
    assert spa.curtemp == 19.0
    assert spa.get_settemp() == 19.0
    assert spa.get_pump(1) == 2  # pump 1 on high
    assert spa.get_pump(2) == 0
    assert spa.isUVOn == 0
    assert spa.statusByte17 == 1  # flow switch
    assert spa.statusByte21 == 66  # second temperature sensor
    assert spa.lastupd > 0


def test_fahrenheit_frame_is_not_halved_on_first_packet():
    # Regression test: the scale must be read before temperatures convert
    spa = make_spa()
    raw = bytearray.fromhex(JACUZZI_STATUS_0x16)
    raw[18] = 0x80
    feed(spa, raw)
    assert spa.curtemp == 38.0
    assert spa.get_settemp() == 38.0


def test_identical_packets_are_skipped():
    spa = make_spa()
    raw = bytes.fromhex(JACUZZI_STATUS_0x16)
    feed(spa, raw)
    spa.lastupd = 0
    feed(spa, raw)
    assert spa.lastupd == 0  # unchanged packet did not re-parse


def test_bad_status_packet_is_ignored_not_fatal():
    spa = make_spa()
    feed(spa, bytes.fromhex(JACUZZI_STATUS_0x16)[:20])
    assert spa.lastupd == 0
