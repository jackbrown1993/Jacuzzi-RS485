"""Frames captured from real spas, with where each came from.

Add new captures here (with provenance) rather than inline in tests. Every
frame in REAL_FRAMES must have a valid CRC; test_protocol.py checks that.
"""

# Request for the module identification, sent by this project. Logged in
# https://github.com/jackbrown1993/Jacuzzi-RS485/issues/54 and /62.
MODULE_IDENT_REQ = "7e050abf04777e"

# Set temperature to 20.0 C (0x28 = 40 half-degrees). Same issues.
SET_TEMP_20C = "7e060abf2028ca7e"

# A complete Jacuzzi 0x16 status frame, from a J-series spa. Source:
# DECODING.md section 3.9 of
# https://github.com/HyperActiveJ/sundance780-jacuzzi-balboa-rs485-tcp
# Decodes to Monday 7 Nov 2022 16:18, 19.0 C current and set, pump 1 high.
# (7 Nov 2022 really was a Monday, an independent check of the date fields.)
JACUZZI_STATUS_0x16 = (
    "7e25ffaf16"
    "10122 70b16420026fa260a14018100004201"
    "1c0009800000 0a000000ff000000"
    "2f7e"
).replace(" ", "")

# Button-press frames (message type 0xCC) from a Sundance 780, same source,
# section 5b. Different message type from Jacuzzi's 0x17, but the framing and
# CRC are identical, which makes them a useful independent check of the CRC.
SUNDANCE_BUTTON_FRAMES = [
    "7e0710bfcc50b58e7e",
    "7e0710bfcc6d882d7e",
    "7e0710bfcc6387d67e",
    "7e0710bfccc226b57e",
]

REAL_FRAMES = {
    "module_ident_req": MODULE_IDENT_REQ,
    "set_temp_20c": SET_TEMP_20C,
    "jacuzzi_status_0x16": JACUZZI_STATUS_0x16,
    **{"sundance_button_%d" % i: f for i, f in enumerate(SUNDANCE_BUTTON_FRAMES)},
}
