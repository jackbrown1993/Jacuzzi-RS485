import os
import sys
import voluptuous as vol
from homeassistant import core, config_entries, exceptions
from homeassistant.const import CONF_HOST, CONF_NAME

from .const import DOMAIN, DEFAULT_JACUZZI_PORT, _LOGGER


# Below code to import our Jacuzzi module by adding the path for 2 directories above current
sys.path.append(os.path.abspath(os.path.join(os.path.abspath(__file__), '..', '..')))
import app.jacuzziRS485 as jacuzziRS485

##In this example, the MyHacsConfigFlow class extends config_entries.ConfigFlow and sets the DOMAIN variable to the name of your integration. The async_step_user method is responsible for handling the configuration flow.
##Inside async_step_user, we first check if user_input is not None. If it's not None, we retrieve the IP address and port number from the user input and perform validation using the validate_ip_address and validate_port functions.
##If there are no validation errors, we call self.async_create_entry to create the integration entry using the provided IP address and port number.
##If there are validation errors or user_input is None, we use self.async_show_form to display the form to the user. The form consists of two fields, ip_address and port, both marked as required. Any validation errors are passed to the form for display.
##You can customize the validate_ip_address and validate_port functions to add your specific validation logic for IP address and port number.

# This data schema defines what we are asking and other options which will display in UI such as labels and default values
DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME, default='Jacuzzi'): str,
        vol.Required(CONF_HOST, default='10.100.10.216'): str,
        vol.Optional('jacuzzi_port', default=DEFAULT_JACUZZI_PORT): int
    }
)

async def validate_input(hass: core.HomeAssistant, data):
    """Validate the user input allows us to connect."""
    for entry in hass.config_entries.async_entries(DOMAIN):
        if entry.data[CONF_HOST] == data[CONF_HOST]:
            raise AlreadyConfigured

    _LOGGER.debug("Attempting to connect to %s", data[CONF_HOST])
    spa = jacuzziRS485.JacuzziRS485(data[CONF_HOST], data['jacuzzi_port'])
    await spa.connect()

    if spa.connected:
        _LOGGER.info("Successfully connected to Jacuzzi ({}:{})".format(data[CONF_HOST], data['jacuzzi_port']))
        # Disconnect from spa
        await spa.disconnect()
        return {"title": data[CONF_NAME]}
    else:
        raise CannotConnect

class JacuzziConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    ## This is first form shown after user adds integration, it asks for defined values.
    async def async_step_user(self, user_input=None):
        errors = {}

        # user_input will be populated when user submits the form, so on submit we should validate input
        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
                # Continue to add and create the integration
                return self.async_create_entry(title=info["title"], data=user_input)
            except AlreadyConfigured:
                return self.async_abort(reason="already_configured")
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
    
        # No user_input so show form asking for data input
        return self.async_show_form(
            step_id='user',
            data_schema=DATA_SCHEMA,
            errors=errors
        )

class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


class AlreadyConfigured(exceptions.HomeAssistantError):
    """Error to indicate this device is already configured."""