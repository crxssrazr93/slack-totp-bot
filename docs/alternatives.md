# Alternatives to Google Sheets

Google Sheets is the default because it is free and anyone can edit it. You may want something stricter, or you may already pay for a secrets manager. Everything below plugs into the same bot.

## How to swap the source

The bot only touches the secret store in one method, `Default._accounts` in `src/entry.py`. It needs a list of rows where row 1 is the header, exactly like the sheet:

```python
[
    ["name", "secret", "username"],
    ["GitHub (ops)", "JBSWY3DPEHPK3PXP", "ops@example.com"],
]
```

The easiest swap for almost every manager: store **one secret** called `TOTP_ACCOUNTS` whose value is CSV text in the same format as `examples/sheet-template.csv`, then turn it into rows:

```python
import csv, io

def rows_from_csv(text: str) -> list[list[str]]:
    return list(csv.reader(io.StringIO(text)))
```

Then in `_accounts` replace the `read_sheet(...)` call with something that fetches that CSV text (examples below) and `return parse_rows(rows_from_csv(text))`. Everything else (validation, Slack, the board) stays the same. You can delete `src/sheets.py` and the `GOOGLE_*` and `SHEET_*` settings.

## Comparison

| Option | Cost | Edit experience | Works from a Worker | Secrets leave the store? | Best when |
| --- | --- | --- | --- | --- | --- |
| Google Sheets (default) | Free | Spreadsheet, anyone can add rows | Yes (this repo) | Yes, read by the Worker | Non technical owner, quick start |
| Cloudflare Worker secret | Free | CLI only (`secret put`) | Native | Yes | Few accounts, rarely changes, fewest moving parts |
| Cloudflare Secrets Store | Free tier | Dashboard or CLI | Native binding | Yes | Same as above, with a dashboard and account wide reuse |
| HashiCorp Vault / OpenBao, TOTP engine | Free self hosted, or HCP | CLI, UI, API | Yes, plain HTTPS | **No**, Vault generates the code | Strongest option if you already run Vault |
| 1Password (Connect server) | Business plan | 1Password apps, TOTP is native | Yes, plain HTTPS | Optional, Connect can return the code | Team already uses 1Password |
| Doppler | Free tier | Web dashboard | Yes, one GET | Yes | Want a dashboard with audit log, little setup |
| Infisical | Free tier or self hosted | Web dashboard | Yes, two calls | Yes | Open source preference |
| Google Secret Manager | Pennies | Console or CLI | Yes, same auth as this repo | Yes | Already on GCP, want IAM and audit logs |
| AWS Secrets Manager | About $0.40 per secret per month | Console or CLI | Possible, needs SigV4 signing | Yes | Already on AWS |
| Azure Key Vault | Pennies | Portal or CLI | Yes, OAuth client credentials | Yes | Already on Azure |
| Bitwarden | Teams plan | Bitwarden apps, TOTP is native | Not a good fit | n/a | See "Maybe you do not need the bot" |

## Option details

### Cloudflare Worker secret (simplest possible)

No external service at all. Put the CSV into a secret:

```bash
uv run pywrangler secret put TOTP_ACCOUNTS < accounts.csv && rm accounts.csv
```

```python
async def _accounts(self):
    return parse_rows(rows_from_csv(self.env.TOTP_ACCOUNTS))
```

Trade off: to change an account you re run `secret put` with the whole file. Nobody can view the value afterwards, including you, so keep the master copy in a password manager.

### Cloudflare Secrets Store

Same idea, but the secret lives in an account level store you can manage in the dashboard. Add a binding in `wrangler.toml`:

```toml
[[secrets_store_secrets]]
binding = "TOTP_ACCOUNTS"
store_id = "YOUR_STORE_ID"
secret_name = "totp-accounts"
```

```python
text = await self.env.TOTP_ACCOUNTS.get()
```

### HashiCorp Vault or OpenBao with the TOTP secrets engine

This is the only option where **the Worker never sees the secrets**. Vault stores them and returns only the current code.

```bash
vault secrets enable totp
vault write totp/keys/github-ops url="otpauth://totp/GitHub:ops@example.com?secret=JBSWY3DPEHPK3PXP&issuer=GitHub"
```

The Worker calls `GET https://vault.example.com/v1/totp/code/github-ops` with header `X-Vault-Token`, and gets `{"data": {"code": "123456"}}`. Because codes come back ready made, you would replace the `totp(...)` calls in `src/slack.py` with these API results, which is a bigger change than the CSV swap. Give the Worker a token whose policy allows only `read` on `totp/code/*`. Vault must be reachable over HTTPS from Cloudflare (Cloudflare Tunnel works well for this).

### 1Password

1Password stores TOTP natively in any login item ("One Time Password" field). To read it from the Worker, run a [1Password Connect](https://developer.1password.com/docs/connect/) server (a small container, Cloudflare Tunnel can expose it) and call:

```
GET https://connect.example.com/v1/vaults/{vault_id}/items/{item_id}
Authorization: Bearer <connect token>
```

The OTP field in the response carries the `otpauth://` URI, and Connect also includes the current code in that field. Either use that code directly or take `secret=` from the URI and keep using this repo's `totp.py`. 1Password Service Accounts are the newer alternative, but they are used through the CLI and SDKs rather than plain HTTP, which makes them awkward inside a Worker.

### Doppler

Create a project, add a secret `TOTP_ACCOUNTS` with the CSV as its value, create a read only **service token** for that config, and store it as the Worker secret `DOPPLER_TOKEN`.

```python
response = await fetch(
    "https://api.doppler.com/v3/configs/config/secrets/download?format=json",
    headers={"Authorization": f"Bearer {self.env.DOPPLER_TOKEN}"},
)
text = json.loads(await response.text())["TOTP_ACCOUNTS"]
```

### Infisical

Create a Machine Identity with Universal Auth and read only access to one environment. Store its client ID and secret as Worker secrets. The Worker logs in (`POST /api/v1/auth/universal-auth/login`) to get an access token, then reads the secret through the raw secrets endpoint. Check the current API version in the [Infisical API docs](https://infisical.com/docs/api-reference/overview/introduction) since the secrets endpoints have been versioned more than once. Cache the access token in a module global like `src/sheets.py` does for Google.

### Google Secret Manager

The smallest change from the default, because the auth code is already here.

1. Create a secret `totp-accounts` holding the CSV.
2. Grant the existing service account the **Secret Manager Secret Accessor** role on that secret only.
3. In `src/sheets.py` change `SCOPE` to `https://www.googleapis.com/auth/cloud-platform` and fetch
   `https://secretmanager.googleapis.com/v1/projects/PROJECT/secrets/totp-accounts/versions/latest:access`.
   The CSV is base64 encoded at `payload.data` in the response.

You gain IAM, versioning, and Cloud Audit Logs of every read.

### AWS Secrets Manager and Azure Key Vault

Both work over HTTPS. AWS requires SigV4 request signing (use a small signing helper, or put an API Gateway or Lambda in front). Azure uses an OAuth client credentials token for an app registration, then `GET https://VAULT.vault.azure.net/secrets/totp-accounts?api-version=7.4`. Pick these only if your team already lives in that cloud.

## Maybe you do not need the bot

If your team already pays for **1Password Business/Teams** or **Bitwarden Teams/Enterprise**, both can store the TOTP key on a shared item and show the live code to everyone the vault or collection is shared with, inside their normal apps. Access control is the vault membership instead of a Slack channel. That is usually the more secure answer, because the password and the code stay inside one audited tool. The bot is most useful when the people who need codes live in Slack and do not have seats in a password manager.
