from accounts import parse_rows

HEADER = ["Name", "Secret", "Username", "Digits", "Period", "Algorithm", "Enabled", "Notes"]


def test_parses_defaults_and_skips_disabled_and_blank():
    accounts, problems = parse_rows([
        HEADER,
        ["GitHub", "JBSWY3DPEHPK3PXP", "ops@x.com"],
        ["Old", "JBSWY3DPEHPK3PXP", "", "", "", "", "FALSE"],
        [],
        ["AWS", "JBSWY3DPEHPK3PXP", "", "8", "60", "sha256", "TRUE"],
    ])
    assert problems == []
    assert [a.name for a in accounts] == ["GitHub", "AWS"]
    assert (accounts[0].digits, accounts[0].period, accounts[0].algorithm) == (6, 30, "SHA1")
    assert (accounts[1].digits, accounts[1].period, accounts[1].algorithm) == (8, 60, "SHA256")


def test_bad_rows_are_reported_not_fatal():
    accounts, problems = parse_rows([
        HEADER,
        ["NoSecret", ""],
        ["BadSecret", "not base32!!"],
        ["BadAlgo", "JBSWY3DPEHPK3PXP", "", "", "", "MD5"],
        ["Good", "JBSWY3DPEHPK3PXP"],
    ])
    assert [a.name for a in accounts] == ["Good"]
    assert len(problems) == 3
    assert problems[0].startswith("Row 2")


def test_missing_header_columns():
    accounts, problems = parse_rows([["title", "key"]])
    assert accounts == [] and "name, secret" in problems[0]
