<h1 align="center">Jacuzzi Smart Control</h1>

<h2>Project Purpose</h2>

To provide an interface for Jacuzzi's with or without the ProLink module. An RS485 Serial to WiFi adaptor can instead be used, connected to the RS485 port on the main board. The adaptor I used was around £25 on Amazon.co.uk (https://www.amazon.co.uk/gp/product/B097C8PT6F). With settings as 115200,8,1,NONE

Currently the project allows control via MQTT or a terminal interface.

<h2>Project Status</h2>

| Part | Status |
| --- | --- |
| Python app (`app/`): MQTT + Home Assistant discovery via Docker, and a terminal UI | **Maintenance.** Bug fixes only. This is what the published Docker image runs. |
| ESPHome version (`esphome/`) | **In development, not usable yet.** An ESP32 wired straight to the tub's RS485 bus, talking natively to Home Assistant, with no WiFi/TCP bridge, Docker or MQTT broker. See [esphome/README.md](esphome/README.md). |

The Python app will keep working while the ESPHome version is built. When the ESPHome version has been proven on a real tub, the Python app will be deprecated with notice, and its last release kept on a `legacy` branch.

<h2>Getting Started</h2>

Whether you utilize the Jacuzzi ProLink module or opt for an RS485 to WiFi Adaptor, it is essential to determine the IP address assigned to the module on your home network. In the following example, we have identified the module's IP address as 192.168.1.125. By default, the ProLink module tends to employ port 4257, but if desired, you can specify an alternative port using the "--port" flag.

<h3>Terminal Interface (port flag is optional and defaults to 4257)</h3>

python3 app/ui_app.py --ip 192.168.1.125 --port 9988

<h3>MQTT (Current only supported using a Docker container)</h3>

Rename the file example.env to .env and populate the following variables.

`MQTT_IP` - IP address of your MQTT server.

`MQTT_PORT` - Port that your MQTT server is listening on. (Optional - Defaults to 1883)

`MQTT_USER` - Username of MQTT server.

`MQTT_PASSWORD` - Password of MQTT server.

`JACUZZI_IP` - IP address of your ProLink or RS485 to WiFi module.

`JACUZZI_PORT` - Port of your ProLink or RS485 to WiFi module. (Optional - Defaults to 4257)

An MQTT Bridge is provided to allow easy integration with other systems. You will need a separate MQTT server running (Mosquitto is a relatively easy and robust one). The app publishes Home Assistant MQTT discovery messages (retained), so entities appear automatically in Home Assistant when MQTT discovery is enabled.

Topics (state topics are `jacuzzi/<name>/state`, commands are `jacuzzi/<name>/set`):

* `jacuzzi/target_temperature/set` - publish a float (e.g. `37.5`) to change the set temperature.
* `jacuzzi/pump_1/set` and `jacuzzi/pump_2/set` - publish `0` (off) or `1` (on; pump 1 also accepts `2` for high speed).
* `jacuzzi/connection/availability` - `online`/`offline` (last will), `jacuzzi/connection/status` - `1` when the spa is sending data.

<h4>Docker</h4>

There is a published multi-arch (amd64 and arm64) docker image at ghcr.io/jackbrown1993/jacuzzi-rs485. `:latest` is the newest tagged release; you can also pin a version such as `:1.1.0`, `:1.1` or `:1`.

Run docker image using published image ```docker run -d -e MQTT_IP= -e MQTT_PORT= -e MQTT_USER= -e MQTT_PASSWORD= -e JACUZZI_IP= -e JACUZZI_PORT= ghcr.io/jackbrown1993/jacuzzi-rs485:latest```

Run docker image built locally:

First build the image: ```docker build -t jacuzzi-rs485 .```

Then run the image: ```docker run -e MQTT_IP= -e MQTT_PORT= -e MQTT_USER= -e MQTT_PASSWORD= -e JACUZZI_IP= -e JACUZZI_PORT= jacuzzi-rs485```

docker-compose example using published image: docker-compose.yml

docker-compose example with image built locally: docker-compose.dev.yml

<h3>Inspirations and Credits</h3>

* https://github.com/ccutrer/balboa_worldwide_app for so much research and documentation on the messages.

* https://github.com/HyperActiveJ/sundance780-jacuzzi-balboa-rs485-tcp for getting me started on decoding messages for my specific Jacuzzi model.

* https://github.com/garbled1/pybalboa for providing the Python module that this code was based on.

* https://github.com/peterg79/bwalink for testing and documenting on the RS485 to WiFi process.

* https://github.com/dhmsjs/pyjacuzzi for making lots of progress on getting this to work with Jacuzzi and his effort on code readability and commenting.

<h3>Development</h3>

The wire protocol (framing, checksum, status decoding, channel negotiation) lives in `app/protocol.py` and has no I/O, so it can be tested without a spa. The tests in `tests/` replay frames captured from real spas (see `tests/frames.py` for where each came from) and double as the specification for the protocol. Run them with:

```
pip install pytest
python -m pytest tests
```

If you capture frames from your own spa, adding them to `tests/frames.py` (with a note of the model) is the most useful contribution.
