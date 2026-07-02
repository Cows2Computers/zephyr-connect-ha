# Zephyr Hood — Home Assistant Integration

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)

A Home Assistant custom integration for **Zephyr Connect** Wi-Fi range hoods. It
talks to the same cloud backend the official Zephyr Connect app uses, so you can
control and monitor your hood from Home Assistant — including local automations,
dashboards, and voice assistants.

State updates are **pushed** in real time over MQTT, so changes made from the
wall control or the app show up in Home Assistant immediately (no polling).

## Features

| Platform | Entity | Notes |
|----------|--------|-------|
| `fan` | Blower | On/off + speed (maps to the hood's speed steps) |
| `light` | Cooktop light | On/off + brightness (maps to the hood's light levels) |
| `switch` | Recirculating mode | Ductless / recirculating toggle |
| `switch` | Clean air | Periodic auto-ventilation function |
| `number` | Delay off | Delayed shut-off timer (minutes) |
| `sensor` | Grease / charcoal filter life | % of filter life remaining (100% fresh → 0% replace), matching the app |
| `sensor` | Fan / light runtime | Cumulative on-time, minutes (diagnostic) |
| `sensor` | Fault code | Reported hood fault(s), `OK` when clear |
| `binary_sensor` | Online | Cloud connectivity (connectivity class) |
| `binary_sensor` | Grease / charcoal filter | Needs cleaning — derived from usage ≥ 85% of max (problem class) |
| `button` | Reset grease / charcoal filter | Clears the usage counter after you clean/replace a filter |

> Per-device maxes (fan speeds, light levels, filter life hours) are read from the
> hood's `/discoverdevice` record; filter life and fan/light ranges are accurate
> per model. Available controls otherwise populate from the hood's reported state.

## Installation

### HACS (recommended)
1. HACS → ⋮ → **Custom repositories** → add this repo, category **Integration**.
2. Install **Zephyr Hood**, then restart Home Assistant.
3. **Settings → Devices & Services → Add Integration → Zephyr Hood**.
4. Sign in with your Zephyr Connect app email and password.

### Manual
1. Copy `custom_components/zephyr_hood` into your HA `custom_components` folder.
2. Restart Home Assistant and add the integration as above.

## How it works

The Zephyr Connect app is an AWS Amplify application. This integration speaks the
same protocol, implemented in pure Python (no `awscrt`/native extensions, so it
runs cleanly on Home Assistant OS):

1. **Auth** — Cognito User Pool sign-in via SRP (`pycognito`).
2. **Credentials** — the Cognito ID token is exchanged at the Cognito Identity
   Pool for short-lived AWS credentials.
3. **Devices** — the account's hoods are fetched from the Zephyr app API.
4. **State & control** — AWS IoT **Device Shadow** over MQTT (WebSocket, SigV4):
   the integration subscribes to the shadow for live state and writes the
   shadow to send commands.

The AWS identifiers in `const.py` (Cognito pool/client IDs, IoT endpoint) are the
app's own public configuration — they are embedded in every copy of the Zephyr
Connect app and are required for sign-in to work. They are **not** account
secrets; you still authenticate with your personal email and password, which are
stored only in your Home Assistant config entry.

## Security & privacy

- **Your credentials stay in your HA.** Your Zephyr email/password live in the
  config entry (HA's encrypted `.storage`) and are sent only to Zephyr's own
  Cognito sign-in — never to this project or any third party. No secrets
  (credentials, tokens, or the signed MQTT URL) are written to the log.
- **The `const.py` AWS IDs/secret are not yours.** They're the public app's own
  configuration, identical in every APK, required for Cognito `SECRET_HASH`
  sign-in. They identify the shared Zephyr backend, not an account.
- **TLS stays verified.** Chain + hostname verification remain on (anchored to
  `certifi`); only the strict X.509 *Subject Key Identifier* check is relaxed for
  the Zephyr/Gemtek API cert, which omits that extension. Validation is **not**
  disabled.
- **Data stays local.** The integration talks only to the same Zephyr/Gemtek and
  AWS IoT endpoints the official app uses. Everything runs inside your HA; there
  is no extra telemetry.
- **Unofficial & cloud-dependent.** Built by reverse-engineering the public app;
  not affiliated with or endorsed by Zephyr. It uses undocumented endpoints and
  could break if Zephyr changes its backend.

See [SECURITY.md](SECURITY.md) for vulnerability reporting and log-scrubbing
guidance.

## Credits & acknowledgments

This project began as a fork of
[**Cows2Computers/zephyr-connect-ha**](https://github.com/Cows2Computers/zephyr-connect-ha)
by Eric (Cows2Computers), which laid out the original integration scaffold and
goal. The cloud backend (Cognito + AWS IoT Device Shadow) and the entity
implementations in this release were built on top of that starting point. The
original work is MIT-licensed and that copyright is retained in
[LICENSE](LICENSE) — thank you for the head start.

Community integration, not affiliated with or endorsed by Zephyr. Built by
reverse-engineering the public app. Contributions welcome — please open an issue
to discuss substantial changes first.

## License

MIT
