"""Read-only Gmail access. Everything here returns plain dicts for the tools."""
import base64
import html
import re
from email.utils import parseaddr, parsedate_to_datetime
from zoneinfo import ZoneInfo

MAX_BODY_CHARS = 4000  # a long newsletter shouldn't flood the model's context


def search(service, query: str, max_results: int, tz: str) -> list[dict]:
    """Gmail search syntax, e.g. 'is:unread newer_than:1d', 'from:alex'."""
    resp = service.users().messages().list(userId="me", q=query, maxResults=max_results).execute()
    results = []
    for ref in resp.get("messages", []):
        # format="metadata": headers + snippet only, much smaller than full bodies.
        msg = service.users().messages().get(
            userId="me", id=ref["id"], format="metadata",
            metadataHeaders=["From", "Subject", "Date"]).execute()
        headers = _headers(msg)
        results.append({
            "id": msg["id"],
            "from": _sender(headers.get("from", "")),
            "subject": headers.get("subject", "(no subject)"),
            "date": _local_date(headers.get("date", ""), tz),
            "snippet": html.unescape(msg.get("snippet", "")),
            "unread": "UNREAD" in msg.get("labelIds", []),
            "important": "IMPORTANT" in msg.get("labelIds", []),
        })
    return results


def read(service, message_id: str, tz: str) -> dict:
    msg = service.users().messages().get(userId="me", id=message_id, format="full").execute()
    headers = _headers(msg)
    body = _body_text(msg.get("payload", {}))
    truncated = len(body) > MAX_BODY_CHARS
    return {
        "id": msg["id"],
        "from": _sender(headers.get("from", "")),
        "to": headers.get("to", ""),
        "subject": headers.get("subject", "(no subject)"),
        "date": _local_date(headers.get("date", ""), tz),
        "body": body[:MAX_BODY_CHARS] + (" [...truncated]" if truncated else ""),
    }


def _headers(msg: dict) -> dict[str, str]:
    return {h["name"].lower(): h["value"] for h in msg.get("payload", {}).get("headers", [])}


def _sender(raw: str) -> str:
    name, address = parseaddr(raw)
    return f"{name} <{address}>" if name else address


def _local_date(raw: str, tz: str) -> str:
    try:
        return parsedate_to_datetime(raw).astimezone(ZoneInfo(tz)).strftime("%a %b %-d, %-I:%M %p")
    except (TypeError, ValueError):
        return raw


def _body_text(payload: dict) -> str:
    """Emails are MIME trees (multipart/alternative, attachments...). Prefer the
    text/plain part; fall back to text/html with tags stripped."""
    plain, html_parts = [], []

    def walk(part: dict) -> None:
        mime = part.get("mimeType", "")
        data = part.get("body", {}).get("data")
        if data and mime == "text/plain":
            plain.append(_decode(data))
        elif data and mime == "text/html":
            html_parts.append(_decode(data))
        for child in part.get("parts", []) or []:
            walk(child)

    walk(payload)
    if plain:
        text = "\n".join(plain)
    elif html_parts:
        text = _html_to_text("\n".join(html_parts))
    else:
        text = ""
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def _decode(data: str) -> str:
    # Gmail uses URL-safe base64, sometimes without padding.
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4)).decode("utf-8", errors="replace")


def _html_to_text(markup: str) -> str:
    markup = re.sub(r"(?is)<(script|style|head).*?</\1>", " ", markup)
    markup = re.sub(r"(?i)<br\s*/?>|</p>|</div>|</tr>|</li>", "\n", markup)
    text = re.sub(r"<[^>]+>", " ", markup)
    return re.sub(r"[ \t]+", " ", html.unescape(text))
