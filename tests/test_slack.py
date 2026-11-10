import hashlib
import hmac

from accounts import Account
from slack import board_message, command_response, group_code, verify_signature
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


def test_group_code():
    assert group_code("482193") == "482 193"
    assert group_code("12345678") == "1234 5678"


def test_board_is_one_table_with_every_account():
    accounts = [Account(f"App {i}", "JBSWY3DPEHPK3PXP") for i in range(60)]
    message = board_message(accounts, ["Row 9: bad"], now=1000)
    table = message["blocks"][0]
    assert table["type"] == "table"
    assert len(table["rows"]) == 60
    assert table["column_settings"][1]["align"] == "right"
    first = table["rows"][0]
    assert first[0]["elements"][0]["elements"][0] == {"type": "text", "text": "App 0", "style": {"bold": True}}
    assert first[1]["text"] == group_code(totp("JBSWY3DPEHPK3PXP", 1000))
    assert any("Row 9" in str(b) for b in message["blocks"])
    assert "Refreshes every 30 seconds" in str(message["blocks"][-1])


def test_board_empty_sheet():
    assert "No accounts" in str(board_message([], [], now=0)["blocks"])
