"""Executable specification of the RS485 panel protocol.

These tests use only app/protocol.py, which has no I/O, so the same cases can
be ported to another implementation (e.g. an ESPHome C++ component).
"""

import datetime

import pytest

import protocol as p
from frames import (
    JACUZZI_STATUS_0x16,
    MODULE_IDENT_REQ,
    REAL_FRAMES,
    SET_TEMP_20C,
)


def b(hexstr):
    return bytes.fromhex(hexstr)


# --- CRC and framing -------------------------------------------------------


@pytest.mark.parametrize("name", sorted(REAL_FRAMES))
def test_real_frames_have_valid_crc_and_length(name):
    raw = b(REAL_FRAMES[name])
    frame = p.parse_frame(raw)
    assert frame.raw == raw
    assert raw[1] + 2 == len(raw)


def test_crc_known_values():
    # LEN..PAYLOAD of the two frames logged by this project
    assert p.crc(b("050abf04")) == 0x77
    assert p.crc(b("060abf2028")) == 0xCA


def test_parse_frame_fields():
    frame = p.parse_frame(b(SET_TEMP_20C))
    assert frame.dst == 0x0A
    assert frame.pf == 0xBF
    assert frame.mtype == p.MSG_SET_TEMP
    assert frame.payload == b"\x28"


@pytest.mark.parametrize(
    "raw",
    [
        b""  ,
        b("7e"),
        b("7e050abf04777e")[:-1],  # missing end flag
        b("7e050abf0477ff"),  # wrong end flag
        b("7f050abf04777e"),  # wrong start flag
        b("7e060abf04777e"),  # length byte too big for the frame
        b("7e050abf04787e"),  # bad CRC
    ],
)
def test_parse_frame_rejects_invalid(raw):
    with pytest.raises(p.ProtocolError):
        p.parse_frame(raw)


def test_build_frame_reproduces_real_frames():
    assert p.build_module_ident_req(0x0A).hex() == MODULE_IDENT_REQ
    assert p.build_set_temp(0x0A, 20.0, p.TSCALE_C).hex() == SET_TEMP_20C


def test_build_frame_roundtrip():
    raw = p.build_frame(0x10, p.PF_ADDRESSED, 0xCC, b"\x50\xb5")
    assert raw.hex() == "7e0710bfcc50b58e7e"  # a real Sundance button frame
    frame = p.parse_frame(raw)
    assert (frame.dst, frame.pf, frame.mtype, frame.payload) == (
        0x10,
        0xBF,
        0xCC,
        b"\x50\xb5",
    )


def test_build_frame_rejects_oversize_payload():
    with pytest.raises(p.ProtocolError):
        p.build_frame(0x0A, p.PF_ADDRESSED, 0x01, bytes(200))


# --- Stream splitting ------------------------------------------------------


def test_reader_splits_back_to_back_frames():
    stream = b(MODULE_IDENT_REQ) + b(SET_TEMP_20C) + b(JACUZZI_STATUS_0x16)
    frames = p.FrameReader().feed(stream)
    assert [f.mtype for f in frames] == [0x04, 0x20, 0x16]


def test_reader_handles_any_chunking():
    stream = b(MODULE_IDENT_REQ) + b(JACUZZI_STATUS_0x16) + b(SET_TEMP_20C)
    for size in (1, 2, 3, 7, 13):
        reader = p.FrameReader()
        got = []
        for i in range(0, len(stream), size):
            got.extend(reader.feed(stream[i : i + size]))
        assert [f.mtype for f in got] == [0x04, 0x16, 0x20], size
        assert reader.bad_frames == 0


def test_reader_resyncs_after_garbage():
    stream = b"\x00\x01\x02" + b(MODULE_IDENT_REQ) + b"\xff\xff" + b(SET_TEMP_20C)
    reader = p.FrameReader()
    frames = reader.feed(stream)
    assert [f.mtype for f in frames] == [0x04, 0x20]


