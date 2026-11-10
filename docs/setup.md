# Setup guide

You need: a Google account, a Slack workspace where you can install apps, a free Cloudflare account, and on your machine [uv](https://docs.astral.sh/uv/) plus Node.js 20 or newer.

```bash
git clone https://github.com/crxssrazr93/slack-totp-bot.git
cd slack-totp-bot
```

Keep a scratch note open. You will collect five values along the way:

| Value | Where it comes from | Goes into |
| --- | --- | --- |
| Sheet ID | Step 1 | `wrangler.toml` `SHEET_ID` |
| Service account JSON key | Step 2 | Worker secret `GOOGLE_SERVICE_ACCOUNT_JSON` |
| Channel ID | Step 3 | `wrangler.toml` `SLACK_CHANNEL_ID` |
| Bot token (`xoxb-...`) | Step 4 | Worker secret `SLACK_BOT_TOKEN` |
| Signing secret | Step 4 | Worker secret `SLACK_SIGNING_SECRET` |

## 1. Create the Google Sheet

1. Create a new Google Sheet. Rename the first tab to `TOTP` (exactly).
2. Import `examples/sheet-template.csv` (File, Import, Upload, "Replace current sheet") or type the header row yourself: `name, secret, username, digits, period, algorithm, enabled, notes`.
3. Replace the example rows with your real accounts. The example secrets are public test values, so delete them.
4. Copy the Sheet ID from the URL: `https://docs.google.com/spreadsheets/d/`**`THIS_PART`**`/edit`.

Format the `secret` column as plain text (Format, Number, Plain text) so Sheets never reformats a key.

## 2. Create a Google service account (read only access to that one sheet)

1. Open [Google Cloud Console](https://console.cloud.google.com/) and create a project (for example `slack-totp-bot`).
2. APIs and Services, Library: search for **Google Sheets API** and click Enable.
3. IAM and Admin, Service Accounts, Create service account. Name it `totp-bot`. Skip the optional role and user steps (it needs no project roles).
4. Open the new service account, Keys tab, Add key, Create new key, JSON. A `.json` file downloads. Treat it like a password.
5. Copy the service account email (looks like `totp-bot@your-project.iam.gserviceaccount.com`).
6. Back in your sheet: Share, paste that email, set it to **Viewer**, untick "Notify people", Share.

Your sheet is now shared with you and with this robot account only. Nobody else can open it.

If your organisation blocks key creation (policy `iam.disableServiceAccountKeyCreation`), ask a Workspace admin for an exception for this project, or use one of the options in [alternatives.md](alternatives.md).

## 3. Create the private Slack channel

1. Create a private channel, for example `#shared-2fa`. Add the people who need codes.
2. Open the channel name, scroll to the bottom of the About tab, and copy the **Channel ID** (starts with `C` or `G`).

## 4. Create the Slack app

1. Go to [api.slack.com/apps](https://api.slack.com/apps), Create New App, **From a manifest**, choose your workspace.
2. Paste the contents of `slack-app-manifest.yml`. Leave the placeholder URL for now, you will fix it in step 6.
3. Create, then **Install to Workspace** and allow.
4. OAuth and Permissions: copy the **Bot User OAuth Token** (`xoxb-...`).
5. Basic Information, App Credentials: copy the **Signing Secret**.
6. In Slack, inside your private channel, type `/invite @totp-bot`. The bot can only post to private channels it has been invited to.

## 5. Deploy the Worker

```bash
npx wrangler login                               # opens a browser, approve access
npx wrangler kv namespace create BOARD           # prints an id
```

Edit `wrangler.toml`:

* paste the KV id into `[[kv_namespaces]]` `id`
* set `SHEET_ID` and `SLACK_CHANNEL_ID`
* leave `SHEET_RANGE = "TOTP!A:Z"` unless you named the tab differently

Set the three secrets (each command prompts for the value, or reads it from a pipe):

```bash
uv run pywrangler secret put SLACK_BOT_TOKEN
uv run pywrangler secret put SLACK_SIGNING_SECRET
uv run pywrangler secret put GOOGLE_SERVICE_ACCOUNT_JSON < path/to/downloaded-key.json
```

Then delete the downloaded JSON key from your machine (or move it into your password manager). The only copy the bot needs is now an encrypted Cloudflare secret.

Deploy:

```bash
uv run pywrangler deploy
```

The output ends with your URL, for example `https://slack-totp-bot.your-subdomain.workers.dev`.

## 6. Connect Slack to the Worker

1. In your Slack app settings, Slash Commands, edit `/totp`.
2. Set Request URL to `https://slack-totp-bot.your-subdomain.workers.dev/slack/commands` and Save.
3. If Slack asks you to reinstall the app, do it.

## 7. Check it works

* In the private channel, type `/totp`. You should see every code, with "Only visible to you".
* Within a minute the bot posts and pins the live board. After that the same message is edited every minute.
* Compare one code with your authenticator app. They should match.
* Type `/totp` in any other channel. The bot should refuse.

## Day to day

* **Add an account:** add a row to the sheet. It appears on the next board refresh (within a minute) and immediately in `/totp`.
* **Remove access for a person:** remove them from the Slack channel. Then, since they saw the codes but never the secrets, nothing else is needed unless they also know the account passwords.
* **Retire an account:** set `enabled` to `FALSE` or delete the row.
* **Do not want the board?** Delete the `[triggers]` block from `wrangler.toml` and redeploy. `/totp` keeps working. See [security.md](security.md) for why you might choose that.

## Troubleshooting

Live logs: `npx wrangler tail`.

| Symptom | Likely cause |
| --- | --- |
| `/totp failed with the error "dispatch_failed"` | Request URL wrong, or the Worker is not deployed. Open the URL in a browser: a `Not found` page means the Worker is up and the path is what needs fixing |
| `Invalid signature` in logs | `SLACK_SIGNING_SECRET` is wrong (it is not the bot token, and not the client secret) |
| "only works in the shared 2FA channel" in the right channel | `SLACK_CHANNEL_ID` does not match, copy it again from the channel About tab |
| "Could not read the codes sheet" | Look in `wrangler tail`. `PERMISSION_DENIED`: sheet not shared with the service account email. `Unable to parse range`: tab is not called `TOTP`. `API has not been used`: enable the Sheets API in the same project as the key |
| Board never appears | Bot not invited to the channel (`not_in_channel`), or the KV id is still the placeholder |
| Codes do not match the authenticator app | Wrong secret, or the account uses non default digits, period or algorithm. Check the site's setup page or the `otpauth://` link parameters |
| `Exceeded CPU time limit` | Rare on Workers Free (10 ms CPU per request) with very large sheets. The Workers Paid plan raises the limit |
