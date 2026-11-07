from datetime import datetime
import json
import logging
import os
import sys
import asyncio
import paho.mqtt.client as mqtt
import jacuzziRS485

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s:%(levelname)s:%(message)s")
log = logging.getLogger(__name__)

if "MQTT_IP" not in os.environ:
    log.error(
        "MQTT IP not provided, please provide IP address or hostname of your MQTT server."
    )
    sys.exit(1)
else:
    mqtt_ip = os.environ.get("MQTT_IP")

if "MQTT_USER" not in os.environ:
    log.error("MQTT user not provided, please provide username of your MQTT server.")
    sys.exit(1)
else:
    mqtt_user = os.environ.get("MQTT_USER")

if "MQTT_PASSWORD" not in os.environ:
    log.error(
        "MQTT password not provided, please provide password of your MQTT server."
    )
    sys.exit(1)
else:
    mqtt_password = os.environ.get("MQTT_PASSWORD")

if "JACUZZI_IP" not in os.environ:
    log.error(
        "Jacuzzi IP not provided, please provide IP address or hostname of your Prolink or RS485 Module."
    )
    sys.exit(1)
else:
    jacuzzi_ip = os.environ.get("JACUZZI_IP")

if "MQTT_PORT" not in os.environ:
    mqtt_port = 1883
else:
    mqtt_port = int(os.environ.get("MQTT_PORT"))

if "JACUZZI_PORT" not in os.environ:
    jacuzzi_port = 4257
else:
    jacuzzi_port = int(os.environ.get("JACUZZI_PORT"))


AVAILABILITY_TOPIC = "jacuzzi/connection/availability"


def on_connect(mqttc, obj, flags, rc):
    """This is triggered whenever we connect to MQTT"""
    log.info("Connected to MQTT broker.")
    # Subscribe only to command topics
    mqtt_client.subscribe("jacuzzi/+/set")
    # Discovery and availability must be re-sent on every (re)connect
    mqtt_client.publish(AVAILABILITY_TOPIC, payload="online", qos=1, retain=True)
    publish_all_discovery()


def on_disconnect(mqttc, obj, rc):
    """This is triggered whenever we disconnect fromm MQTT"""
    log.info("Disconnected MQTT broker.")


def on_message(mqttc, obj, msg):
    """This is triggered whenever we receive a message on MQTT"""
    payload = msg.payload.decode(errors="replace").strip()
    log.debug(f"MQTT message received on topic: {msg.topic} with value: {payload}")
    try:
        if msg.topic == "jacuzzi/target_temperature/set":
            new_temp = float(payload)
            run_on_main_loop(spa.send_temp_change(new_temp))
        elif msg.topic in ("jacuzzi/pump_1/set", "jacuzzi/pump_2/set"):
            pump = 1 if msg.topic == "jacuzzi/pump_1/set" else 2
            state = int(payload)
            if state < 0 or state > spa.pump_array[pump]:
                log.error(f"Invalid state {state} for pump {pump}, ignoring.")
                return
            run_on_main_loop(spa.change_pump(pump, state))
        else:
            log.debug(f"Unhandled MQTT message on topic {msg.topic}.")
    except ValueError:
        log.error(f"Invalid payload '{payload}' on topic {msg.topic}, ignoring.")
    except Exception:  # pylint: disable=broad-except
        log.exception(f"Failed to handle MQTT message on topic {msg.topic}")


def run_on_main_loop(coro):
    """Run a coroutine on the main event loop (called from the paho thread)."""
    future = asyncio.run_coroutine_threadsafe(coro, main_loop)
    future.add_done_callback(_log_command_result)


def _log_command_result(future):
    if future.exception() is not None:
        log.error(f"MQTT command failed: {future.exception()!r}")


# Function to publish Home Assistant discovery configuration
def publish_discovery_config(
    entity_id, name, component, state_topic, command_topic=None, extra_config=None
):
    discovery_topic = f"homeassistant/{component}/{entity_id}/config"
    payload = {
        "name": name,
        "state_topic": state_topic,
        "unique_id": entity_id,
        "availability_topic": AVAILABILITY_TOPIC,
        "device": {
            "identifiers": ["jacuzzi_device"],
            "name": "Jacuzzi",
            "manufacturer": "https://github.com/jackbrown1993",
            "model": "Jacuzzi J335 (2019)",
            "sw_version": "1.0",
        },
    }
    if command_topic:
        payload["command_topic"] = command_topic
    payload.update(extra_config or {})
    mqtt_client.publish(
        discovery_topic, payload=json.dumps(payload), qos=1, retain=True
    )


