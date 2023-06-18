import logging
import os
import asyncio
import paho.mqtt.client as mqtt

import jacuzziRS485

logging.basicConfig(level=logging.INFO, format="%(asctime)s:%(levelname)s:%(message)s")
log = logging.getLogger("__name__")

mqtt_host = os.environ.get("MQTT_HOST")
mqtt_port = int(os.environ.get("MQTT_PORT"))
mqtt_user = os.environ.get("MQTT_USER")
mqtt_password = os.environ.get("MQTT_PASSWORD")

serial_ip = os.environ.get("SERIAL_IP")
serial_port = int(os.environ.get("SERIAL_PORT"))


def on_connect(mqttc, obj, flags, rc):
    """This is triggered whenever we connect to MQTT"""
    log.info("Connected to MQTT.")


def on_message(mqttc, obj, msg):
    """This is triggered whenever we recieve a message on MQTT"""
    global spa
    log.info(
        "MQTT message received on topic: "
        + msg.topic
        + " with value: "
        + msg.payload.decode()
    )
    if msg.topic == "homie/hot_tub/J335/set_temperature/set":
        new_temp = spa.set_temp_value_formatter(msg.payload.decode())
        asyncio.run(spa.send_temp_change(new_temp))
    else:
        log.debug("Unhandled MQTT message on topic {}.".format(msg.topic))


async def read_spa_data(spa, lastupd):
    """This is triggered whenever spa data has changed"""
    await asyncio.sleep(1)
    if spa.lastupd != lastupd:
        lastupd = spa.lastupd
        log.info(
            "Set Temp is {} and Water Temp is {}".format(spa.get_settemp(), spa.curtemp)
        )

        mqtt_client.publish(
            "homie/hot_tub/J335/set_temperature",
            payload=spa.get_settemp(),
            qos=0,
            retain=False,
        )

        mqtt_client.publish(
            "homie/hot_tub/J335/temperature", payload=spa.curtemp, qos=0, retain=False
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
        "homie/hot_tub/$name", payload="Acorns J335", qos=0, retain=False
    )
    mqtt_client.publish("homie/hot_tub/$state", payload="ready", qos=0, retain=False)
    mqtt_client.publish("homie/hot_tub/$nodes", payload="J335", qos=0, retain=False)
    mqtt_client.publish(
        "homie/hot_tub/J335/set_temperature/$name",
        payload="Set Temperature",
        qos=0,
        retain=False,
    )
    mqtt_client.publish(
        "homie/hot_tub/J335/set_temperature/$unit", payload="°C", qos=0, retain=False
    )
    mqtt_client.publish(
        "homie/hot_tub/J335/set_temperature/$datatype",
        payload="integer",
        qos=0,
        retain=False,
    )
    mqtt_client.publish(
        "homie/hot_tub/J335/set_temperature/$settable",
        payload="true",
        qos=0,
        retain=False,
    )

    mqtt_client.publish(
        "homie/hot_tub/J335/temperature/$name",
        payload="Temperature",
        qos=0,
        retain=False,
    )
    mqtt_client.publish(
        "homie/hot_tub/J335/temperature/$unit", payload="°C", qos=0, retain=False
    )
    mqtt_client.publish(
        "homie/hot_tub/J335/temperature/$datatype",
        payload="integer",
        qos=0,
        retain=False,
    )
    mqtt_client.publish(
        "homie/hot_tub/J335/temperature/$settable", payload="false", qos=0, retain=False
    )

    # Subscribe to MQTT
    mqtt_client.subscribe("homie/hot_tub/J335/set_temperature/set")


async def start_app():
    """Test a miniature engine of talking to the spa."""
    global spa
    # Connect to MQTT
    await start_mqtt()

    # Connect to Spa (Serial Device)
    spa = jacuzziRS485.JacuzziRS485(serial_ip, serial_port)

    asyncio.ensure_future(spa.check_connection_status())
    asyncio.ensure_future(spa.listen())

    lastupd = 0

    while True:
        lastupd = await read_spa_data(spa, lastupd)


if __name__ == "__main__":
    asyncio.run(start_app())
