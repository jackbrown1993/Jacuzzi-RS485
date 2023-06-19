import jacuzziRS485

import asyncio
import paho.mqtt.client as mqtt
import os
import sys
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s:%(levelname)s:%(message)s")
log = logging.getLogger("__name__")

if 'MQTT_IP' not in os.environ:
    log.error("MQTT IP not provided, please provide IP address or hostname of your MQTT server.")
    sys.exit(1)
else:
    mqtt_ip = os.environ.get("MQTT_IP")

if 'MQTT_USER' not in os.environ:
    log.error("MQTT user not provided, please provide username of your MQTT server.")
    sys.exit(1)
else:
    mqtt_user = os.environ.get("MQTT_USER")

if 'MQTT_PASSWORD' not in os.environ:
    log.error("MQTT password not provided, please provide password of your MQTT server.")
    sys.exit(1)
else:
    mqtt_password = os.environ.get("MQTT_PASSWORD")

if 'JACUZZI_IP' not in os.environ:
    log.error("Jacuzzi IP not provided, please provide IP address or hostname of your Prolink or RS485 Module.")
    sys.exit(1)
else:
    jacuzzi_ip = os.environ.get("JACUZZI_IP")

if 'MQTT_PORT' not in os.environ:
    mqtt_port = 1883
else:
    mqtt_port = os.environ.get("MQTT_PORT")

if 'JACUZZI_PORT' not in os.environ:
    jacuzzi_port = 4257
else:
    jacuzzi_port = os.environ.get("JACUZZI_PORT")

def on_connect(mqttc, obj, flags, rc):
    log.info("Connected to MQTT.")


def on_message(mqttc, obj, msg):
    log.info(
        "MQTT message received on topic: "
        + msg.topic
        + " with value: "
        + msg.payload.decode()
    )
    if msg.topic == "homie/hot_tub/jacuzzi/set_temperature/set":
        # Figure this out
        new_temp = int(msg.payload.decode())
        asyncio.run(spa.send_temp_change(new_temp))
        log.info("as")
    else:
        log.debug("Unhandled MQTT message on topic {}.".format(msg.topic))


async def read_spa_data(spa, lastupd):
    await asyncio.sleep(1)
    if spa.lastupd != lastupd:
        lastupd = spa.lastupd
        log.info(
            "Set Temp is {} and Water Temp is {}".format(spa.get_settemp(), spa.curtemp)
        )

        mqtt_client.publish(
            "homie/hot_tub/jacuzzi/set_temperature",
            payload=spa.get_settemp(),
            qos=0,
            retain=False,
        )

        mqtt_client.publish(
            "homie/hot_tub/jacuzzi/temperature", payload=spa.curtemp, qos=0, retain=False
        )

    return lastupd


async def start_mqtt():
    global mqtt_client
    mqtt_client = mqtt.Client("jacuzzi_rs485")
    mqtt_client.username_pw_set(username=mqtt_user, password=mqtt_password)
    mqtt_client.on_connect = on_connect
    mqtt_client.on_message = on_message
    mqtt_client.connect(mqtt_host, mqtt_port)
    mqtt_client.loop_start()

    mqtt_client.publish("homie/hot_tub/$homie", payload="3.0", qos=0, retain=False)
    mqtt_client.publish(
        "homie/hot_tub/$name", payload="Jaccuzi", qos=0, retain=False
    )
    mqtt_client.publish("homie/hot_tub/$state", payload="ready", qos=0, retain=False)
    mqtt_client.publish("homie/hot_tub/$nodes", payload="jacuzzi", qos=0, retain=False)
    mqtt_client.publish(
        "homie/hot_tub/jacuzzi/set_temperature/$name",
        payload="Set Temperature",
        qos=0,
        retain=False,
    )
    mqtt_client.publish(
        "homie/hot_tub/jacuzzi/set_temperature/$unit", payload="°C", qos=0, retain=False
    )
    mqtt_client.publish(
        "homie/hot_tub/jacuzzi/set_temperature/$datatype",
        payload="integer",
        qos=0,
        retain=False,
    )
    mqtt_client.publish(
        "homie/hot_tub/jacuzzi/set_temperature/$settable",
        payload="true",
        qos=0,
        retain=False,
    )

    mqtt_client.publish(
        "homie/hot_tub/jacuzzi/temperature/$name",
        payload="Temperature",
        qos=0,
        retain=False,
    )
    mqtt_client.publish(
        "homie/hot_tub/jacuzzi/temperature/$unit", payload="°C", qos=0, retain=False
    )
    mqtt_client.publish(
        "homie/hot_tub/jacuzzi/temperature/$datatype",
        payload="integer",
        qos=0,
        retain=False,
    )
    mqtt_client.publish(
        "homie/hot_tub/jacuzzi/temperature/$settable", payload="false", qos=0, retain=False
    )

    # Subscribe to MQTT
    mqtt_client.subscribe("homie/hot_tub/jacuzzi/set_temperature/set")


async def start_app():
    """Test a miniature engine of talking to the spa."""
    global spa
    # Connect to MQTT
    await start_mqtt()

    # Connect to Jacuzzi
    spa = jacuzziRS485.JacuzziRS485(jacuzzi_ip, jacuzzi_port)

    asyncio.ensure_future(spa.check_connection_status())
    asyncio.ensure_future(spa.listen())

    lastupd = 0

    while True:
        lastupd = await read_spa_data(spa, lastupd)


if __name__ == "__main__":
    asyncio.run(start_app())
