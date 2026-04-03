# Zephyr Hood - Home Assistant Integration

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)

A Home Assistant custom integration for Zephyr Connect-compatible range hoods.

## Supported Models

- ALU-E43CSX (Lux Connect Island 43")
- ALU-E43CWX
- ALU-E63CSX
- ALU-E63CWX
- Other Zephyr Connect-compatible models

## Features

- **Fan control** — turn on/off and set speed (6 speeds)
- **Light control** — turn on/off and set brightness (3 levels)
- **Filter status sensor** — get notified when filters need cleaning
- **Fan speed sensor** — monitor current fan speed
- Full integration with Home Assistant automations and dashboards

## Status

> ⚠️ **This integration is under active development.** API endpoints are being reverse engineered. Not yet functional.

## Installation

### HACS (Recommended)
1. Add this repo as a custom repository in HACS
2. Install "Zephyr Hood"
3. Restart Home Assistant
4. Go to Settings → Integrations → Add Integration → Zephyr Hood
5. Enter your Zephyr Connect app email and password

### Manual
1. Copy `custom_components/zephyr_hood` to your HA `custom_components` folder
2. Restart Home Assistant

## Configuration

Enter your Zephyr Connect app credentials when prompted during setup.

## Development

This integration was built by reverse engineering the Zephyr Connect Android app API using mitmproxy. 

### API Notes
> API endpoint details to be documented here after traffic analysis is complete.

## Contributing

Pull requests welcome! Please open an issue first to discuss major changes.

## License

MIT
