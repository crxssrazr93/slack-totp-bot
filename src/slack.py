"""Slack request verification and message building (pure Python, no I/O)."""

import hashlib
import hmac

from accounts import Account
from totp import totp, window_end

MAX_REQUEST_AGE_SECONDS = 60 * 5
MAX_ACCOUNT_BLOCKS = 45  # Slack allows 50 blocks per message; leave room for header/footer.
MAX_TABLE_ROWS = 100  # Slack table block limit.


def verify_signature(signing_secret: str, timestamp: str, body: str, signature: str, now: float) -> bool:
    """Check X-Slack-Signature as described in https://api.slack.com/authentication/verifying-requests-from-slack"""
    try:
        if abs(now - int(timestamp)) > MAX_REQUEST_AGE_SECONDS:
            return False
    except (TypeError, ValueError):
        return False
    base = f"v0:{timestamp}:{body}".encode()
    expected = "v0=" + hmac.new(signing_secret.encode(), base, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature or "")


def _until(ts: int) -> str:
    """Slack renders this in each viewer's own timezone."""
    return f"<!date^{ts}^{{time_secs}}|{ts}>"


def _title(account: Account) -> str:
    title = f"*{account.name}*"
    if account.username:
        title += f"  ({account.username})"
    if account.notes:
        title += f"\n_{account.notes}_"
    return title


def _problems_block(problems: list[str]) -> list[dict]:
    if not problems:
        return []
    text = ":warning: Some sheet rows were skipped:\n" + "\n".join(f"• {p}" for p in problems)
    return [{"type": "context", "elements": [{"type": "mrkdwn", "text": text[:2900]}]}]


def command_response(accounts: list[Account], problems: list[str], query: str, now: float) -> dict:
    """Ephemeral reply to /totp [query]. Only the person who ran it sees it."""
    query = query.strip().lower()
    matches = [a for a in accounts if query in a.name.lower()] if query else accounts
    if not matches:
        text = f"No account matches `{query}`." if query else "No accounts in the sheet yet."
        return {"response_type": "ephemeral", "text": text}

    blocks = []
    for account in matches[:MAX_ACCOUNT_BLOCKS]:
        code = totp(account.secret, now, account.digits, account.period, account.algorithm)
        seconds_left = window_end(now, account.period) - int(now)
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"{_title(account)}\n`{code}`  expires in {seconds_left}s"},
        })
    blocks += _problems_block(problems)
    return {"response_type": "ephemeral", "text": "TOTP codes", "blocks": blocks}


def group_code(code: str) -> str:
    """482193 -> "482 193", 12345678 -> "1234 5678"."""
    half = len(code) // 2
    return f"{code[:half]} {code[half:]}"


def board_message(accounts: list[Account], problems: list[str], now: float) -> dict:
    """The pinned live board: every account as one table row, name left, code right.

    Rewritten every 30 seconds by the cron trigger (see entry.py).
    """
    rows = []
    for account in accounts[:MAX_TABLE_ROWS]:
        code = totp(account.secret, now, account.digits, account.period, account.algorithm)
        rows.append([
            {
                "type": "rich_text",
                "elements": [{
                    "type": "rich_text_section",
                    "elements": [{"type": "text", "text": account.name, "style": {"bold": True}}],
                }],
            },
            {"type": "raw_text", "text": group_code(code)},
        ])

    if rows:
        blocks = [{
            "type": "table",
            "column_settings": [{"is_wrapped": True}, {"align": "right"}],
            "rows": rows,
        }]
    else:
        blocks = [{"type": "section", "text": {"type": "mrkdwn", "text": "No accounts in the sheet yet."}}]
    blocks += _problems_block(problems)
    blocks.append({
        "type": "context",
        "elements": [{"type": "mrkdwn", "text": f"Refreshes every 30 seconds  ·  updated {_until(int(now))}"}],
    })
    return {"text": "Shared 2FA codes", "blocks": blocks}
