# Security Policy

## Reporting a vulnerability

Please report security issues privately using GitHub's **Report a vulnerability**
(the **Security** tab → *Advisories*) on this repository. If you can't, open a
minimal issue that contains **no personal data** and ask a maintainer to follow
up privately.

Do **not** include your Zephyr credentials, Cognito/ID tokens, device
`thingName`, `MAC`, `SN`, or home location in issues, logs, or screenshots.

## What this integration handles

- **Your Zephyr password is stored in your Home Assistant config entry**,
  alongside your email and the Cognito **refresh token** issued at sign-in.
  HA's `.storage` is plain JSON on disk, not encrypted, so anyone who can read
  your HA config directory or an unencrypted backup can read it. It's stored
  because Cognito refresh tokens have a hard ~30-day lifetime: without the
  password, the integration would stop working every month until you
  re-entered it. Day to day, sign-in uses the refresh token; the password is
  sent (only to Zephyr's own Cognito pool) when that token expires. Versions
  0.4.x did not store the password; entries created by them will prompt for
  reauth once when their token expires, and keep the password from then on.
  Use a unique password for your Zephyr account, and if you ever shared it
  (e.g. while debugging), rotate it.
- **The AWS Cognito pool/client IDs and client secret in `const.py` are not your
  secrets.** They are the public Zephyr Connect app's own configuration —
  identical in every copy of the app — and are required for Cognito's
  `SECRET_HASH` sign-in. They identify the shared Zephyr backend, not an account.
- **TLS is verified.** Certificate-chain and hostname verification stay enabled
  (anchored to the `certifi` CA bundle). Only the strict X.509 *Subject Key
  Identifier* check is relaxed for the Zephyr/Gemtek API, whose certificate omits
  that extension. Certificate validation is **not** disabled.
- **No secrets are logged.** Credentials, tokens, and the SigV4-signed MQTT URL
  are never written to the log. Auth failures log only the provider's generic
  error message.

## Scrubbing shared logs

When attaching logs or diagnostics to a bug report, redact any `thingName`,
`MAC`, `SN`, and `location`/latitude-longitude values returned by the device API.