def test_reader_drops_bad_crc_and_recovers():
    corrupt = bytearray(b(JACUZZI_STATUS_0x16))
    corrupt[10] ^= 0xFF  # damage a payload byte
    reader = p.FrameReader()
    frames = reader.feed(bytes(corrupt) + b(SET_TEMP_20C))
    assert [f.mtype for f in frames] == [0x20]
    assert reader.bad_frames >= 1


def test_reader_ignores_implausible_length():
    # A stray 0x7e followed by a huge "length" must not stall the reader
    reader = p.FrameReader()
    frames = reader.feed(b"\x7e\xf0" + b(MODULE_IDENT_REQ))
    assert [f.mtype for f in frames] == [0x04]


# --- Status decoding -------------------------------------------------------


def status_frame(**overrides):
    """The real status frame with some bytes changed (CRC not recomputed)."""
    raw = bytearray(b(JACUZZI_STATUS_0x16))
    for index, value in overrides.items():
        raw[int(index.lstrip("b"))] = value
    return bytes(raw)


def test_real_status_frame():
    s = p.parse_status(b(JACUZZI_STATUS_0x16))
    assert (s.hour, s.minute) == (16, 18)
    assert (s.year, s.month, s.day) == (2022, 11, 7)
    assert s.day_of_week == 1  # Monday
    assert s.temp_scale == p.TSCALE_C
    assert s.current_temp == 19.0
    assert s.set_temp == 19.0
    assert s.pump_states == (2, 2, 0, 0)
    assert (s.secondary_on, s.primary_on, s.blower_on, s.uv_on) == (0, 1, 1, 0)
    assert s.flow_switch == 1
    assert s.error_code == 0
    assert s.second_temp_raw == 66
    assert (s.clearray_time, s.water_time) == (9, 32768)
    assert s.outer_filter_time == 10
    assert s.inner_filter_time == 0
    assert s.unknown_tail == (255, 0, 0, 0)
    assert s.twelve_hour is True


def test_status_date_is_a_real_monday():
    # Independent check that the date and day-of-week fields are decoded
    # correctly: the capture's own calendar date falls on its own weekday.
    s = p.parse_status(b(JACUZZI_STATUS_0x16))
    assert datetime.date(s.year, s.month, s.day).isoweekday() == s.day_of_week


def test_fahrenheit_uses_whole_degrees():
    # Bit 0 of byte 18 clear = Fahrenheit: no halving
    s = p.parse_status(status_frame(b18=0x80))
    assert s.temp_scale == p.TSCALE_F
    assert s.current_temp == 38.0
    assert s.set_temp == 38.0


def test_no_temperature_reading():
    s = p.parse_status(status_frame(b12=0xFF))
    assert s.current_temp is None
    assert s.set_temp == 19.0


def test_pump_state_bits():
    s = p.parse_status(status_frame(b15=0b11_10_01_00))
    assert s.pump_states == (0, 1, 2, 3)


def test_short_frames_drop_optional_fields():
    full = b(JACUZZI_STATUS_0x16)
    # Truncate to LEN 30 (outer filter present, nothing after)
    short = bytearray(full[:32])
    short[1] = 30
    s = p.parse_status(bytes(short))
    assert s.outer_filter_time == 10
    assert s.inner_filter_time is None
    assert s.wifi_state is None
    assert s.unknown_tail is None


def test_status_rejects_wrong_type_and_short_frames():
    with pytest.raises(p.ProtocolError):
        p.parse_status(b(MODULE_IDENT_REQ))
    with pytest.raises(p.ProtocolError):
        p.parse_status(b(JACUZZI_STATUS_0x16)[:20])


def test_temperature_encoding():
    assert p.encode_temperature(20.0, p.TSCALE_C) == 40
    assert p.encode_temperature(37.5, p.TSCALE_C) == 75
    assert p.encode_temperature(104, p.TSCALE_F) == 104


# --- Channel negotiation ---------------------------------------------------
#
# These sequences are built from the current implementation's behaviour, not
# from captures of a real handshake (none are available yet). Replace them with
# real captures as they turn up.


