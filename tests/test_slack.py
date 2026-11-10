import hashlib
import hmac

from accounts import Account
from slack import board_message, command_response, verify_signature
from totp import totp

SECRET = "8f742231b10e8888abcd99yyyzzz85a5"


def sign(ts, body):
    return "v0=" + hmac.new(SECRET.encode(), f"v0:{ts}:{body}".encode(), hashlib.sha256).hexdigest()


def test_signature_valid_and_invalid():
    body = "command=%2Ftotp&text=github"
    assert verify_signature(SECRET, "1000", body, sign(1000, body), now=1010)
    assert not verify_signature(SECRET, "1000", body + "x", sign(1000, body), now=1010)
    assert not verify_signature(SECRET, "1000", body, sign(1000, body), now=1000 + 301)  # replay
    assert not verify_signature(SECRET, None, body, None, now=1000)


ACCOUNTS = [Account("GitHub", "JBSWY3DPEHPK3PXP", "ops@x.com"), Account("AWS", "GEZDGNBVGY3TQOJQ")]


def test_command_filters_by_name_and_is_ephemeral():
    reply = command_response(ACCOUNTS, [], "git", now=1000)
    assert reply["response_type"] == "ephemeral"
    assert len(reply["blocks"]) == 1
    assert totp("JBSWY3DPEHPK3PXP", 1000) in reply["blocks"][0]["text"]["text"]
    assert "expires in 20s" in reply["blocks"][0]["text"]["text"]


def test_command_no_match():
    assert "No account matches" in command_response(ACCOUNTS, [], "nope", now=0)["text"]


def test_board_shows_current_and_next_code():
    message = board_message(ACCOUNTS, ["Row 9: bad"], now=1000)
    text = message["blocks"][1]["text"]["text"]
    assert f"Now: `{totp('JBSWY3DPEHPK3PXP', 1000)}`" in text
    assert f"Next: `{totp('JBSWY3DPEHPK3PXP', 1020)}`" in text
    assert any("Row 9" in str(b) for b in message["blocks"])