async def read_spa_data(spa, lastupd):
    """This is triggered whenever spa data has changed"""
    await asyncio.sleep(1)
    if spa.lastupd != lastupd:
        lastupd = spa.lastupd
        log.info(
            f"Spa date: {spa.get_spadate()}\n"
            f"Spa time: {spa.get_spatime()}\n"
            f"Water temp: {spa.curtemp}\n"
            f"Set Temp: {spa.get_settemp()}"
        )

        # Last update
        mqtt_client.publish(
            "jacuzzi/connection/last_update",
            payload=datetime.now().astimezone().isoformat(),
            qos=0,
            retain=True,
        )

        # Connection Status
        mqtt_client.publish(
            "jacuzzi/connection/status",
            payload="1" if spa.connection_state.name == "Connected" else "0",
            qos=0,
            retain=False,
        )

        # Set Temp
        mqtt_client.publish(
            "jacuzzi/target_temperature/state",
            payload=spa.get_settemp(),
            qos=0,
            retain=False,
        )

        # Temp
        mqtt_client.publish(
            "jacuzzi/actual_temperature/state",
            payload=spa.curtemp,
            qos=0,
            retain=False,
        )

        # Ciculation Pump
        mqtt_client.publish(
            "jacuzzi/circulation_pump/state",
            payload="On" if spa.statusByte17 else "Off",
            qos=0,
            retain=False,
        )

        # UV
        mqtt_client.publish(
            "jacuzzi/uv_lamp/state",
            payload="On" if spa.isUVOn else "Off",
            qos=0,
            retain=False,
        )

        # Pump 1
        mqtt_client.publish(
            "jacuzzi/pump_1/state",
            payload=spa.get_pump(1, False),
            qos=0,
            retain=False,
        )

        # Pump 2
        mqtt_client.publish(
            "jacuzzi/pump_2/state",
            payload=spa.get_pump(2, False),
            qos=0,
            retain=False,
        )

    return lastupd


async def start_mqtt():
    global mqtt_client
    mqtt_client = mqtt.Client("jacuzzi_rs485")
    mqtt_client.username_pw_set(username=mqtt_user, password=mqtt_password)
    mqtt_client.on_connect = on_connect
    mqtt_client.on_disconnect = on_disconnect
    mqtt_client.on_message = on_message
    mqtt_client.will_set(AVAILABILITY_TOPIC, payload="offline", qos=1, retain=True)
    mqtt_client.connect(mqtt_ip, mqtt_port)
    mqtt_client.loop_start()


