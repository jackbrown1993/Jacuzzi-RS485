import logging

from homeassistant.components.climate.const import (
    HVAC_MODE_HEAT
)

_LOGGER = logging.getLogger(__name__)

DOMAIN = "jacuzzi"
DEFAULT_JACUZZI_PORT = 4257
PLATFORMS = ["climate"]
CONF_SYNC_TIME = "sync_time"
DEFAULT_SYNC_TIME = False
CLIMATE_SUPPORTED_MODES = [HVAC_MODE_HEAT]