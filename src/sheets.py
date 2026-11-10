"""Read the private Google Sheet with a service account (RS256 JWT signed via WebCrypto)."""

import base64
import json
import time
from urllib.parse import quote, urlencode

from js import Object, crypto
from pyodide.ffi import to_js
from workers import fetch

TOKEN_URL = "https://oauth2.googleapis.com/token"
SCOPE = "https://www.googleapis.com/auth/spreadsheets.readonly"

# Cached per isolate so most requests skip the token exchange.
_token: dict = {"value": None, "expires": 0}


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _js(obj):
    return to_js(obj, dict_converter=Object.fromEntries)


async def _sign_rs256(private_key_pem: str, message: bytes) -> bytes:
    der = base64.b64decode(
        "".join(line for line in private_key_pem.strip().splitlines() if "-----" not in line)
    )
    algorithm = _js({"name": "RSASSA-PKCS1-v1_5", "hash": "SHA-256"})
    key = await crypto.subtle.importKey("pkcs8", to_js(der), algorithm, False, _js(["sign"]))
    signature = await crypto.subtle.sign(algorithm, key, to_js(message))
    return signature.to_bytes()


async def _access_token(service_account: dict) -> str:
    now = int(time.time())
    if _token["value"] and _token["expires"] - 60 > now:
        return _token["value"]

    header = _b64url(json.dumps({"alg": "RS256", "typ": "JWT"}).encode())
    claims = _b64url(json.dumps({
        "iss": service_account["client_email"],
        "scope": SCOPE,
        "aud": TOKEN_URL,
        "iat": now,
        "exp": now + 3600,
    }).encode())
    unsigned = f"{header}.{claims}"
    signature = _b64url(await _sign_rs256(service_account["private_key"], unsigned.encode()))

    response = await fetch(
        TOKEN_URL,
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        body=urlencode({
            "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
            "assertion": f"{unsigned}.{signature}",
        }),
    )
    data = json.loads(await response.text())
    if "access_token" not in data:
        raise RuntimeError(f"Google token exchange failed: {data}")
    _token["value"] = data["access_token"]
    _token["expires"] = now + int(data.get("expires_in", 3600))
    return _token["value"]


async def read_sheet(service_account_json: str, sheet_id: str, sheet_range: str) -> list[list[str]]:
    token = await _access_token(json.loads(service_account_json))
    url = (
        f"https://sheets.googleapis.com/v4/spreadsheets/{sheet_id}/values/"
        f"{quote(sheet_range, safe='')}?valueRenderOption=FORMATTED_VALUE"
    )
    response = await fetch(url, headers={"Authorization": f"Bearer {token}"})
    data = json.loads(await response.text())
    if "error" in data:
        raise RuntimeError(f"Google Sheets API error: {data['error'].get('message', data['error'])}")
    return data.get("values", [])
