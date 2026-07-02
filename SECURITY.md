# Security Policy

## Reporting a vulnerability

Please report security issues privately using GitHub's **Report a vulnerability**
(the **Security** tab → *Advisories*) on this repository. If you can't, open a
minimal issue that contains **no personal data** and ask a maintainer to follow
up privately.

Do **not** include your Zephyr credentials, Cognito/ID tokens, device
`thingName`, `MAC`, `SN`, or home location in issues, logs, or screenshots.

## What this integration handles

- **Your Zephyr password is never persisted.** It's used once, in memory, to sign
  in to Zephyr's own Cognito pool, then discarded. What's stored in your Home
  Assistant config entry (HA's encrypted `.storage`) is your email and the
  Cognito **refresh token** issued at sign-in, which is scoped to that pool and
  can't be used to derive your password. If the refresh token expires, HA's
  reauth flow will ask you to enter your password again (again used once, not
  stored). Existing config entries created before this change had the password
  stored; they are automatically migrated to a refresh token the next time the
  integration starts. If you ever shared your password (e.g. while debugging),
  rotate it.
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
