"""Zephyr Connect cloud client.

Flow (all reverse-engineered + verified against a real ZVE hood):
  email/password -> Cognito User Pool (SRP)            [pycognito]
                 -> Cognito Identity Pool -> AWS creds [plain HTTPS]
  device list    -> Gemtek API  POST /getowndevices    [Cognito IdToken]
  state+control  -> AWS IoT MQTT (WebSocket, SigV4)     [paho-mqtt]
                    read : subscribe $aws/things/{t}/shadow/get|update/accepted
                    write: publish  $aws/things/{t}/shadow/update
                           {"state":{"reported":{<field>:<value>}}}
"""
from __future__ import annotations

import base64
import datetime
import hashlib
import hmac
import json
import logging
import ssl
import threading
import urllib.error
import urllib.parse
import urllib.request
import uuid
from collections.abc import Callable
from typing import Any

import paho.mqtt.client as mqtt
from pycognito import Cognito

from .const import (
    APP_API_BASE_URL,
    AWS_REGION,
    COGNITO_APP_CLIENT_ID,
    COGNITO_APP_CLIENT_SECRET,
    COGNITO_IDENTITY_POOL_ID,
    COGNITO_USER_POOL_ID,
    IOT_ENDPOINT,
)

_LOGGER = logging.getLogger(__name__)

# paho logs every PUBLISH/PINGREQ/PINGRESP at DEBUG, which drowns out HA's own
# debug log for this integration. Keep it quiet unless explicitly re-enabled.
logging.getLogger("paho").setLevel(logging.WARNING)

_RECONNECT_MIN_DELAY = 1
_RECONNECT_MAX_DELAY = 60


class ZephyrAuthError(Exception):
    """Raised on Cognito authentication failure (bad credentials)."""


class ZephyrApiError(Exception):
    """Raised on any other cloud/API failure."""


def _build_certifi_context() -> ssl.SSLContext:
    try:
        import certifi

        return ssl.create_default_context(cafile=certifi.where())
    except Exception:  # noqa: BLE001 - fall back to the system store
        return ssl.create_default_context()


def build_aws_ssl_context() -> ssl.SSLContext:
    """Verifying SSL context for AWS endpoints (Cognito Identity, IoT Core).

    On Home Assistant OS the system CA store does not verify these chains, even
    though botocore's bundled certifi store does, so we anchor to certifi to
    match behaviour everywhere. AWS's own certs pass strict X.509 checks, so
    unlike the Gemtek context below we leave strict mode enabled.
    """
    return _build_certifi_context()


def build_gemtek_ssl_context() -> ssl.SSLContext:
    """Verifying SSL context for the Gemtek app API.

    Same CA anchoring as `build_aws_ssl_context`, plus one extra quirk: the
    Gemtek cert is missing the Subject Key Identifier extension, which Python
    3.13's strict mode rejects. We keep full chain + hostname verification but
    drop only the strict RFC checks.
    """
    ctx = _build_certifi_context()
    if hasattr(ssl, "VERIFY_X509_STRICT"):
        ctx.verify_flags &= ~ssl.VERIFY_X509_STRICT
    return ctx


def _jwt_claim(token: str, claim: str) -> str | None:
    """Read one claim out of a JWT's payload, without verifying its signature.

    Used only to recover Cognito's internal `cognito:username` (a UUID-style
    id, distinct from the email alias used to sign in) from a token we already
    trust because we just received it directly from Cognito over TLS.
    """
    try:
        payload = token.split(".")[1]
        padded = payload + "=" * (-len(payload) % 4)
        return json.loads(base64.urlsafe_b64decode(padded)).get(claim)
    except Exception:  # noqa: BLE001
        return None


