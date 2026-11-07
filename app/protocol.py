"""Jacuzzi / Balboa-style RS485 panel protocol, with no I/O.

Everything in here is a pure function or a plain data structure: no sockets,
no asyncio, no logging, no MQTT. That keeps it testable with captured frames
and easy to port to another language (e.g. an ESPHome C++ component). The
tests in ``tests/`` are the executable specification.

Frame layout (all values are bytes)::

    7E | LEN | DST | PF | TYPE | PAYLOAD ... | CRC | 7E
         ^-------------------------------------^
         LEN counts itself, DST, PF, TYPE, PAYLOAD and CRC (so the whole frame
         is LEN + 2 bytes). The CRC covers LEN through PAYLOAD.

    DST      channel the frame is addressed to (0xFF = broadcast)
    PF       0xAF for broadcasts from the spa, 0xBF for addressed frames
    TYPE     message type, see the constants below

Offsets used by ``parse_status`` are into the *whole* frame including the
leading 0x7E, so ``frame[4]`` is the message type and ``frame[5]`` is the
first payload byte. This matches the offsets quoted throughout the existing
reverse-engineering notes.
"""

from dataclasses import dataclass
from typing import List, NamedTuple, Optional, Tuple

FLAG = 0x7E

# Preamble bytes
PF_BROADCAST = 0xAF
PF_ADDRESSED = 0xBF
DST_BROADCAST = 0xFF

# Message types sent or received by Jacuzzi (ProLink-style, unencrypted) spas
JACUZZI_STATUS_UPDATE = 0x16
CC_REQ = 0x17  # a button press seen on the bus
JACUZZI_LIGHTS_UPDATE = 0x23

# Channel negotiation
CLIENT_CLEAR_TO_SEND = 0x00
CHANNEL_ASSIGNMENT_REQ = 0x01
CHANNEL_ASSIGNMENT_RESPONSE = 0x02
CHANNEL_ASSIGNMENT_ACK = 0x03
EXISTING_CLIENT_REQ = 0x04
EXISTING_CLIENT_RESPONSE = 0x05
CLEAR_TO_SEND = 0x06
NOTHING_TO_SEND = 0x07

# Commands we send
MSG_MODULE_IDENT_REQ = 0x04
MSG_SET_TEMP = 0x20

# Largest frame LEN we accept; real traffic is well under this.
MAX_LEN = 128
# Shortest frame we will treat as a frame at all: 7E LEN DST PF TYPE CRC 7E.
MIN_FRAME_LEN = 7

# Last status payload byte parse_status reads is frame[27], so the frame must
# be at least 28 bytes long.
MIN_STATUS_LEN = 28

TSCALE_F = 0
TSCALE_C = 1


class ProtocolError(ValueError):
    """Raised when bytes do not form a valid frame."""


def crc(data: bytes) -> int:
    """Checksum over LEN..PAYLOAD (CRC-8, poly 0x07, init 0xB5, final xor 0x02)."""
    value = 0xB5
    for byte in data:
        for i in range(8):
            carry = value & 0x80
            value = ((value << 1) & 0xFF) | ((byte >> (7 - i)) & 0x01)
            if carry:
                value ^= 0x07
    for _ in range(8):
        carry = value & 0x80
        value = (value << 1) & 0xFF
        if carry:
            value ^= 0x07
    return value ^ 0x02


class Frame(NamedTuple):
    """A validated frame."""

    dst: int
    pf: int
    mtype: int
    payload: bytes
    raw: bytes  # the complete frame, including both 0x7E flags


def build_frame(dst: int, pf: int, mtype: int, payload: bytes = b"") -> bytes:
    """Build a complete frame, adding flags, length and CRC."""
    payload = bytes(payload)
    # LEN counts itself, DST, PF, TYPE, the payload and the CRC byte
    length = len(payload) + 5
    if length > MAX_LEN:
        raise ProtocolError("payload too long")
    body = bytes([length, dst, pf, mtype]) + payload
    return bytes([FLAG]) + body + bytes([crc(body), FLAG])


