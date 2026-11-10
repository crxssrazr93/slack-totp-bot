# Security notes

Sharing 2FA codes is a trade off. It is better than texting codes around or keeping one person on call to read their phone, but it does change what 2FA protects you from. Read this before rolling it out.

## The model

* **Who can get a code:** members of the one private Slack channel. Nothing else. Slack membership is your access control list.
* **Who can see the secrets:** you (sheet owner), the service account, and the running Worker. Channel members only ever see 6 digit codes that expire within seconds.
* **What an attacker needs to log in to a shared account:** the account password plus access to the channel (or to one of the systems below). Keep passwords somewhere else, such as a team password manager. **Never put passwords or recovery codes in the same sheet.** If both factors live in one place, you effectively have one factor.

## Things that hold the keys (protect all of them)

| Asset | Why it matters | Hardening |
| --- | --- | --- |
| The Google Sheet | Holds every TOTP secret | Share only with the service account (Viewer). Turn on 2FA for your Google account. Check Share settings now and then. Do not publish to web |
| Service account JSON key | Can read the sheet from anywhere | Lives only as a Cloudflare secret. Delete the local download. Rotate yearly (create new key, update secret, delete old key) |
| Cloudflare account | Can read Worker secrets indirectly by deploying new code | Turn on 2FA. Limit who has Workers access |
| Slack bot token | Can post in channels it is in | Stored as a Cloudflare secret. The bot only has `commands`, `chat:write`, `pins:write` |
| Slack channel membership | Gets codes | Keep it small. Review members when people change roles |

## The live board vs. slash command only

The board posts codes into channel history. The codes are overwritten every 30 seconds, and old codes are useless once they expire, so the practical risk is low. However:

* Slack workspace exports and compliance tools (Enterprise Grid, Discovery API) may retain edited message content.
* Anyone who can read the channel later can see that a code existed and when.

If that matters to you, remove the `[triggers]` cron from `wrangler.toml` and use `/totp` only. Its replies are ephemeral: shown to one person, never stored in channel history.

## What this code does to stay safe

* Every request is checked against Slack's HMAC signature with a 5 minute replay window, and requests from any other channel are refused.
* The service account uses the `spreadsheets.readonly` scope, so even a leaked token cannot edit your sheet.
* Codes are computed in memory and never written anywhere. The KV namespace stores only the Slack message timestamp of the board.
* No third party Python packages. TOTP, HMAC and JWT code are standard library or WebCrypto, so there is nothing to supply chain attack.

## Audit trail

The Worker logs are thin by design (no codes or secrets are printed). If you want a record of who requested codes, add a `print(form.get("user_id"), form.get("text"))` in `src/entry.py` and view it with `npx wrangler tail` or Workers Logs.
