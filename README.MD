# Jacuzzi App

This repo is still under development.

Inspired from https://github.com/HyperActiveJ/sundance780-jacuzzi-balboa-rs485-tcp


## Purpose:

To remotely control the Jacuzzi J335 without the expensive celluar module and subscription. An Elfin serial to WiFi adaptor is used instead connected to the RS485 port on the main board.


## Configuration:

### Mandatory ENV variables:

`MQTT_HOST` - DNS or IP of your MQTT server.

`MQTT_PORT` - Port that your MQTT server is listening on.

`MQTT_USER` - Username of MQTT server.

`MQTT_PASSWORD` - Password of MQTT server.


`SERIAL_IP` - IP address of your Elfin serial to WiFi device.

`SERIAL_PORT` - Port that the NETP service of your serial to WiFi device is running on.


### Optional ENV vars:

