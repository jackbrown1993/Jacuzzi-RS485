import logging
import os
import sys
import asyncio
import paho.mqtt.client as mqtt
import jacuzziRS485

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s:%(levelname)s:%(message)s")
log = logging.getLogger("__name__")

# Environment variable checks
if "MQTT_IP" not in os.environ:
    log.error("MQTT IP not provided. Please provide the MQTT server address.")
    sys.exit(1)
else:
    mqtt_ip = os.environ.get("MQTT_IP")

if "MQTT_USER" not in os.environ:
    log.error("MQTT user not provided. Please provide the username for MQTT server.")
    sys.exit(1)
else:
    mqtt_user = os.environ.get("MQTT_USER")

if "MQTT_PASSWORD" not in os.environ:
    log.error("MQTT password not provided. Please provide the MQTT server password.")
    sys.exit(1)
else:
    mqtt_password = os.environ.get("MQTT_PASSWORD")

if "JACUZZI_IP" not in os.environ:
    log.error("Jacuzzi IP not provided. Please provide the Jacuzzi module address.")
    sys.exit(1)
else:
    jacuzzi_ip = os.environ.get("JACUZZI_IP")

mqtt_port = int(os.environ.get("MQTT_PORT", 1883))
jacuzzi_port = int(os.environ.get("JACUZZI_PORT", 4257))


# MQTT Client setup
def on_connect(mqttc, obj, flags, rc):
    """Triggered when connected to MQTT"""
    log.info("Connected to MQTT broker.")
    mqtt_client.subscribe("homie/hot_tub/jacuzzi/set_temperature/set")


async def on_message(mqttc, obj, msg):
    """Triggered upon receiving an MQTT message"""
    global spa
    log.info(f"Received MQTT message on {msg.topic}: {msg.payload.decode()}")
    if msg.topic == "homie/hot_tub/jacuzzi/set_temperature/set":
        new_temp = float(msg.payload.decode())
        await spa.send_temp_change(new_temp)  # Awaiting the async function directly
    else:
        log.debug(f"Unhandled MQTT topic: {msg.topic}")


async def read_spa_data(spa, lastupd):
    """Reads and publishes spa data changes to MQTT"""
    await asyncio.sleep(3)
    if spa.lastupd != lastupd:
        lastupd = spa.lastupd
        log.info(
            f"Set temperature: {spa.get_settemp()}, current temperature: {spa.curtemp}"
        )

        mqtt_client.publish(
            "homie/hot_tub/jacuzzi/set_temperature",
            payload=spa.get_settemp(),
            qos=0,
            retain=False,
        )

        mqtt_client.publish(
            "homie/hot_tub/jacuzzi/temperature",
            payload=spa.curtemp,
            qos=0,
            retain=False,
        )

    return lastupd


def start_mqtt():
    """Sets up MQTT topics and publishes initial state"""
    mqtt_client.publish("homie/hot_tub/$homie", payload="3.0", qos=0, retain=False)
    mqtt_client.publish("homie/hot_tub/$name", payload="Jacuzzi", qos=0, retain=False)
    mqtt_client.publish("homie/hot_tub/$state", payload="ready", qos=0, retain=False)
    mqtt_client.publish("homie/hot_tub/$nodes", payload="jacuzzi", qos=0, retain=False)

    # Set temperature-related topics
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

    # Current temperature-related topics
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
        "homie/hot_tub/jacuzzi/temperature/$settable",
        payload="false",
        qos=0,
        retain=False,
    )


async def main():
    global spa  # Define spa here or import from jacuzziRS485 if required

    # Initialize MQTT client
    global mqtt_client
    mqtt_client = mqtt.Client("jacuzzi_rs485")
    mqtt_client.username_pw_set(username=mqtt_user, password=mqtt_password)
    mqtt_client.on_connect = on_connect
    mqtt_client.on_message = on_message
    mqtt_client.connect(mqtt_ip, mqtt_port)

    # Start MQTT in a separate thread and set up initial topics
    mqtt_client.loop_start()
    start_mqtt()

    # Initialize spa and last update
    spa = jacuzziRS485.Spa(jacuzzi_ip, jacuzzi_port)  # Adjust as needed
    last_update = None

    try:
        # Main loop to periodically read and publish spa data
        while True:
            last_update = await read_spa_data(spa, last_update)
            await asyncio.sleep(5)  # Throttle loop delay
    finally:
        mqtt_client.loop_stop()  # Stop MQTT loop cleanly on exit


# Run the main async function
asyncio.run(main())
