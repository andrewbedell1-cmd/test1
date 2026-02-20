"""
Export action items as an iCalendar (.ics) file.
The resulting file can be imported into Google Calendar, Apple Calendar, Outlook, etc.
"""

from datetime import datetime, date, timedelta
from typing import Optional, List
from icalendar import Calendar, Event, vText
import hashlib


def _make_uid(item_id: int, title: str) -> str:
    h = hashlib.md5(f"{item_id}-{title}".encode()).hexdigest()
    return f"action-{h}@transcript-pm"


def _parse_date(due_date_str: Optional[str]) -> Optional[date]:
    if not due_date_str:
        return None
    try:
        return date.fromisoformat(due_date_str)
    except (ValueError, TypeError):
        return None


def build_ical(action_items: List[dict], calendar_name: str = "Transcript Action Items") -> bytes:
    """
    Build an iCal file from a list of action item dicts.
    Items without a due_date are given a 1-week-from-now default.
    Returns raw .ics bytes.
    """
    cal = Calendar()
    cal.add("prodid", "-//Transcript PM//transcript-pm//EN")
    cal.add("version", "2.0")
    cal.add("calscale", "GREGORIAN")
    cal.add("x-wr-calname", vText(calendar_name))
    cal.add("x-wr-timezone", vText("UTC"))

    default_date = date.today() + timedelta(weeks=1)

    priority_map = {"high": 1, "medium": 5, "low": 9}

    for item in action_items:
        event = Event()
        event.add("summary", item["title"])

        due = _parse_date(item.get("due_date")) or default_date
        event.add("dtstart", due)
        event.add("dtend", due + timedelta(days=1))
        event.add("dtstamp", datetime.utcnow())

        description_parts = []
        if item.get("description"):
            description_parts.append(item["description"])
        if item.get("assignee"):
            description_parts.append(f"Assignee: {item['assignee']}")
        if item.get("priority"):
            description_parts.append(f"Priority: {item['priority'].upper()}")
        if item.get("project_name"):
            description_parts.append(f"Project: {item['project_name']}")
        if item.get("status"):
            description_parts.append(f"Status: {item['status']}")

        event.add("description", "\n\n".join(description_parts))
        event.add("priority", priority_map.get(item.get("priority", "medium"), 5))
        event.add("uid", _make_uid(item["id"], item["title"]))

        if item.get("status") == "done":
            event.add("status", "COMPLETED")
        else:
            event.add("status", "NEEDS-ACTION")

        cal.add_component(event)

    return cal.to_ical()
