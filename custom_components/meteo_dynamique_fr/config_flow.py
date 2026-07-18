"""Config flow pour Météo Dynamique (Météo-France)."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import CONF_NAME, CONF_SCAN_INTERVAL, CONF_TRACKER_ENTITY, DEFAULT_SCAN_INTERVAL_MINUTES, DOMAIN


class MeteoDynamiqueConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Gère le flux de configuration : une instance = une position suivie."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> config_entries.FlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            # Un titre unique par entité suivie pour permettre plusieurs instances
            await self.async_set_unique_id(f"{DOMAIN}_{user_input[CONF_TRACKER_ENTITY]}")
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title=user_input[CONF_NAME],
                data=user_input,
            )

        schema = vol.Schema(
            {
                vol.Required(CONF_NAME): selector.TextSelector(),
                vol.Required(CONF_TRACKER_ENTITY): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain=["person", "device_tracker", "zone"])
                ),
                vol.Optional(
                    CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL_MINUTES
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=5, max=120, step=5, unit_of_measurement="min")
                ),
            }
        )

        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> MeteoDynamiqueOptionsFlow:
        return MeteoDynamiqueOptionsFlow(config_entry)


class MeteoDynamiqueOptionsFlow(config_entries.OptionsFlow):
    """Permet de changer l'intervalle de rafraîchissement après coup."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self.config_entry = config_entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> config_entries.FlowResult:
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current = self.config_entry.options.get(
            CONF_SCAN_INTERVAL,
            self.config_entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_MINUTES),
        )

        schema = vol.Schema(
            {
                vol.Optional(CONF_SCAN_INTERVAL, default=current): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=5, max=120, step=5, unit_of_measurement="min")
                ),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