def parse_frame(raw: bytes) -> Frame:
    """Validate and split a complete frame. Raises ProtocolError if invalid."""
    raw = bytes(raw)
    if len(raw) < MIN_FRAME_LEN:
        raise ProtocolError("frame too short")
    if raw[0] != FLAG or raw[-1] != FLAG:
        raise ProtocolError("missing frame flag")
    if raw[1] + 2 != len(raw):
        raise ProtocolError("length byte does not match frame size")
    if crc(raw[1:-2]) != raw[-2]:
        raise ProtocolError("bad CRC")
    return Frame(
        dst=raw[2], pf=raw[3], mtype=raw[4], payload=raw[5:-2], raw=raw
    )


class FrameReader:
    """Splits a byte stream into valid frames, resynchronising after garbage.

    Feed it whatever the transport gives you (any chunking); it returns the
    frames completed by that chunk. Corrupt frames are dropped and counted in
    ``bad_frames`` instead of raising, since a noisy bus is normal.
    """

    def __init__(self) -> None:
        self._buf = bytearray()
        self.bad_frames = 0

    def feed(self, data: bytes) -> List[Frame]:
        self._buf.extend(data)
        frames: List[Frame] = []
        while True:
            # Drop anything before the next start flag
            start = self._buf.find(bytes([FLAG]))
            if start < 0:
                self._buf.clear()
                break
            if start > 0:
                del self._buf[:start]
            if len(self._buf) < 2:
                break
            length = self._buf[1]
            if length == FLAG:
                # Two flags in a row: the first closed a frame we dropped, the
                # second opens the next one.
                del self._buf[0]
                continue
            if length < MIN_FRAME_LEN - 2 or length > MAX_LEN:
                # Not a plausible length: this 0x7E was inside other data
                self.bad_frames += 1
                del self._buf[0]
                continue
            total = length + 2
            if len(self._buf) < total:
                break  # wait for the rest
            candidate = bytes(self._buf[:total])
            try:
                frames.append(parse_frame(candidate))
                del self._buf[:total]
            except ProtocolError:
                self.bad_frames += 1
                del self._buf[0]  # resync on the next 0x7E
        return frames


@dataclass
class SpaStatus:
    """Decoded Jacuzzi status update (message type 0x16)."""

    hour: int
    minute: int
    day_of_week: int  # 1 = Monday
    day: int
    month: int
    year: int
    filter2_mode: int
    heat_mode_state: int
    spa_state: int
    error_code: int
    temp_scale: int  # TSCALE_F or TSCALE_C
    current_temp: Optional[float]  # None when the sensor reports 0xFF
    set_temp: float
    pump_states: Tuple[int, int, int, int]  # index 0..3, each 0..3
    secondary_on: int
    primary_on: int
    blower_on: int
    uv_on: int
    flow_switch: int  # byte 17, believed to be the flow switch signal
    twelve_hour: bool
    light_bits: int  # byte 19, not believed to hold light state
    setting_lock: int
    access_lock: int
    service_lock: int
    second_temp_raw: int  # byte 21, water temperature in the plumbing
    clearray_time: int
    water_time: int
    outer_filter_time: Optional[int]
    inner_filter_time: Optional[int]
    wifi_state: Optional[int]
    unknown_tail: Optional[Tuple[int, int, int, int]]  # frame[33:37] when present
    # Bytes the existing code keeps but does not interpret: frame[13], [22], [23]
    raw_bytes: Tuple[int, int, int]


