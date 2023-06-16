# Jacuzzi App

This repo is still under development.

Inspired from / credit to:
- [https://github.com/ccutrer/balboa_worldwide_app](https://github.com/ccutrer/balboa_worldwide_app)
- [https://github.com/HyperActiveJ/sundance780-jacuzzi-balboa-rs485-tcp](https://github.com/garbled1/pybalboa)
- [https://github.com/garbled1/pybalboa](https://github.com/garbled1/pybalboa)
- [https://github.com/peterg79/bwalink](https://github.com/jshank/bwalink)
- [https://github.com/dhmsjs/pyjacuzzi](https://github.com/dhmsjs/pyjacuzzi) for making lots of progress on getting this to work with Jacuzzi and especially for code commenting.


## Purpose:

To remotely control the Jacuzzi J335 without the expensive SmartTub / ProLink module and celluar subscription (although if you have it, that is also ok). An RS485 Serial to WiFi adaptor is used instead connected to the RS485 port on the main board. The adaptor I used was around £25 on Amazon.co.uk (https://www.amazon.co.uk/gp/product/B097C8PT6F).

The aim is to allow control from either MQTT or from Home Assistant.


## Configuration:

### If using a Jacuzzi ProLink (not yet supported)

`MQTT_HOST` - DNS or IP of your MQTT server.

`MQTT_PORT` - Port that your MQTT server is listening on.

`MQTT_USER` - Username of MQTT server.

`MQTT_PASSWORD` - Password of MQTT server.

### If using a RS485 Serial to WiFi Adaptor

`MQTT_HOST` - DNS or IP of your MQTT server.

`MQTT_PORT` - Port that your MQTT server is listening on.

`MQTT_USER` - Username of MQTT server.

`MQTT_PASSWORD` - Password of MQTT server.

`SERIAL_IP` - IP address of your Elfin serial to WiFi device (only required if pro_link = false).

`SERIAL_PORT` - Port that the NETP service of your serial to WiFi device is running on (only required if pro_link = false).

## MQTT

An MQTT Bridge is provided to allow easy integration with other systems. You will need a separate MQTT server running (Mosquitto is a relatively easy and robust one). The MQTT topics follow the Homie convention, making them self-describing.

Publishing a float value to ```homie/hot_tub/J335/set_temperature/set``` will change the set temp value of Jacuzzi.

## Docker:

Run docker image using ```docker run -d -e MQTT_HOST= -e MQTT_PORT=1883 -e MQTT_USER= -e MQTT_PASSWORD= -e SERIAL_IP= -e SERIAL_PORT=8899 ghcr.io/jackbrown1993/jacuzzi-rs485:latest```

### docker-compose Example (if using a Jacuzzi ProLink):

```
version: '3.8'
services:

  jacuzzi-rs485:
    image: ghcr.io/jackbrown1993/jacuzzi-rs485:latest
    container_name: jacuzzi
    restart: unless-stopped
    environment:
      - MQTT_HOST=
      - MQTT_PORT=1883
      - MQTT_USER=
      - MQTT_PASSWORD=
```
### docker-compose Example (if using a RS485 Serial to WiFi Adaptor):

```
version: '3.8'
services:

  jacuzzi-rs485:
    image: ghcr.io/jackbrown1993/jacuzzi-rs485:latest
    container_name: jacuzzi
    restart: unless-stopped
    environment:
      - MQTT_HOST=
      - MQTT_PORT=1883
      - MQTT_USER=
      - MQTT_PASSWORD=
      - SERIAL_IP=
      - SERIAL_PORT=8899
```
## Code Quality Checks

When pull requests are opened a Github action is used to ensure code quality:
- Black to ensure code is formatted
