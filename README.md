# Slack TOTP Bot

A small Slack bot for teams that share accounts protected by 2FA. It reads TOTP secrets from a private Google Sheet and makes the current codes available in one private Slack channel. Anyone you add to that channel can get a code. Anyone you remove loses access immediately.

It runs as a Python [Cloudflare Worker](https://developers.cloudflare.com/workers/languages/python/), so there is no server to maintain, and it fits in the Workers free tier for typical team sizes.

## What your team gets

1. **`/totp`** in the private channel replies with every code, visible only to the person who asked (Slack "ephemeral" message). `/totp github` filters by name. This is always exact, because the code is computed at the moment you ask.
2. **A live board**: one pinned message listing every account, name on the left and code on the right, rewritten every 30 seconds. Nobody has to ask for anything.

   ```
   GitHub        482 193
   AWS           731 046
   Notion        905 274
   Refreshes every 30 seconds
   ```

Codes are never stored. They are computed on demand from the secrets in your sheet (TOTP codes are just a function of the secret and the clock).

## How it works

```
 Google Sheet (private, shared read only with one service account)
        │  Sheets API, RS256 service account token
        ▼
 Cloudflare Worker (Python)
   ├─ POST /slack/commands  ◄── Slack slash command /totp (signature verified)
   └─ cron every minute     ──► chat.update on the pinned board, twice (every 30 s)
        │
        ▼
 Private Slack channel
```

| File | Purpose |
| --- | --- |
| `src/entry.py` | Worker handlers: slash command and cron |
| `src/totp.py` | RFC 6238 TOTP, standard library only |
| `src/accounts.py` | Parses and validates the sheet rows |
| `src/slack.py` | Slack signature check and message layout |
| `src/sheets.py` | Google service account auth and Sheets read |
| `slack-app-manifest.yml` | One paste Slack app setup |
| `examples/sheet-template.csv` | Starter sheet to import |

## The sheet

One tab named `TOTP`. Row 1 is the header. Columns are matched by name, so order does not matter.

| Column | Required | Example | Notes |
| --- | --- | --- | --- |
| `name` | yes | `GitHub (ops)` | What people type after `/totp` |
| `secret` | yes | `JBSWY3DPEHPK3PXP` | Base32 setup key. Spaces and lowercase are fine |
| `username` | no | `ops@example.com` | Which login this code is for |
| `digits` | no | `6` | Default 6 |
| `period` | no | `30` | Seconds, default 30 |
| `algorithm` | no | `SHA1` | `SHA1` (default), `SHA256` or `SHA512` |
| `enabled` | no | `TRUE` | `FALSE` hides the row without deleting it |
| `notes` | no | `Billing admin` | Shown under the name |

Bad rows are skipped and listed in a small warning, so one typo never takes the whole bot down.

**Getting the secret:** when a site shows a QR code for 2FA setup, click "can't scan?" or "enter key manually" to see the base32 key. If you only have an `otpauth://totp/...?secret=XXXX` link, the value after `secret=` is what goes in the sheet.

## Setup

Allow about 30 minutes. The full walkthrough is in **[docs/setup.md](docs/setup.md)**:

1. Google: create a service account, enable the Sheets API, share the sheet with it as Viewer.
2. Slack: create the app from `slack-app-manifest.yml`, install it, invite it to the private channel.
3. Cloudflare: create a KV namespace, set three secrets, deploy with `uv run pywrangler deploy`.
4. Point the Slack slash command at your Worker URL.

## More

* [docs/setup.md](docs/setup.md) for the step by step guide and troubleshooting
* [docs/security.md](docs/security.md) for what this protects, what it does not, and how to harden it
* [docs/alternatives.md](docs/alternatives.md) for using 1Password, Bitwarden, Vault, Doppler, Infisical, cloud secret managers or plain Worker secrets instead of a Google Sheet
* [AGENTS.md](AGENTS.md) for AI coding agents helping someone set this up

## Development

```bash
uv run --no-project --with pytest pytest -q   # unit tests, includes RFC 6238 vectors
cp .dev.vars.example .dev.vars                # fill in real values
uv run pywrangler dev --test-scheduled        # local Worker on http://localhost:8787
```

## License

MIT