def parse_status(frame: bytes) -> SpaStatus:
    """Decode a complete 0x16 status frame (flags included).

    Does not verify the CRC; use ``parse_frame`` first if you need that.

    Field notes (offsets into the whole frame; reverse-engineered, see the
    credits in the README). Where the notes say "believed", it is a guess.

    =====  ==============================================================
    5, 6   hour, minute
    7      bits 7-5 day of week (1 = Monday), bits 4-0 day of month
    8, 9   month, year since 2000
    10     bits 7-6 secondary filter mode, 5-4 heat mode state,
           3-0 spa state
    11     error code (0 = none)
    12     current water temperature; 0xFF = no reading
    13     unknown (usually 0xFA)
    14     set temperature
    15     pump states, two bits each: bits 1-0 pump 0 (circulation, not
           present on J-235), 3-2 pump 1, 5-4 pump 2, 7-6 pump 3
           (0 = off, 1 = low, 2 = high)
    16     two bits each: 7-6 secondary on, 5-4 primary on, 3-2 blower,
           1-0 UV. The bit positions are uncertain; all but secondary
           come on during a filter cycle and when pump 1 is on. No
           Jacuzzi spa is known to have a blower.
    17     believed to be the flow switch (1 whenever pump 1 runs, about
           a second late; blips at the end of a filter cycle)
    18     bit 0 temperature scale (1 = Celsius), bits 2-1 clear means
           12 hour clock
    19     unknown; NOT the light state (lights come in message 0x23)
    20     bits 5-4 setting lock, 3-2 access lock, 1-0 service lock
    21     second water temperature (sensor in the plumbing, not the tub)
    22, 23 unknown
    24, 25 ClearRay time (big-endian, despite the original LSB/MSB naming)
    26, 27 water time
    28-31  outer and inner filter times (only when LEN allows)
    32     bits 7-4 wifi state (0 unknown ... 5 infrastructure + cloud,
           14 linking, 15 not communicating to spa)
    33-36  unknown
    =====  ==============================================================

    Celsius temperatures are sent in half-degrees; Fahrenheit in whole
    degrees. The temperature scale (byte 18) must be read before converting
    bytes 12 and 14, which this function does.
    """
    d = bytes(frame)
    if len(d) < MIN_STATUS_LEN:
        raise ProtocolError("status frame too short")
    if d[4] != JACUZZI_STATUS_UPDATE:
        raise ProtocolError("not a status update")

    temp_scale = TSCALE_C if d[18] & 0x01 else TSCALE_F
    divisor = 2 if temp_scale == TSCALE_C else 1
    current_raw = d[12]

    length = d[1]
    return SpaStatus(
        hour=d[5],
        minute=d[6],
        day_of_week=(d[7] & 0xE0) >> 5,
        day=d[7] & 0x1F,
        month=d[8],
        year=d[9] + 2000,
        filter2_mode=(d[10] & 0xC0) >> 6,
        heat_mode_state=(d[10] & 0x30) >> 4,
        spa_state=d[10] & 0x0F,
        error_code=d[11],
        temp_scale=temp_scale,
        current_temp=None if current_raw == 255 else current_raw / divisor,
        set_temp=d[14] / divisor,
        pump_states=(
            d[15] & 0x03,
            (d[15] & 0x0C) >> 2,
            (d[15] & 0x30) >> 4,
            (d[15] & 0xC0) >> 6,
        ),
        secondary_on=(d[16] & 0xC0) >> 6,
        primary_on=(d[16] & 0x30) >> 4,
        blower_on=(d[16] & 0x0C) >> 2,
        uv_on=d[16] & 0x03,
        flow_switch=d[17],
        twelve_hour=(d[18] & 0x06) == 0,
        light_bits=d[19],
        setting_lock=(d[20] & 0x30) >> 4,
        access_lock=(d[20] & 0x0C) >> 2,
        service_lock=d[20] & 0x03,
        second_temp_raw=d[21],
        clearray_time=d[24] * 256 + d[25],
        water_time=d[26] * 256 + d[27],
        outer_filter_time=d[28] * 256 + d[29] if length >= 30 else None,
        inner_filter_time=d[30] * 256 + d[31] if length >= 32 else None,
        wifi_state=(d[32] & 0xF0) >> 4 if length >= 33 else None,
        unknown_tail=(d[33], d[34], d[35], d[36]) if length >= 37 else None,
        raw_bytes=(d[13], d[22], d[23]),
    )


def encode_temperature(temp: float, temp_scale: int) -> int:
    """Convert a set point to the single byte the spa expects.

    Celsius is sent in half-degrees (20.0 -> 40). Fahrenheit is whole degrees.
    """
    value = temp * 2.0 if temp_scale == TSCALE_C else temp
    return int(round(value))


def build_set_temp(channel: int, temp: float, temp_scale: int) -> bytes:
    """Frame that sets the target temperature."""
    return build_frame(
        channel,
        PF_ADDRESSED,
        MSG_SET_TEMP,
        bytes([encode_temperature(temp, temp_scale)]),
    )


