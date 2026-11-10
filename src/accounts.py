"""Turn raw Google Sheets rows into validated TOTP accounts."""

from dataclasses import dataclass

from totp import ALGORITHMS, decode_secret

DISABLED_VALUES = {"false", "no", "0", "n", "off"}


@dataclass
class Account:
    name: str
    secret: str
    username: str = ""
    digits: int = 6
    period: int = 30
    algorithm: str = "SHA1"
    notes: str = ""


def parse_rows(values: list[list[str]]) -> tuple[list[Account], list[str]]:
    """Parse the sheet. Row 1 is the header. Returns (accounts, problems).

    Columns are matched by header name (case insensitive), so their order
    does not matter. Required: name, secret. Optional: username, digits,
    period, algorithm, enabled, notes.
    """
    if not values:
        return [], ["Sheet is empty (expected a header row)."]

    header = [h.strip().lower() for h in values[0]]
    missing = {"name", "secret"} - set(header)
    if missing:
        return [], [f"Header row is missing column(s): {', '.join(sorted(missing))}."]

    accounts, problems = [], []
    for row_number, row in enumerate(values[1:], start=2):
        cells = {header[i]: (row[i].strip() if i < len(row) else "") for i in range(len(header))}
        if not any(cells.values()):
            continue
        if cells.get("enabled", "").lower() in DISABLED_VALUES:
            continue
        name, secret = cells.get("name", ""), cells.get("secret", "")
        if not name or not secret:
            problems.append(f"Row {row_number}: name and secret are both required.")
            continue
        try:
            account = Account(
                name=name,
                secret=secret,
                username=cells.get("username", ""),
                digits=int(cells.get("digits") or 6),
                period=int(cells.get("period") or 30),
                algorithm=(cells.get("algorithm") or "SHA1").upper(),
                notes=cells.get("notes", ""),
            )
            decode_secret(account.secret)
            if account.algorithm not in ALGORITHMS:
                raise ValueError(f"unknown algorithm {account.algorithm}")
            if not 6 <= account.digits <= 10 or account.period <= 0:
                raise ValueError("digits must be 6 to 10 and period must be positive")
        except Exception as error:  # noqa: BLE001  (report any bad row, never crash)
            problems.append(f"Row {row_number} ({name}): {error}")
            continue
        accounts.append(account)
    return accounts, problems
