import jacuzziRS485
import asyncio
import paho.mqtt.client as mqtt
import os
from datetime import datetime
from threading import Thread

mqtt_host = os.environ.get("MQTT_HOST")
mqtt_port = int(os.environ.get("MQTT_PORT"))
mqtt_user = os.environ.get("MQTT_USER")
mqtt_password = os.environ.get("MQTT_PASSWORD")

serial_ip = os.environ.get("SERIAL_IP")
serial_port = int(os.environ.get("SERIAL_PORT"))

mqtt_connected = False

async def on_message(mqttc, obj, msg):
    print(
        "MQTT message received on topic: "
        + msg.topic
        + " with value: "
        + msg.payload.decode()
    )
    if msg.topic == "homie/hot_tub/J335/set_temperature/set":
        new_temp = float(msg.payload.decode())
        await spa.send_temp_change(new_temp)
    else:
        print("No logic for this topic, discarding.")

async def read_spa_data(spa, lastupd):
    await asyncio.sleep(1)
    if spa.lastupd != lastupd:
        lastupd = spa.lastupd
        print(
            "New data as of "
            + datetime.utcfromtimestamp(spa.lastupd).strftime("%d-%m-%Y %H:%M:%S")
        )

        print("Set Temp: {0}".format(spa.get_settemp()))
        print("Current Temp: {0}".format(spa.curtemp))

        print()
    return lastupd

def mqtt_on_connect(client, userdata, flags, rc):
    global mqtt_connected
    print("Connected to MQTT.")
    mqtt_connected = True

def mqtt_on_disconnect(client, userdata, rc):
    global mqtt_connected
    print("Disconnected from MQTT.")
    mqtt_connected = False

def start_mqtt():
    mqtt_client = mqtt.Client("jacuzzi_rs485")
    mqtt_client.username_pw_set(username=mqtt_user, password=mqtt_password)
    mqtt_client.on_connect = mqtt_on_connect
    mqtt_client.on_disconnect = mqtt_on_disconnect
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
    global spa
    spa = jacuzziRS485.JacuzziRS485(serial_ip)

    await asyncio.sleep(1)  # Allow time for MQTT connection
    while not mqtt_connected:
        await asyncio.sleep(1)

    asyncio.create_task(spa.check_connection_status())
    asyncio.create_task(spa.listen())

    lastupd = 0
    while True:
        lastupd = await read_spa_data(spa, lastupd)
        await asyncio.sleep(1)

def run_app():
    loop = asyncio.get_event_loop()
    loop.create_task(start_app())
    loop.run_forever()

if __name__ == "__main__":
    start_mqtt()
    run_app()
