# ESPHome version (in development)

**Status: not usable yet.** Nothing in this directory runs on a tub. The Python app in
[`app/`](../app) is the working implementation.

## Goal

Replace the chain *tub → RS485-to-WiFi adapter → TCP → Python/Docker → MQTT broker → Home
Assistant* with *tub → ESP32 + RS485 transceiver → Home Assistant (native API)*.

That removes the TCP link (and with it the half-open-connection stalls behind issues #54 and
#62), Docker, and the MQTT broker, and lets the protocol run next to the bus instead of across
a network.

## Plan

The protocol is specified by the code in [`app/protocol.py`](../app/protocol.py) and the tests in
[`tests/`](../tests), which replay frames captured from real spas. The C++ port is held to the
same test vectors.

| Phase | What | Needs a tub? |
| --- | --- | --- |
| 0 | Listen-only firmware: decode frames, log raw hex, transmit nothing. Also produces new captures for the tests. | Yes (read-only) |
| 1 | Read-only entities in Home Assistant (temperatures, pumps, UV, error, clock) | Yes (read-only) |
| 2 | Join the bus and send commands (set point, then pumps with confirmation and retry) | Yes |
| 3 | Extras: lights, locks, filter cycles, clock sync | Yes |
| 4 | Encrypted boards (J-235/J-355 "encrypted" variants), once the decoders are reconciled | Yes |

Before phase 0 there is work that needs no hardware: move the test vectors to a shared JSON file,
and write the C++ protocol core (CRC, frame reader, status decoder, bus state machine) with
desktop unit tests.

## Layout

ESPHome finds external components in `esphome/components/` of a git repository without any extra
`path:` setting, so the component will live at `esphome/components/jacuzzi_rs485/`. Users will
eventually reference it with:

```yaml
external_components:
  - source: github://jackbrown1993/Jacuzzi-RS485@main
    components: [ jacuzzi_rs485 ]
```

That component does not exist yet; do not use this snippet.

## Hardware (to be confirmed on a real tub)

- Any ESP32 board (a C3 or S3 mini is plenty).
- A TTL-to-RS485 transceiver module, ideally with automatic direction control; otherwise a
  MAX485 with DE and RE tied together and driven from a GPIO.
- A 4-pin ATX Micro-Fit connector to the tub's communications port (+V, GND, RS485 A and B), and a
  buck converter to run the ESP from the tub's supply.
- Wiring and pin identification guides: [bwalink](https://github.com/peterg79/bwalink) and
  [ccutrer/balboa_worldwide_app](https://github.com/ccutrer/balboa_worldwide_app) (which also has
  an ESP32 + MAX485 ESPHome serial-proxy example). **Disconnect the tub's power before working on it.**
- Baud rate is 115200 8N1 per the main README; confirm during phase 0.

## Help wanted

Raw frames from other Jacuzzi models (including Fahrenheit tubs and encrypted boards) are the most
useful contribution. Add them, with the model, to [`tests/frames.py`](../tests/frames.py) once
that file is merged.
