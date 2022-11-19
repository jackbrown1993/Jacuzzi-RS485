import sundanceRS485

import asyncio
import paho.mqtt.client as mqtt
import os
from datetime import datetime

mqtt_host = os.environ.get("MQTT_HOST")
mqtt_port = int(os.environ.get("MQTT_PORT"))
mqtt_user = os.environ.get("MQTT_USER")
mqtt_password = os.environ.get("MQTT_PASSWORD")

serial_ip = os.environ.get("SERIAL_IP")
serial_port = int(os.environ.get("SERIAL_PORT"))

client = mqtt.Client("jacuzzi_app")
client.username_pw_set(username=mqtt_user, password=mqtt_password)
client.connect(mqtt_host, mqtt_port, 10)

client.publish("homie/hot_tub/$homie", payload="3.0", qos=0, retain=False)
client.publish("homie/hot_tub/$name", payload="Acorns J335", qos=0, retain=False)
client.publish("homie/hot_tub/$state", payload="ready", qos=0, retain=False)
client.publish("homie/hot_tub/$nodes", payload="J335", qos=0, retain=False)

client.publish(
    "homie/hot_tub/J335/set_temperature/$name",
    payload="Set Temperature",
    qos=0,
    retain=False,
)
client.publish(
    "homie/hot_tub/J335/set_temperature/$unit", payload="°C", qos=0, retain=False
)
client.publish(
    "homie/hot_tub/J335/set_temperature/$datatype",
    payload="integer",
    qos=0,
    retain=False,
)
client.publish(
    "homie/hot_tub/J335/set_temperature/$settable", payload="true", qos=0, retain=False
)

client.publish(
    "homie/hot_tub/J335/temperature/$name", payload="Temperature", qos=0, retain=False
)
client.publish(
    "homie/hot_tub/J335/temperature/$unit", payload="°C", qos=0, retain=False
)
client.publish(
    "homie/hot_tub/J335/temperature/$datatype", payload="integer", qos=0, retain=False
)
client.publish(
    "homie/hot_tub/J335/temperature/$settable", payload="false", qos=0, retain=False
)


async def ReadR(spa, lastupd):
    await asyncio.sleep(1)
    if spa.lastupd != lastupd:
        lastupd = spa.lastupd
        print(
            "New data as of "
            + datetime.utcfromtimestamp(spa.lastupd).strftime("%d-%m-%Y %H:%M:%S")
        )

        print("Set Temp: {0}".format(spa.get_settemp()))
        print("Current Temp: {0}".format(spa.curtemp))
        client.publish(
            "homie/hot_tub/J335/set_temperature",
            payload=spa.get_settemp(),
            qos=0,
            retain=False,
        )

        client.publish(
            "homie/hot_tub/J335/temperature", payload=spa.curtemp, qos=0, retain=False
        )

        print()
    return lastupd


async def newFormatTest():
    """Test a miniature engine of talking to the spa."""
    spa = sundanceRS485.SundanceRS485(serial_ip, serial_port)
    await spa.connect()

    asyncio.ensure_future(spa.listen())
    lastupd = 0
    for i in range(0, 9999999999):
        lastupd = await ReadR(spa, lastupd)
    return

    print("Pump Array: {0}".format(str(spa.pump_array)))
    print("Light Array: {0}".format(str(spa.light_array)))
    print("Aux Array: {0}".format(str(spa.aux_array)))
    print("Circulation Pump: {0}".format(spa.circ_pump))
    print("Blower: {0}".format(spa.blower))
    print("Mister: {0}".format(spa.mister))
    print("Min Temps: {0}".format(spa.tmin))
    print("Max Temps: {0}".format(spa.tmax))
    print("Nr of pumps: {0}".format(spa.nr_of_pumps))
    print("Tempscale: {0}".format(spa.get_tempscale(text=True)))
    print("Heat Mode: {0}".format(spa.get_heatmode(True)))
    print("Temp Range: {0}".format(spa.get_temprange(True)))
    print("Blower Status: {0}".format(spa.get_blower(True)))
    print("Mister Status: {0}".format(spa.get_mister(True)))
    print("Filter Mode: {0}".format(spa.get_filtermode(True)))
    lastupd = 0


if __name__ == "__main__":

    asyncio.run(newFormatTest())
