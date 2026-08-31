# Climate Push (Webhook)

A small, privacy focused Home Assistant custom integration. It sends selected climate
readings (temperature, humidity, optionally soil moisture) to an external dashboard using
a signed outbound webhook, so no Home Assistant access token ever leaves your network.

## Design goals

- **No credentials leave the home.** Home Assistant reads local sensors and pushes only the
  chosen readings. The dashboard never gets access to Home Assistant.
- **Data minimisation.** Only the sensors you select are transmitted. No entity names, no
  locations, no other state.
- **Works behind NAT.** A plain outbound HTTPS POST, so no inbound port and no cloud
  subscription are required.
- **Authenticated and replay safe.** Every request is signed with HMAC-SHA256 over the raw
  body and carries a timestamp plus a one time nonce.

## How it works

1. The user copies a pairing code from the dashboard. It encodes the target URL, a public
   token and a signing secret (`CLIMATE1.<base64url json>`).
2. The integration is configured through the Home Assistant UI: paste the code, pick the
   temperature and humidity sensors, choose the send interval.
3. On each interval the integration builds a compact JSON payload, signs it and POSTs it.

```json
{
  "v": 1,
  "plant_token": "<public handle>",
  "ts": 1730000000,
  "nonce": "<random>",
  "readings": [
    { "metric": "temperature", "value": 24.1, "unit": "C" },
    { "metric": "humidity", "value": 55, "unit": "%" }
  ]
}
```

Header: `X-Climate-Signature: sha256=<hmac_sha256(secret, raw_body)>`

## Installation

**HACS (custom repository):** add this repository as an Integration, install
"Climate Push (Webhook)", restart Home Assistant.

**Manual:** copy `custom_components/climate_push` into your Home Assistant `config` folder
and restart.

## Configuration

Settings, Devices and Services, Add Integration, "Climate Push". Paste the pairing code,
select your sensors, confirm the interval (default 10 minutes). An options flow lets you
change the sensors or interval later. Removing the integration or revoking the connection
on the dashboard side stops all data flow.

## Structure

```
custom_components/climate_push/
  __init__.py       sender: reads sensors, signs, POSTs (fail soft, periodic)
  config_flow.py    UI setup + options, pairing code parsing
  const.py          constants
  manifest.json     integration metadata
  strings.json      UI strings (en) + translations/de.json
```

## License

MIT

## About this snapshot

Little had to be removed here, since the integration is built to carry no
addresses in the first place: the dashboard URL arrives at runtime inside the
pairing code. The publishing pass ran over it anyway, replacing internal paths
with placeholders and requiring two secret scanners to pass.

Single commit, because the history stays private. This runs in my own Home
Assistant.