def cts(channel):
    return p.parse_frame(p.build_frame(channel, p.PF_ADDRESSED, p.CLEAR_TO_SEND))


def button(channel, code=0x04):
    return p.parse_frame(
        p.build_frame(channel, p.PF_ADDRESSED, p.CC_REQ, bytes([code, 0x00]))
    )


def test_learns_channels_and_picks_lowest_free_one():
    bus = p.BusClient()
    for chan in (0x10, 0x0A, 0x0B):  # channels the spa polls
        bus.handle(cts(chan))
    assert sorted(bus.discovered) == [0x0A, 0x0B, 0x10]

    # 0x0A and 0x10 are in use by real panels. Detection counts later
    # presses from channels already known to be active.
    bus.handle(button(0x0A))
    bus.handle(button(0x10))
    assert bus.channel is None
    for _ in range(p.DETECT_CHANNEL_STATE_CHANNEL_NOT_FOUND):
        bus.handle(button(0x0A))
    assert bus.channel == 0x0B


def test_requests_channel_when_none_is_free():
    bus = p.BusClient()
    bus.handle(button(0x0A))  # first sighting only registers the channel
    for _ in range(p.DETECT_CHANNEL_STATE_CHANNEL_NOT_FOUND):
        bus.handle(button(0x0A))
    assert bus.channel is None  # nothing polled that is free

    offer = p.parse_frame(
        p.build_frame(0xFF, p.PF_ADDRESSED, p.CLIENT_CLEAR_TO_SEND)
    )
    actions = bus.handle(offer)
    assert actions.send == [p.build_frame(0xFE, 0xBF, 0x01, b"\x02\xf1\x73")]


def test_does_not_request_channel_before_detection_finishes():
    bus = p.BusClient()
    offer = p.parse_frame(
        p.build_frame(0xFF, p.PF_ADDRESSED, p.CLIENT_CLEAR_TO_SEND)
    )
    assert bus.handle(offer).send == []


def test_channel_assignment_is_acknowledged():
    bus = p.BusClient()
    resp = p.parse_frame(
        p.build_frame(0xFF, p.PF_ADDRESSED, p.CHANNEL_ASSIGNMENT_RESPONSE, b"\x11")
    )
    actions = bus.handle(resp)
    assert bus.channel == 0x11
    assert actions.send == [p.build_frame(0x11, 0xBF, p.CHANNEL_ASSIGNMENT_ACK)]


def test_answers_existing_client_probe_only_once_it_has_a_channel():
    probe = p.parse_frame(
        p.build_frame(0xFF, p.PF_ADDRESSED, p.EXISTING_CLIENT_REQ)
    )
    assert p.BusClient().handle(probe).send == []
    actions = p.BusClient(channel=0x11).handle(probe)
    assert actions.send == [
        p.build_frame(0x11, 0xBF, p.EXISTING_CLIENT_RESPONSE, b"\x04\x08\x00")
    ]


def test_sends_one_queued_frame_per_clear_to_send_for_our_channel():
    bus = p.BusClient(channel=0x11)
    bus.discovered.append(0x11)  # we have seen our own channel polled before
    bus.queue(b(MODULE_IDENT_REQ))
    bus.queue(b(SET_TEMP_20C))

    assert bus.handle(cts(0x0A)).send == []  # someone else's turn
    assert bus.handle(cts(0x11)).send == [b(MODULE_IDENT_REQ)]
    assert bus.queued == 1
    assert bus.handle(cts(0x11)).send == [b(SET_TEMP_20C)]
    assert bus.handle(cts(0x11)).send == []  # nothing left


def test_clear_queue_discards_pending_commands():
    bus = p.BusClient(channel=0x11)
    bus.discovered.append(0x11)
    bus.queue(b(SET_TEMP_20C))
    bus.clear_queue()
    assert bus.handle(cts(0x11)).send == []


def test_button_presses_are_reported():
    actions = p.BusClient().handle(button(0x0A, code=0x04))
    assert actions.button == (p.CC_REQ, 0x04)
    assert p.BusClient().handle(button(0x0A, code=0x00)).button is None
