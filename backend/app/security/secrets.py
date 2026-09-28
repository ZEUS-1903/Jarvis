"""Detect text that looks like a secret (passwords, card numbers, API keys...).

Used to refuse storing secrets in memory and to keep them out of logs.
Heuristic: it errs on the side of flagging, and it can't catch everything.
"""
import re

_SECRETS = [
    re.compile(r"\b(password|passcode|passwd|pin code|cvv|cvc|security code|"
               r"social security|ssn|routing number|account number|api[ _-]?key|secret key)\b",
               re.IGNORECASE),
    re.compile(r"\b(?:\d[ -]?){12,19}\b"),                     # card/account-number-like digit runs
    re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),                      # US SSN format
    re.compile(r"\b(sk|pk|ghp|xox[bp])[-_][A-Za-z0-9_-]{16,}"),  # common API token shapes
]


def looks_secret(text: str) -> bool:
    return any(p.search(text) for p in _SECRETS)


def redact(value: object) -> object:
    """For logs: replace anything secret-looking with a placeholder."""
    return "[redacted: looks like a secret]" if looks_secret(str(value)) else value
