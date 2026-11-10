"""RFC 6238 TOTP using only the Python standard library."""

import base64
import hashlib
import hmac
import struct

ALGORITHMS = {"SHA1": hashlib.sha1, "SHA256": hashlib.sha256, "SHA512": hashlib.sha512}


def decode_secret(secret: str) -> bytes:
    """Decode a base32 secret as shown by most sites (spaces and lowercase allowed)."""
    cleaned = secret.replace(" ", "").replace("-", "").upper()
    cleaned += "=" * (-len(cleaned) % 8)
    return base64.b32decode(cleaned)


def totp(secret: str, at: float, digits: int = 6, period: int = 30, algorithm: str = "SHA1") -> str:
    key = decode_secret(secret)
    counter = int(at // period)
    mac = hmac.new(key, struct.pack(">Q", counter), ALGORITHMS[algorithm]).digest()
    offset = mac[-1] & 0x0F
    code = (struct.unpack(">I", mac[offset : offset + 4])[0] & 0x7FFFFFFF) % (10**digits)
    return str(code).zfill(digits)


def window_end(at: float, period: int = 30) -> int:
    """Unix time at which the code valid at `at` expires."""
    return (int(at // period) + 1) * period
