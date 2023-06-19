<h2 align="center">Jacuzzi Smart Control</h2>

<p align="center">
<a href="https://github.com/psf/black"><img alt="Code style: black" src="https://img.shields.io/badge/code%20style-black-000000.svg"></a>
</p>

## Purpose

To provide an interface for Jacuzzi's without the expensive ProLink module (although if you have it, that is also ok). An RS485 Serial to WiFi adaptor can instead be used, connected to the RS485 port on the main board. The adaptor I used was around £25 on Amazon.co.uk (https://www.amazon.co.uk/gp/product/B097C8PT6F).

Currently the project allows control via MQTT or a terminal interface.

## Running the project

Regardless of you using the Jacuzzi ProLink module or an RS485 to WiFi Adaptor, you will need to know the IP address the module has on your home network, in the below example we have identified the module to have an IP address of 192.168.1.125, by default the ProLink module seems to use port 4257, you can optionally supply a different port using the --port flag.

# Terminal Interface (port flag is optional and defaults to 4257)

python 3 app/ui_app.py --ip 192.168.1.125 --port 9988

# MQTT (Current only supported using a Docker container)

The following environment variables are supported when deploying the MQTT app via Docker.

`MQTT_IP` - IP address of your MQTT server.

`MQTT_PORT` - Port that your MQTT server is listening on. (Optional - Defaults to 1883)

`MQTT_USER` - Username of MQTT server.

`MQTT_PASSWORD` - Password of MQTT server.

`JACUZZI_IP` - IP address of your ProLink or RS485 to WiFi module.

`JACUZZI_PORT` - Port of your ProLink or RS485 to WiFi module. (Optional - Defaults to 4257)

An MQTT Bridge is provided to allow easy integration with other systems. You will need a separate MQTT server running (Mosquitto is a relatively easy and robust one). The MQTT topics follow the Homie convention, making them self-describing.

Publishing a float value to ```homie/hot_tub/J335/set_temperature/set``` will change the set temp value of Jacuzzi.

## Docker:

Run docker image using ```docker run -d -e MQTT_IP= -e MQTT_PORT= -e MQTT_USER= -e MQTT_PASSWORD= -e JACUZZI_IP= -e JACUZZI_PORT= ghcr.io/jackbrown1993/jacuzzi-rs485:latest```

### docker-compose example:

```
version: '3.8'
services:

  jacuzzi-rs485:
    image: ghcr.io/jackbrown1993/jacuzzi-rs485:latest
    container_name: jacuzzi
    restart: unless-stopped
    environment:
      - MQTT_HOST=
      - MQTT_PORT=
      - MQTT_USER=
      - MQTT_PASSWORD=
      - JACUZZI_IP=
      - JACUZZI_PORT=
```

Inspired from / credit to:
- [https://github.com/ccutrer/balboa_worldwide_app](https://github.com/ccutrer/balboa_worldwide_app) for so much research and documentation on the messages.
- [https://github.com/HyperActiveJ/sundance780-jacuzzi-balboa-rs485-tcp](https://github.com/HyperActiveJ/sundance780-jacuzzi-balboa-rs485-tcp) for getting me started on decoding messages for my specific Jacuzzi model.
- [https://github.com/garbled1/pybalboa](https://github.com/garbled1/pybalboa) for providing the Python module that this code was based on.
- [https://github.com/peterg79/bwalink](https://github.com/jshank/bwalink) for testing and documenting on the RS485 to WiFi process.
- [https://github.com/dhmsjs/pyjacuzzi](https://github.com/dhmsjs/pyjacuzzi) for making lots of progress on getting this to work with Jacuzzi and his effort on code readability and commenting.