def publish_all_discovery():
    """Publish Home Assistant discovery config for all entities."""
    # Register control for temperature (number component for setting temperature)
    publish_discovery_config(
        entity_id="jacuzzi_temperature",
        name="Target Temperature",
        component="number",
        state_topic="jacuzzi/target_temperature/state",
        command_topic="jacuzzi/target_temperature/set",
        extra_config={
            "min": 20,
            "max": 40,
            "step": 0.5,
            "unit_of_measurement": "°C",
            "device_class": "temperature",
        },
    )

    # Register control for pump 1
    publish_discovery_config(
        entity_id="jacuzzi_pump_1_control",
        name="Pump 1",
        component="switch",
        state_topic="jacuzzi/pump_1/state",
        command_topic="jacuzzi/pump_1/set",
        extra_config={
            "payload_on": "1",
            "payload_off": "0",
            "state_on": "1",
            "state_off": "0",
            "value_template": "{{ 1 if value | int(0) > 0 else 0 }}",
            "icon": "mdi:water-pump",
        },
    )

    # Register control for pump 2
    publish_discovery_config(
        entity_id="jacuzzi_pump_2_control",
        name="Pump 2",
        component="switch",
        state_topic="jacuzzi/pump_2/state",
        command_topic="jacuzzi/pump_2/set",
        extra_config={
            "payload_on": "1",
            "payload_off": "0",
            "state_on": "1",
            "state_off": "0",
            "value_template": "{{ 1 if value | int(0) > 0 else 0 }}",
            "icon": "mdi:water-pump",
        },
    )

    # Register timestamp sensor for last update
    publish_discovery_config(
        entity_id="jacuzzi_connection_last_update",
        name="Last Update",
        component="sensor",
        state_topic="jacuzzi/connection/last_update",
        extra_config={"device_class": "timestamp", "icon": "mdi:clock"},
    )

    # Register binary sensor for connection status
    publish_discovery_config(
        entity_id="jacuzzi_connection_status",
        name="Connection Status",
        component="binary_sensor",
        state_topic="jacuzzi/connection/status",
        extra_config={
            "device_class": "connectivity",
            "payload_on": "1",
            "payload_off": "0",
            "icon": "mdi:network",
        },
    )

    # Register sensor for current temperature
    publish_discovery_config(
        entity_id="jacuzzi_temperature_sensor",
        name="Actual Temperature",
        component="sensor",
        state_topic="jacuzzi/actual_temperature/state",
        extra_config={"unit_of_measurement": "°C", "device_class": "temperature"},
    )

    # Register sensor for target temperature
    publish_discovery_config(
        entity_id="jacuzzi_target_temperature_sensor",
        name="Target Temperature",
        component="sensor",
        state_topic="jacuzzi/target_temperature/state",
        extra_config={"unit_of_measurement": "°C", "device_class": "temperature"},
    )

    # Register sensor for circulation pump
    publish_discovery_config(
        entity_id="jacuzzi_circulation_pump_sensor",
        name="Circulation Pump",
        component="binary_sensor",
        state_topic="jacuzzi/circulation_pump/state",
        extra_config={
            "device_class": "power",
            "payload_on": "On",
            "payload_off": "Off",
            "icon": "mdi:water-pump",
        },
    )

    # Register sensor for pump 1
    publish_discovery_config(
        entity_id="jacuzzi_pump_1_sensor",
        name="Pump 1",
        component="binary_sensor",
        state_topic="jacuzzi/pump_1/state",
        extra_config={
            "device_class": "power",
            "payload_on": "1",
            "payload_off": "0",
            "value_template": "{{ 1 if value | int(0) > 0 else 0 }}",
            "icon": "mdi:water-pump",
        },
    )

    # Register sensor for pump 2
    publish_discovery_config(
        entity_id="jacuzzi_pump_2_sensor",
        name="Pump 2",
        component="binary_sensor",
        state_topic="jacuzzi/pump_2/state",
        extra_config={
            "device_class": "power",
            "payload_on": "1",
            "payload_off": "0",
            "value_template": "{{ 1 if value | int(0) > 0 else 0 }}",
            "icon": "mdi:water-pump",
        },
    )

    # Register sensor for UV
    publish_discovery_config(
        entity_id="jacuzzi_uv_lamp_sensor",
        name="UV Lamp",
        component="binary_sensor",
        state_topic="jacuzzi/uv_lamp/state",
        extra_config={
            "device_class": "power",
            "payload_on": "On",
            "payload_off": "Off",
            "icon": "mdi:lightbulb-cfl",
        },
    )


async def start_app():
    global spa, main_loop
    main_loop = asyncio.get_running_loop()

    # Connect to Jacuzzi
    spa = jacuzziRS485.JacuzziRS485(jacuzzi_ip, jacuzzi_port)

    # Connect to MQTT
    await start_mqtt()

    # Start background tasks. Keep references so a crash is noticed.
    tasks = [
        asyncio.ensure_future(spa.check_connection_status()),
        asyncio.ensure_future(spa.listen()),
    ]

    lastupd = 0

    while True:
        lastupd = await read_spa_data(spa, lastupd)
        for task in tasks:
            if task.done():
                log.error(f"Background task stopped unexpectedly: {task!r}")
                # Exit so the container supervisor restarts us cleanly.
                sys.exit(1)


if __name__ == "__main__":
    asyncio.run(start_app())
