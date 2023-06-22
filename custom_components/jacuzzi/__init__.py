import os
import sys
import time
import asyncio
from typing import Any, Dict
from datetime import datetime, timedelta

from homeassistant import core, config_entries
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.core import callback
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
import homeassistant.util.dt as dt_util
from .const import DOMAIN, _LOGGER, PLATFORMS, CONF_SYNC_TIME, DEFAULT_SYNC_TIME

# Below code to import our Jacuzzi module by adding the path for 2 directories above current
sys.path.append(os.path.abspath(os.path.join(os.path.abspath(__file__), "..", "..")))
import app.jacuzziRS485 as jacuzziRS485

KEEP_ALIVE_INTERVAL = timedelta(minutes=1)
SYNC_TIME_INTERVAL = timedelta(hours=1)


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

    if not await spa.connect():
        _LOGGER.error("Failed to connect to spa at %s", host)
        raise ConfigEntryNotReady("Unable to connect")

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = spa

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    await async_setup_time_sync(hass, entry)
    entry.async_on_unload(entry.add_update_listener(update_listener))

    return True


async def async_unload_entry(hass: core.HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.debug("Disconnecting from spa")
    # spa: SpaClient = hass.data[DOMAIN][entry.entry_id]

    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    await spa.disconnect()

    return unload_ok


async def update_listener(hass: core.HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_setup_time_sync(hass: core.HomeAssistant, entry: ConfigEntry) -> None:
    """Set up the time sync."""
    if not entry.options.get(CONF_SYNC_TIME, DEFAULT_SYNC_TIME):
        return

    _LOGGER.debug("Setting up daily time sync")
    spa = hass.data[DOMAIN][entry.entry_id]

    async def sync_time(now: datetime) -> None:
        now = dt_util.as_local(now)
        if (now.hour, now.minute) != (spa.time_hour, spa.time_minute):
            _LOGGER.debug("Syncing time with Home Assistant")
            await spa.set_time(now.hour, now.minute)

    await sync_time(dt_util.utcnow())
    entry.async_on_unload(
        async_track_time_interval(hass, sync_time, SYNC_TIME_INTERVAL)
    )


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
        return True

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
            "manufacturer": "Jacuzzi Hot Tub",
            "model": self._client.get_model_name(),
            "sw_version": self._client.get_ssid(),
            "connections": {(CONNECTION_NETWORK_MAC, self._client.get_macaddr())},
        }
