"""
Read-only Apple Calendar access through macOS osascript/JXA.
"""

import asyncio
import json
import logging
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Any

logger = logging.getLogger(__name__)


class CalendarError(Exception):
    """Raised when Apple Calendar cannot be queried."""


@dataclass(frozen=True)
class CalendarEvent:
    title: str
    calendar: str
    start: str
    end: str
    all_day: bool
    location: str | None = None
    notes: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "calendar": self.calendar,
            "start": self.start,
            "end": self.end,
            "all_day": self.all_day,
            "location": self.location,
            "notes": self.notes,
        }


class AppleCalendarTool:
    """Read-only wrapper around Apple Calendar.app."""

    def __init__(self, timeout_seconds: int = 30):
        self.timeout_seconds = timeout_seconds

    async def events_between(self, start: datetime, end: datetime) -> list[CalendarEvent]:
        if end <= start:
            raise CalendarError("Calendar end time must be after start time.")

        script = _calendar_jxa_script()
        command = [
            "osascript",
            "-l",
            "JavaScript",
            "-e",
            script,
            start.isoformat(),
            end.isoformat(),
        ]

        try:
            process = await asyncio.create_subprocess_exec(
                *command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=self.timeout_seconds,
            )
        except FileNotFoundError as exc:
            raise CalendarError("osascript is not available on this system.") from exc
        except asyncio.TimeoutError as exc:
            process.kill()
            raise CalendarError("Apple Calendar query timed out.") from exc

        out = stdout.decode("utf-8", errors="replace").strip()
        err = stderr.decode("utf-8", errors="replace").strip()

        if process.returncode != 0:
            message = err or f"osascript failed with exit code {process.returncode}"
            if "not authorized" in message.lower() or "not allowed" in message.lower():
                message += (
                    " Grant Terminal or your Python runner access in macOS "
                    "System Settings > Privacy & Security > Automation/Calendars."
                )
            raise CalendarError(message)

        try:
            payload = json.loads(out or "[]")
        except json.JSONDecodeError as exc:
            logger.debug("Invalid Calendar JSON output: %s", out)
            raise CalendarError("Apple Calendar returned invalid JSON.") from exc

        return [
            CalendarEvent(
                title=str(item.get("title") or "Untitled"),
                calendar=str(item.get("calendar") or "Unknown"),
                start=str(item.get("start") or ""),
                end=str(item.get("end") or ""),
                all_day=bool(item.get("all_day")),
                location=item.get("location") or None,
                notes=item.get("notes") or None,
            )
            for item in payload
        ]

    async def events_for_day(self, day: date) -> list[CalendarEvent]:
        start = datetime.combine(day, time.min)
        end = start + timedelta(days=1)
        return await self.events_between(start, end)

    async def events_for_today(self) -> list[CalendarEvent]:
        return await self.events_for_day(date.today())

    async def events_for_tomorrow(self) -> list[CalendarEvent]:
        return await self.events_for_day(date.today() + timedelta(days=1))

    async def events_for_week(self) -> list[CalendarEvent]:
        start = datetime.combine(date.today(), time.min)
        end = start + timedelta(days=7)
        return await self.events_between(start, end)


def parse_date(value: str, field_name: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise CalendarError(f"{field_name} must use YYYY-MM-DD format.") from exc


def _calendar_jxa_script() -> str:
    return r"""
function run(argv) {
  const start = new Date(argv[0]);
  const end = new Date(argv[1]);
  const app = Application("Calendar");
  const output = [];

  function valueOrNull(getter) {
    try {
      const value = getter();
      if (value === undefined || value === null) {
        return null;
      }
      return String(value);
    } catch (error) {
      return null;
    }
  }

  function dateIso(value) {
    if (!value) {
      return null;
    }
    return new Date(value).toISOString();
  }

  const calendars = app.calendars();
  calendars.forEach(function(calendar) {
    const calendarName = valueOrNull(function() { return calendar.name(); }) || "Unknown";
    let events = [];

    try {
      events = calendar.events.whose({
        startDate: {_greaterThan: start, _lessThan: end}
      })();
    } catch (error) {
      events = calendar.events().filter(function(event) {
        const eventStart = new Date(event.startDate());
        return eventStart >= start && eventStart < end;
      });
    }

    events.forEach(function(event) {
      output.push({
        title: valueOrNull(function() { return event.summary(); }) || "Untitled",
        calendar: calendarName,
        start: dateIso(valueOrNull(function() { return event.startDate(); })),
        end: dateIso(valueOrNull(function() { return event.endDate(); })),
        all_day: Boolean(valueOrNull(function() { return event.alldayEvent(); }) === "true"),
        location: valueOrNull(function() { return event.location(); }),
        notes: valueOrNull(function() { return event.description(); })
      });
    });
  });

  output.sort(function(a, b) {
    return String(a.start).localeCompare(String(b.start));
  });

  return JSON.stringify(output);
}
"""
