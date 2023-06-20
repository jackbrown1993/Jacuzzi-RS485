import os
import sys
import time
import asyncio
from typing import Any, Dict

from homeassistant import core, config_entries
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.core import callback
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
import homeassistant.util.dt as dt_util
from .const import DOMAIN, _LOGGER, PLATFORMS, CONF_SYNC_TIME, DEFAULT_SYNC_TIME

# Below code to import our Jacuzzi module by adding the path for 2 directories above current
sys.path.append(os.path.abspath(os.path.join(os.path.abspath(__file__), "..", "..")))
import app.jacuzziRS485 as jacuzziRS485


## NO IDEA WHAT THIS IS DOING
async def async_setup(hass: core.HomeAssistant, config: dict):
    """Configure the Balboa Spa Client component using flow only."""
    hass.data[DOMAIN] = {}

    if DOMAIN in config:
        for entry in config[DOMAIN]:
            hass.async_create_task(
                hass.config_entries.flow.async_init(
                    DOMAIN, context={"source": SOURCE_IMPORT}, data=entry
                )
            )
    return True


async def async_setup_entry(
    hass: core.HomeAssistant, entry: config_entries.ConfigEntry
) -> bool:
    """Set up platform from a ConfigEntry. In this function
      we are storing the data for the config entry in hass under
      our DOMAIN key. This will allow us to store multiple config
      entries in the event the user wants to setup the integration
    multiple times."""

    # Lets connect to Jacuzzi - Get IP address from CONF_HOST
    host = entry.data[CONF_HOST]

    unsub = entry.add_update_listener(update_listener)

    _LOGGER.info("Attempting to connect to %s", host)
    spa = jacuzziRS485.JacuzziRS485(host)
    hass.data[DOMAIN][entry.entry_id] = {"spa": spa, "unsub": unsub}

    connected = await spa.connect()
    if not connected:
        _LOGGER.error("Failed to connect to spa at %s", host)
        raise ConfigEntryNotReady

    hass.data.setdefault(DOMAIN, {})

    # Start setting up various sensors etc
    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )
    return True


async def update_listener(hass, entry):
    """Handle options update."""
    """Not sure what this is doing, looks like it's setting the spa time to match home assistant and then sleeps for a day before repeating?"""
    if entry.options.get(CONF_SYNC_TIME, DEFAULT_SYNC_TIME):
        _LOGGER.info("Setting up daily time sync.")
        spa = hass.data[DOMAIN][entry.entry_id]["spa"]

        async def sync_time():
            while entry.options.get(CONF_SYNC_TIME, DEFAULT_SYNC_TIME):
                _LOGGER.info("Syncing spa time with Home Assistant.")
                await spa.set_time(
                    time.strptime(str(dt_util.now()), "%Y-%m-%d %H:%M:%S.%f%z")
                )
                await asyncio.sleep(86400)

        hass.loop.create_task(sync_time())


class JacuzziEntity(Entity):
    """Abstract class for all Jacuzzi HASS platforms.

    Once you connect to the spa's port, it continuously sends data (at a rate
    of about 5 per second!).  The API updates the internal states of things
    from this stream, and all we have to do is read the values out of the
    accessors.
    """

    def __init__(self, hass, entry, type, num=None):
        """Initialize the spa entity."""
        self.hass = hass
        self._client = hass.data[DOMAIN][entry.entry_id]["spa"]
        self._device_name = entry.data[CONF_NAME]
        self._type = type
        self._num = num

    @property
    def name(self):
        """Return the name of the entity."""
        return f'{self._device_name}: {self._type}{self._num or ""}'

    async def async_added_to_hass(self) -> None:
        """Set up a listener for the entity."""
        async_dispatcher_connect(self.hass, DOMAIN, self._update_callback)

    @callback
    def _update_callback(self) -> None:
        """Call from dispatcher when state changes."""
        _LOGGER.debug(f"Updating {self.name} state with new data.")
        self.async_schedule_update_ha_state(force_refresh=True)

    @property
    def should_poll(self) -> bool:
        """Return false as entities should not be polled."""
        return False

    @property
    def unique_id(self):
        """Set unique_id for this entity."""
        return f'{self._device_name}-{self._type}{self._num or ""}-{self._client.get_macaddr().replace(":","")[-6:]}'

    @property
    def assumed_state(self) -> bool:
        """Return whether the state is based on actual reading from device."""
        if (self._client.lastupd + 5 * 60) < time.time():
            return True
        return False

    @property
    def available(self) -> bool:
        """Return whether the entity is available or not."""
        return self._client.connected

    @property
    def device_info(self) -> Dict[str, Any]:
        """Return the device information for this entity."""
        return {
            "identifiers": {(DOMAIN, self._client.get_macaddr())},
            "name": self._device_name,
            "manufacturer": "Jacuzzi Hot Tubs",
            "model": self._client.get_model_name(),
            "sw_version": self._client.get_ssid(),
            "connections": {(CONNECTION_NETWORK_MAC, self._client.get_macaddr())},
        }
