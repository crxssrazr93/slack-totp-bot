# Notes for AI agents

You are probably helping someone deploy this bot. Read `README.md` and `docs/setup.md` first. This file covers what is not obvious.

## Ground rules

* **Never ask the user to paste TOTP secrets, the service account JSON, the Slack bot token or the signing secret into the chat.** Have them run `uv run pywrangler secret put NAME` themselves (suggest `! <command>` if your harness supports running commands in the user's shell) so values never enter your context or logs.
* Never commit `.dev.vars`, any `*.json` key file, or a filled in CSV of real secrets. `.gitignore` covers the common names; check `git status` before committing anyway.
* The steps in Google Cloud Console, Slack app settings and the Slack client are clicks the user must do. Walk them through `docs/setup.md` one step at a time and confirm each value before moving on.

## Layout

* `src/entry.py` is the only file that touches the Workers runtime (`workers`, `js`, `self.env`). `src/sheets.py` uses WebCrypto via the Pyodide FFI.
* `src/totp.py`, `src/accounts.py` and `src/slack.py` are pure Python and fully unit tested. Keep runtime imports out of them so tests run on plain CPython.
* There are no third party runtime dependencies. Keep it that way unless a dependency is unavoidable; Python Workers support only Pyodide compatible packages.

## Commands

```bash
uv run --no-project --with pytest pytest -q    # tests
uv run pywrangler dev --test-scheduled         # local Worker, needs .dev.vars
uv run pywrangler deploy                       # deploy
npx wrangler tail                              # live logs
```

Locally, trigger the cron with:

```bash
curl -X POST "http://localhost:8787/cdn-cgi/local/explorer/api/local/scheduled?worker=slack-totp-bot" \
  -H 'Content-Type: application/json' -d '{"cron":"* * * * *"}'
```

To send a signed slash command to the local Worker (signing secret `testsecret` in `.dev.vars`):

```bash
TS=$(date +%s); BODY='command=%2Ftotp&text=&channel_id=YOUR_CHANNEL_ID'
SIG="v0=$(printf 'v0:%s:%s' "$TS" "$BODY" | openssl dgst -sha256 -hmac testsecret | awk '{print $2}')"
curl -X POST http://localhost:8787/slack/commands -H "X-Slack-Request-Timestamp: $TS" -H "X-Slack-Signature: $SIG" -d "$BODY"
```

## Gotchas found while building this

* In `.dev.vars`, wrap the service account JSON in **single quotes** with the JSON exactly as Google produced it. Double quoting with escaped inner quotes is not unescaped and fails with `Expecting property name enclosed in double quotes`.
* `.dev.vars` changes are not always picked up by a running `pywrangler dev`; restart it.
* With the old `__scheduled` URL, the request just hits the fetch handler (404). Use the local explorer route above.
* Google returns `invalid_grant: account not found` for a well formed JWT from an unknown or deleted service account, and a signature error for a bad key. That distinction helps when debugging step 2 of setup.
* Slack must get a reply within 3 seconds. The Google token is cached per isolate, so only the first request after a cold start pays for the token exchange.
* Cron Triggers run at most once per minute while codes rotate every 30 seconds, so `scheduled` updates the board, `asyncio.sleep`s to the next 30 second boundary (plus 1 s), and updates again. Sleeping is wall time, not CPU time, so it is cheap. Accounts with a period other than 30 still show their correct current code, just refreshed on the 30 second rhythm.
* The board uses a Slack `table` block (max 100 rows, 10,000 characters). Names are bold `rich_text` cells, codes are right aligned `raw_text` grouped like `482 193`.

## Changing the secret source

See `docs/alternatives.md`. Only `Default._accounts` in `src/entry.py` needs to change, as long as it returns rows with a header row first.
