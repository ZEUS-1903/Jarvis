"""Read-only Google Calendar access."""
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo


def list_events(service, start_day: date, days: int, tz: str) -> list[dict]:
    zone = ZoneInfo(tz)
    start = datetime.combine(start_day, time.min, zone)
    end = start + timedelta(days=days)
    resp = service.events().list(
        calendarId="primary",
        timeMin=start.isoformat(), timeMax=end.isoformat(),
        singleEvents=True,      # expand recurring events into individual occurrences
        orderBy="startTime",
        maxResults=50,
    ).execute()
    return [_event(e, zone) for e in resp.get("items", []) if e.get("status") != "cancelled"]


def _event(e: dict, zone: ZoneInfo) -> dict:
    start, end = e.get("start", {}), e.get("end", {})
    all_day = "date" in start and "dateTime" not in start
    if all_day:
        when = datetime.fromisoformat(start["date"]).strftime("%a %b %-d") + " (all day)"
    else:
        s = datetime.fromisoformat(start["dateTime"]).astimezone(zone)
        f = datetime.fromisoformat(end["dateTime"]).astimezone(zone)
        when = f"{s:%a %b %-d}, {s:%-I:%M %p} - {f:%-I:%M %p}"
    return {
        "title": e.get("summary", "(no title)"),
        "when": when,
        "location": e.get("location"),
        "attendees": len(e.get("attendees", [])),
        "organizer": e.get("organizer", {}).get("email"),
    }
