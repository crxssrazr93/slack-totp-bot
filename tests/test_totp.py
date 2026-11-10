import base64

import pytest

from totp import decode_secret, totp, window_end

# RFC 6238 Appendix B test vectors (8 digits).
SHA1_KEY = base64.b32encode(b"12345678901234567890").decode()
SHA256_KEY = base64.b32encode(b"12345678901234567890123456789012").decode()
SHA512_KEY = base64.b32encode(b"1234567890123456789012345678901234567890123456789012345678901234").decode()


@pytest.mark.parametrize("at,sha1,sha256,sha512", [
    (59, "94287082", "46119246", "90693936"),
    (1111111109, "07081804", "68084774", "25091201"),
    (1111111111, "14050471", "67062674", "99943326"),
    (1234567890, "89005924", "91819424", "93441116"),
    (2000000000, "69279037", "90698825", "38618901"),
    (20000000000, "65353130", "77737706", "47863826"),
])
def test_rfc6238_vectors(at, sha1, sha256, sha512):
    assert totp(SHA1_KEY, at, 8, 30, "SHA1") == sha1
    assert totp(SHA256_KEY, at, 8, 30, "SHA256") == sha256
    assert totp(SHA512_KEY, at, 8, 30, "SHA512") == sha512


def test_secret_formatting_is_forgiving():
    assert decode_secret("jbsw y3dp ehpk 3pxp") == decode_secret("JBSWY3DPEHPK3PXP")


def test_window_end():
    assert window_end(59, 30) == 60
    assert window_end(60, 30) == 90