def build_module_ident_req(channel: int) -> bytes:
    """Frame that asks the spa for its module identification."""
    return build_frame(channel, PF_ADDRESSED, MSG_MODULE_IDENT_REQ)


# ---------------------------------------------------------------------------
# Bus participation: channel negotiation and the outgoing command queue
# ---------------------------------------------------------------------------

# Wait this many button-press frames from known channels before deciding that a
# channel is free for us to use.
DETECT_CHANNEL_STATE_START = 0
DETECT_CHANNEL_STATE_CHANNEL_NOT_FOUND = 5


class BusActions(NamedTuple):
    """What the caller should do after ``BusClient.handle``."""

    send: List[bytes]  # frames to write to the bus, in order
    button: Optional[Tuple[int, int]]  # (type, code) when a panel button was pressed


class BusClient:
    """Sans-IO state machine for joining the panel bus as another panel.

    The spa polls each channel with a clear-to-send. A new client:

    1. watches clear-to-sends to learn which channels the spa polls
       (``discovered``), and button presses to learn which are in use
       (``active``);
    2. after enough button presses from known channels, takes the lowest
       polled channel nobody else is using, or asks the spa to assign one;
    3. may only transmit when it sees a clear-to-send for its own channel, and
       then sends at most one queued frame.

    Feed every received ``Frame`` to ``handle`` and write the returned frames
    to the bus. Frames passed to ``queue`` wait for our clear-to-send.
    """

    def __init__(self, channel: Optional[int] = None) -> None:
        self.channel: Optional[int] = channel
        self.discovered: List[int] = []
        self.active: List[int] = []
        self.detect_state = DETECT_CHANNEL_STATE_START
        self._outbox: List[bytes] = []

    def queue(self, frame: bytes) -> None:
        self._outbox.append(bytes(frame))

    def clear_queue(self) -> None:
        self._outbox.clear()

    @property
    def queued(self) -> int:
        return len(self._outbox)

    def handle(self, frame: Frame) -> BusActions:
        send: List[bytes] = []
        button: Optional[Tuple[int, int]] = None
        mtype = frame.mtype

        if mtype in (JACUZZI_STATUS_UPDATE, JACUZZI_LIGHTS_UPDATE):
            pass  # data frames, nothing to negotiate

        elif mtype == CLIENT_CLEAR_TO_SEND:
            # The spa is offering a free channel. Ask for one if we have
            # watched long enough to know none is free.
            if (
                self.channel is None
                and self.detect_state == DETECT_CHANNEL_STATE_CHANNEL_NOT_FOUND
            ):
                send.append(
                    build_frame(
                        0xFE,
                        PF_ADDRESSED,
                        CHANNEL_ASSIGNMENT_REQ,
                        bytes([0x02, 0xF1, 0x73]),
                    )
                )

        elif mtype == CHANNEL_ASSIGNMENT_RESPONSE and frame.payload:
            self.channel = frame.payload[0]
            send.append(build_frame(self.channel, PF_ADDRESSED, CHANNEL_ASSIGNMENT_ACK))

        elif mtype == EXISTING_CLIENT_REQ and self.channel is not None:
            send.append(
                build_frame(
                    self.channel,
                    PF_ADDRESSED,
                    EXISTING_CLIENT_RESPONSE,
                    bytes([0x04, 0x08, 0x00]),
                )
            )

        elif mtype == CLEAR_TO_SEND:
            if frame.dst not in self.discovered:
                self.discovered.append(frame.dst)
            elif frame.dst == self.channel and self._outbox:
                send.append(self._outbox.pop(0))

        elif mtype == CC_REQ:
            if frame.dst not in self.active:
                self.active.append(frame.dst)
            elif self.detect_state < DETECT_CHANNEL_STATE_CHANNEL_NOT_FOUND:
                self.detect_state += 1
                if self.detect_state == DETECT_CHANNEL_STATE_CHANNEL_NOT_FOUND:
                    for chan in sorted(self.discovered):
                        if chan not in self.active:
                            self.channel = chan
                            break
            if frame.payload and frame.payload[0] != 0:
                button = (mtype, frame.payload[0])

        return BusActions(send, button)