class ZephyrCloud:
    """Synchronous Zephyr cloud client. Blocking calls run in HA's executor."""

    def __init__(
        self,
        email: str,
        password: str | None = None,
        refresh_token: str | None = None,
        cognito_username: str | None = None,
    ) -> None:
        self._email = email
        self._password = password
        self._refresh_token = refresh_token
        self._cognito_username = cognito_username
        self._cognito: Cognito | None = None
        self._lock = threading.Lock()
        self._client: mqtt.Client | None = None
        self._on_state: Callable[[str, dict[str, Any]], None] | None = None
        self._things: set[str] = set()
        self._ssl_aws: ssl.SSLContext | None = None
        self._ssl_gemtek: ssl.SSLContext | None = None
        self._reconnect_delay = _RECONNECT_MIN_DELAY
        self._closing = False

    def _ctx_aws(self) -> ssl.SSLContext:
        """Lazily build the AWS SSL context. Only called from executor threads
        so the cert-file load never blocks the event loop."""
        if self._ssl_aws is None:
            self._ssl_aws = build_aws_ssl_context()
        return self._ssl_aws

    def _ctx_gemtek(self) -> ssl.SSLContext:
        """Lazily build the Gemtek SSL context. Only called from executor
        threads so the cert-file load never blocks the event loop."""
        if self._ssl_gemtek is None:
            self._ssl_gemtek = build_gemtek_ssl_context()
        return self._ssl_gemtek

    # ----------------------------------------------------------------- auth ----
    @property
    def refresh_token(self) -> str | None:
        """Current Cognito refresh token. Callers should persist this instead
        of the account password once available."""
        if self._cognito is not None:
            return self._cognito.refresh_token
        return self._refresh_token

    @property
    def cognito_username(self) -> str | None:
        """Cognito's internal username (the `cognito:username` claim).

        This is a UUID-style id assigned when the pool has email configured as
        an alias rather than the primary username attribute — which is our
        case. It's required (instead of the email) to compute SECRET_HASH for
        the REFRESH_TOKEN_AUTH flow; Cognito accepts the email alias for the
        initial SRP login but rejects it here. Persist alongside the refresh
        token so future renewals don't need the password.
        """
        return self._cognito_username

    def authenticate(self) -> None:
        """Sign in to the Cognito User Pool. Raises ZephyrAuthError.

        Prefers renewing from a stored refresh token (no password needed) and
        only falls back to a full SRP password login when that's unavailable
        or has expired.
        """
        if self._refresh_token and self._cognito_username:
            cog = Cognito(
                COGNITO_USER_POOL_ID,
                COGNITO_APP_CLIENT_ID,
                client_secret=COGNITO_APP_CLIENT_SECRET,
                user_pool_region=AWS_REGION,
                username=self._cognito_username,
                refresh_token=self._refresh_token,
            )
            try:
                cog.renew_access_token()
            except Exception as err:  # noqa: BLE001 - refresh token expired/invalid
                if not self._password:
                    raise ZephyrAuthError(f"refresh token invalid: {err}") from err
                _LOGGER.debug(
                    "Zephyr refresh token renewal failed, falling back to password: %s",
                    err,
                )
            else:
                self._finish_auth(cog)
                return

        if not self._password:
            raise ZephyrAuthError("No refresh token or password available")

        cog = Cognito(
            COGNITO_USER_POOL_ID,
            COGNITO_APP_CLIENT_ID,
            client_secret=COGNITO_APP_CLIENT_SECRET,
            user_pool_region=AWS_REGION,
            username=self._email,
        )
        try:
            cog.authenticate(password=self._password)
        except Exception as err:  # pycognito raises various boto exceptions
            raise ZephyrAuthError(str(err)) from err
        self._finish_auth(cog)

    def _finish_auth(self, cog: Cognito) -> None:
        self._cognito = cog
        username = _jwt_claim(cog.id_token, "cognito:username")
        if username:
            self._cognito_username = username

    def _ensure_token(self) -> None:
        with self._lock:
            if self._cognito is None:
                self.authenticate()
                return
            try:
                self._cognito.check_token(renew=True)
            except Exception:  # refresh token expired -> full re-auth
                self.authenticate()

    # ------------------------------------------------- low-level AWS JSON ------
    def _aws_json(self, host: str, target: str, body: dict) -> dict:
        req = urllib.request.Request(
            f"https://{host}/",
            data=json.dumps(body).encode(),
            headers={
                "Content-Type": "application/x-amz-json-1.1",
                "X-Amz-Target": target,
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=20, context=self._ctx_aws()) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as err:
            body_text = ""
            try:
                body_text = err.read().decode(errors="replace")[:300]
            except Exception:  # noqa: BLE001
                pass
            raise ZephyrApiError(f"{target} HTTP {err.code}: {body_text}") from err
        except Exception as err:
            raise ZephyrApiError(f"{target} failed: {type(err).__name__}: {err}") from err

    def _aws_credentials(self) -> dict[str, str]:
        """Exchange the Cognito IdToken for temporary AWS credentials."""
        self._ensure_token()
        logins = {
            f"cognito-idp.{AWS_REGION}.amazonaws.com/{COGNITO_USER_POOL_ID}": self._cognito.id_token
        }
        host = f"cognito-identity.{AWS_REGION}.amazonaws.com"
        identity_id = self._aws_json(
            host,
            "AWSCognitoIdentityService.GetId",
            {"IdentityPoolId": COGNITO_IDENTITY_POOL_ID, "Logins": logins},
        )["IdentityId"]
        return self._aws_json(
            host,
            "AWSCognitoIdentityService.GetCredentialsForIdentity",
            {"IdentityId": identity_id, "Logins": logins},
        )["Credentials"]

    # ------------------------------------------------------- device list ------
    def get_devices(self) -> list[dict[str, Any]]:
        """Return the account's bound hoods: thingName, SN, modelName, MAC."""
        self._ensure_token()
        req = urllib.request.Request(
            f"{APP_API_BASE_URL}/getowndevices",
            data=b"{}",
            method="POST",
            headers={
                "Authorization": self._cognito.id_token,
                "Content-Type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=20, context=self._ctx_gemtek()) as resp:
                data = json.loads(resp.read())
        except urllib.error.HTTPError as err:
            body = ""
            try:
                body = err.read().decode(errors="replace")[:300]
            except Exception:  # noqa: BLE001
                pass
            raise ZephyrApiError(f"getowndevices HTTP {err.code}: {body}") from err
        except Exception as err:
            raise ZephyrApiError(
                f"getowndevices failed: {type(err).__name__}: {err}"
            ) from err
        return data.get("devices", [])

    def get_device_details(self, thing_name: str) -> dict[str, Any]:
        """Return a hood's static capabilities via /discoverdevice.

        Includes the authoritative per-device maxes (maxFanSpeed, maxLightLevel,
        maxGreasefilterTimer, maxCharcoalfilterTimer) plus warranty/URL metadata.
        """
        self._ensure_token()
        req = urllib.request.Request(
            f"{APP_API_BASE_URL}/discoverdevice",
            data=json.dumps({"thingName": thing_name}).encode(),
            method="POST",
            headers={
                "Authorization": self._cognito.id_token,
                "Content-Type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=20, context=self._ctx_gemtek()) as resp:
                return json.loads(resp.read())
        except Exception as err:
            raise ZephyrApiError(
                f"discoverdevice failed: {type(err).__name__}: {err}"
            ) from err

    # ------------------------------------------- SigV4 presigned WS path ------
    def _signed_ws_path(self) -> str:
        creds = self._aws_credentials()
        ak, sk, token = creds["AccessKeyId"], creds["SecretKey"], creds["SessionToken"]
        service = "iotdevicegateway"
        now = datetime.datetime.now(datetime.timezone.utc)
        amz_date = now.strftime("%Y%m%dT%H%M%SZ")
        datestamp = amz_date[:8]
        scope = f"{datestamp}/{AWS_REGION}/{service}/aws4_request"
        query = {
            "X-Amz-Algorithm": "AWS4-HMAC-SHA256",
            "X-Amz-Credential": f"{ak}/{scope}",
            "X-Amz-Date": amz_date,
            "X-Amz-SignedHeaders": "host",
        }
        canonical_qs = "&".join(
            f"{k}={urllib.parse.quote(v, safe='')}" for k, v in sorted(query.items())
        )
        canonical_request = (
            f"GET\n/mqtt\n{canonical_qs}\nhost:{IOT_ENDPOINT}\n\nhost\n"
            + hashlib.sha256(b"").hexdigest()
        )
        string_to_sign = (
            f"AWS4-HMAC-SHA256\n{amz_date}\n{scope}\n"
            + hashlib.sha256(canonical_request.encode()).hexdigest()
        )

        def _sign(key: bytes, msg: str) -> bytes:
            return hmac.new(key, msg.encode(), hashlib.sha256).digest()

        signing_key = _sign(
            _sign(_sign(_sign(("AWS4" + sk).encode(), datestamp), AWS_REGION), service),
            "aws4_request",
        )
        signature = hmac.new(signing_key, string_to_sign.encode(), hashlib.sha256).hexdigest()
        return (
            f"/mqtt?{canonical_qs}"
            f"&X-Amz-Signature={signature}"
            f"&X-Amz-Security-Token={urllib.parse.quote(token, safe='')}"
        )

    # --------------------------------------------------------------- MQTT ------
    def connect(self, on_state: Callable[[str, dict[str, Any]], None]) -> None:
        """Open the persistent MQTT connection. Blocking — call in executor."""
        self._on_state = on_state
        client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2,
            client_id="ha-zephyr-" + uuid.uuid4().hex[:10],
            transport="websockets",
        )
        client.tls_set_context(self._ctx_aws())
        client.ws_set_options(path=self._signed_ws_path())
        client.on_connect = self._on_connect
        client.on_message = self._on_message
        client.on_disconnect = self._on_disconnect
        client.connect(IOT_ENDPOINT, 443, keepalive=30)
        client.loop_start()
        self._client = client

    def watch_thing(self, thing_name: str) -> None:
        """Subscribe to a hood's shadow and request its current state."""
        self._things.add(thing_name)
        self._subscribe(thing_name)

    def _subscribe(self, thing_name: str) -> None:
        if not self._client:
            return
        for suffix in ("get/accepted", "update/accepted", "update/documents"):
            self._client.subscribe(f"$aws/things/{thing_name}/shadow/{suffix}", qos=1)
        self.request_state(thing_name)

    def request_state(self, thing_name: str) -> None:
        if self._client:
            self._client.publish(f"$aws/things/{thing_name}/shadow/get", "", qos=1)

    def set_value(self, thing_name: str, field: str, value: Any) -> None:
        """Send a control command by writing the shadow `reported` block."""
        if not self._client:
            raise ZephyrApiError("MQTT not connected")
        payload = json.dumps({"state": {"reported": {field: value}}})
        self._client.publish(f"$aws/things/{thing_name}/shadow/update", payload, qos=1)

    def disconnect(self) -> None:
        self._closing = True
        if self._client:
            self._client.loop_stop()
            self._client.disconnect()
            self._client = None

    # ------------------------------------------------------ MQTT callbacks ----
    def _on_connect(self, client, userdata, flags, reason_code, properties=None) -> None:
        _LOGGER.debug("Zephyr MQTT connected (%s)", reason_code)
        self._reconnect_delay = _RECONNECT_MIN_DELAY
        for thing in list(self._things):
            self._subscribe(thing)

    def _on_message(self, client, userdata, msg) -> None:
        try:
            doc = json.loads(msg.payload)
        except (ValueError, TypeError):
            return
        parts = msg.topic.split("/")
        thing = parts[2] if len(parts) > 2 and parts[0] == "$aws" else None
        state = doc.get("state", {})
        # get/accepted + update/accepted -> state.reported
        # update/documents              -> current.state.reported
        reported = state.get("reported") or doc.get("current", {}).get("state", {}).get("reported")
        if thing and reported and self._on_state:
            self._on_state(thing, reported)

    def _on_disconnect(self, client, userdata, *args) -> None:
        if self._closing:
            return
        # Credentials in the presigned URL expire; re-sign and reconnect, backing
        # off exponentially so a persistently unreachable broker doesn't spin.
        delay = self._reconnect_delay
        self._reconnect_delay = min(self._reconnect_delay * 2, _RECONNECT_MAX_DELAY)
        _LOGGER.debug("Zephyr MQTT disconnected; reconnecting in %ss", delay)
        threading.Timer(delay, self._reconnect, args=(client,)).start()

    def _reconnect(self, client: mqtt.Client) -> None:
        if self._closing:
            return
        try:
            client.ws_set_options(path=self._signed_ws_path())
            client.reconnect()
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning("Zephyr MQTT reconnect failed: %s", err)
