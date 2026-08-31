"""Climate Push (Webhook), sendet gewaehlte Klimawerte signiert an ein Dashboard.

Datenschutz: Es verlaesst KEIN Home-Assistant-Token das Haus. Die Integration liest
lokal die gewaehlten Sensoren und schickt ausschliesslich die Messwerte
(Temperatur/Feuchte) per ausgehendem, HMAC-signiertem POST an die im Kopplungscode
hinterlegte URL. Kein eingehender Port, kein Cloud-Abo noetig.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import secrets
import time
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_track_time_interval

from .const import (
    CONF_HUMIDITY_ENTITY,
    CONF_INTERVAL,
    CONF_SECRET,
    CONF_SOIL_ENTITY,
    CONF_TEMPERATURE_ENTITY,
    CONF_TOKEN,
    CONF_URL,
    DEFAULT_INTERVAL,
    DOMAIN,
    HTTP_TIMEOUT,
    PAYLOAD_VERSION,
    SIGNATURE_HEADER,
)

_LOGGER = logging.getLogger(__name__)

_INVALID_STATES = {"unknown", "unavailable", "none", ""}
_METRIC_RANGES = {
    "temperature": (-30.0, 70.0),
    "humidity": (0.0, 100.0),
    "soil_moisture": (0.0, 100.0),
}


def _reading(hass: HomeAssistant, entity_id: str | None, metric: str, unit: str) -> dict | None:
    """Liest einen Sensor als Messwert, oder None wenn ungueltig/ausserhalb Range."""
    if not entity_id:
        return None
    state = hass.states.get(entity_id)
    if state is None:
        return None
    raw = str(state.state).strip().lower().replace(",", ".")
    if raw in _INVALID_STATES:
        return None
    try:
        value = round(float(raw), 1)
    except (TypeError, ValueError):
        return None
    lo, hi = _METRIC_RANGES[metric]
    if value < lo or value > hi:
        return None
    return {"metric": metric, "value": value, "unit": unit}


async def _send_once(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Baut die aktuelle Nutzlast, signiert sie und sendet sie fail-soft."""
    cfg = {**entry.data, **entry.options}
    readings = []
    for entity_id, metric, unit in (
        (cfg.get(CONF_TEMPERATURE_ENTITY), "temperature", "C"),
        (cfg.get(CONF_HUMIDITY_ENTITY), "humidity", "%"),
        (cfg.get(CONF_SOIL_ENTITY), "soil_moisture", "%"),
    ):
        item = _reading(hass, entity_id, metric, unit)
        if item is not None:
            readings.append(item)

    if not readings:
        _LOGGER.debug("Climate Push: keine gueltigen Messwerte, nichts gesendet")
        return

    payload = {
        "v": PAYLOAD_VERSION,
        "plant_token": cfg[CONF_TOKEN],
        "ts": int(time.time()),
        "nonce": secrets.token_hex(16),
        "readings": readings,
    }
    body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    signature = hmac.new(
        cfg[CONF_SECRET].encode("utf-8"), body, hashlib.sha256
    ).hexdigest()

    session = async_get_clientsession(hass)
    try:
        async with session.post(
            cfg[CONF_URL],
            data=body,
            headers={
                "Content-Type": "application/json",
                SIGNATURE_HEADER: f"sha256={signature}",
            },
            timeout=HTTP_TIMEOUT,
        ) as resp:
            if resp.status >= 400:
                text = (await resp.text())[:200]
                _LOGGER.warning(
                    "Climate Push: Server antwortete HTTP %s (%s)", resp.status, text
                )
            else:
                _LOGGER.debug("Climate Push: %d Messwert(e) gesendet", len(readings))
    except Exception as err:  # noqa: BLE001, bewusst fail-soft, naechstes Intervall probiert erneut
        _LOGGER.warning("Climate Push: Senden fehlgeschlagen: %s", err)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    interval = int({**entry.data, **entry.options}.get(CONF_INTERVAL, DEFAULT_INTERVAL))

    async def _tick(_now) -> None:
        await _send_once(hass, entry)

    unsub = async_track_time_interval(hass, _tick, timedelta(minutes=interval))
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = unsub
    entry.async_on_unload(entry.add_update_listener(_async_reload))

    # Erstwert direkt senden (nicht erst nach einem Intervall).
    hass.async_create_task(_send_once(hass, entry))
    return True


async def _async_reload(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unsub = hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    if unsub is not None:
        unsub()
    return True
