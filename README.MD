<h1 align="center">Jacuzzi Smart Control</h1>

<p align="center">
<a href="https://github.com/psf/black"><img alt="Code style: black" src="https://img.shields.io/badge/code%20style-black-000000.svg"></a>
</p>

<h2>Project Purpose</h2>

To provide an interface for Jacuzzi's with or without the ProLink module. An RS485 Serial to WiFi adaptor can instead be used, connected to the RS485 port on the main board. The adaptor I used was around £25 on Amazon.co.uk (https://www.amazon.co.uk/gp/product/B097C8PT6F).

Currently the project allows control via MQTT or a terminal interface.

<h2>Getting Started</h2>

Whether you utilize the Jacuzzi ProLink module or opt for an RS485 to WiFi Adaptor, it is essential to determine the IP address assigned to the module on your home network. In the following example, we have identified the module's IP address as 192.168.1.125. By default, the ProLink module tends to employ port 4257, but if desired, you can specify an alternative port using the "--port" flag.

<h3>Terminal Interface (port flag is optional and defaults to 4257)</h3>

python3 app/ui_app.py --ip 192.168.1.125 --port 9988

<h3>MQTT (Current only supported using a Docker container)</h3>

The following environment variables are supported when deploying the MQTT app via Docker.

`MQTT_IP` - IP address of your MQTT server.

`MQTT_PORT` - Port that your MQTT server is listening on. (Optional - Defaults to 1883)

`MQTT_USER` - Username of MQTT server.

`MQTT_PASSWORD` - Password of MQTT server.

`JACUZZI_IP` - IP address of your ProLink or RS485 to WiFi module.

`JACUZZI_PORT` - Port of your ProLink or RS485 to WiFi module. (Optional - Defaults to 4257)

An MQTT Bridge is provided to allow easy integration with other systems. You will need a separate MQTT server running (Mosquitto is a relatively easy and robust one). The MQTT topics follow the Homie convention, making them self-describing.

Publishing a float value to ```homie/hot_tub/J335/set_temperature/set``` will change the set temp value of Jacuzzi.

<h4>Docker</h4>

There is published docker image at ghcr.io/jackbrown1993/jacuzzi-rs485:latest which is based on the master branch.

Run docker image using published image ```docker run -d -e MQTT_IP= -e MQTT_PORT= -e MQTT_USER= -e MQTT_PASSWORD= -e JACUZZI_IP= -e JACUZZI_PORT= ghcr.io/jackbrown1993/jacuzzi-rs485:latest```

Run docker image using local code:

Fist build the image: ```docker build -t jacuzzi-rs485 .```
Then run the image: ```docker run -e MQTT_IP= -e MQTT_PORT= -e MQTT_USER= -e MQTT_PASSWORD= -e JACUZZI_IP= -e JACUZZI_PORT= jacuzzi-rs485```

docker-compose example using published image:

```
version: '3.8'
services:

  jacuzzi-rs485:
    image: ghcr.io/jackbrown1993/jacuzzi-rs485:latest
    container_name: jacuzzi
    restart: unless-stopped
    environment:
      - MQTT_IP=
      - MQTT_PORT=
      - MQTT_USER=
      - MQTT_PASSWORD=
      - JACUZZI_IP=
      - JACUZZI_PORT=
```

<h3>Inspirations and Credits</h3>

* https://github.com/ccutrer/balboa_worldwide_app for so much research and documentation on the messages.

* https://github.com/HyperActiveJ/sundance780-jacuzzi-balboa-rs485-tcp for getting me started on decoding messages for my specific Jacuzzi model.

* https://github.com/garbled1/pybalboa for providing the Python module that this code was based on.

* https://github.com/peterg79/bwalink for testing and documenting on the RS485 to WiFi process.

* https://github.com/dhmsjs/pyjacuzzi for making lots of progress on getting this to work with Jacuzzi and his effort on code readability and commenting.