"""Config-Flow: Kopplungscode eintragen + Sensoren waehlen. Kein HA-Token verlaesst das Haus."""
from __future__ import annotations

import base64
import binascii
import json
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    CONF_HUMIDITY_ENTITY,
    CONF_INTERVAL,
    CONF_PAIRING_CODE,
    CONF_SECRET,
    CONF_SOIL_ENTITY,
    CONF_TEMPERATURE_ENTITY,
    CONF_TOKEN,
    CONF_URL,
    DEFAULT_INTERVAL,
    DOMAIN,
    MAX_INTERVAL,
    MIN_INTERVAL,
    PAIRING_PREFIX,
)


def parse_pairing_code(code: str) -> dict[str, str] | None:
    """Dekodiert den Kopplungscode (CLIMATE1.<base64url json>).

    Erwartet URL + Token + Secret. Gibt None bei ungueltigem Code zurueck.
    """
    code = (code or "").strip()
    if "." not in code:
        return None
    prefix, _, payload = code.partition(".")
    if prefix != PAIRING_PREFIX or not payload:
        return None
    padding = "=" * (-len(payload) % 4)
    try:
        raw = base64.urlsafe_b64decode(payload + padding)
        data = json.loads(raw.decode("utf-8"))
    except (binascii.Error, ValueError, UnicodeDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    url = str(data.get("url", "")).strip()
    token = str(data.get("token", "")).strip()
    secret = str(data.get("secret", "")).strip()
    if not url.startswith("https://") or not token or not secret:
        return None
    return {"url": url, "token": token, "secret": secret}


def _sensor_selector(device_class: str) -> selector.EntitySelector:
    return selector.EntitySelector(
        selector.EntitySelectorConfig(domain="sensor", device_class=device_class)
    )


def _base_schema(defaults: dict[str, Any] | None = None) -> vol.Schema:
    defaults = defaults or {}
    return vol.Schema(
        {
            vol.Required(
                CONF_TEMPERATURE_ENTITY,
                default=defaults.get(CONF_TEMPERATURE_ENTITY, vol.UNDEFINED),
            ): _sensor_selector("temperature"),
            vol.Optional(
                CONF_HUMIDITY_ENTITY,
                default=defaults.get(CONF_HUMIDITY_ENTITY, vol.UNDEFINED),
            ): _sensor_selector("humidity"),
            vol.Optional(
                CONF_SOIL_ENTITY,
                default=defaults.get(CONF_SOIL_ENTITY, vol.UNDEFINED),
            ): _sensor_selector("moisture"),
            vol.Optional(
                CONF_INTERVAL, default=defaults.get(CONF_INTERVAL, DEFAULT_INTERVAL)
            ): vol.All(vol.Coerce(int), vol.Range(min=MIN_INTERVAL, max=MAX_INTERVAL)),
        }
    )


class ClimatePushConfigFlow(ConfigFlow, domain=DOMAIN):
    """UI-gefuehrte Einrichtung."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        errors: dict[str, str] = {}
        if user_input is not None:
            pairing = parse_pairing_code(user_input.get(CONF_PAIRING_CODE, ""))
            if pairing is None:
                errors["base"] = "invalid_code"
            elif not user_input.get(CONF_TEMPERATURE_ENTITY) and not user_input.get(
                CONF_HUMIDITY_ENTITY
            ):
                errors["base"] = "no_sensor"
            else:
                await self.async_set_unique_id(pairing["token"])
                self._abort_if_unique_id_configured()
                data = {
                    CONF_URL: pairing["url"],
                    CONF_TOKEN: pairing["token"],
                    CONF_SECRET: pairing["secret"],
                    CONF_TEMPERATURE_ENTITY: user_input.get(CONF_TEMPERATURE_ENTITY),
                    CONF_HUMIDITY_ENTITY: user_input.get(CONF_HUMIDITY_ENTITY),
                    CONF_SOIL_ENTITY: user_input.get(CONF_SOIL_ENTITY),
                    CONF_INTERVAL: int(user_input.get(CONF_INTERVAL, DEFAULT_INTERVAL)),
                }
                return self.async_create_entry(title="Climate Push", data=data)

        schema = vol.Schema(
            {vol.Required(CONF_PAIRING_CODE): selector.TextSelector()}
        ).extend(_base_schema().schema)
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return ClimatePushOptionsFlow(config_entry)


class ClimatePushOptionsFlow(OptionsFlow):
    """Sensoren/Intervall nachtraeglich aendern (Kopplung bleibt bestehen)."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        self._entry = config_entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)
        merged = {**self._entry.data, **self._entry.options}
        return self.async_show_form(step_id="init", data_schema=_base_schema(merged))
