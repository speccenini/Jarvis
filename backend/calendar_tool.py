"""
Read-only Apple Calendar access through macOS osascript/JXA.
"""

import asyncio
import json
import logging
import time as monotonic_time
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

    def __init__(
        self,
        timeout_seconds: int = 30,
        per_calendar_timeout_seconds: int = 5,
        query_concurrency: int = 3,
        included_calendar_names: list[str] | None = None,
        excluded_calendar_names: list[str] | None = None,
    ):
        self.timeout_seconds = timeout_seconds
        self.per_calendar_timeout_seconds = per_calendar_timeout_seconds
        self.query_concurrency = max(1, query_concurrency)
        self.included_calendar_names = {
            _normalize_calendar_name(name)
            for name in (included_calendar_names or [])
            if name.strip()
        }
        self.excluded_calendar_names = {
            _normalize_calendar_name(name)
            for name in (excluded_calendar_names or [])
            if name.strip()
        }

    async def events_between(self, start: datetime, end: datetime) -> list[CalendarEvent]:
        if end <= start:
            raise CalendarError("Calendar end time must be after start time.")

        started = monotonic_time.monotonic()

        try:
            calendars = await self._calendar_names()
            calendars = [
                (index, name)
                for index, name in calendars
                if self._calendar_is_enabled(name)
            ]
            semaphore = asyncio.Semaphore(self.query_concurrency)
            tasks = [
                self._events_between_for_calendar_limited(semaphore, index, name, start, end)
                for index, name in calendars
            ]
            batches = max(1, (len(calendars) + self.query_concurrency - 1) // self.query_concurrency)
            overall_timeout = max(
                self.timeout_seconds,
                self.per_calendar_timeout_seconds * batches + 10,
            )
            results = await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True),
                timeout=overall_timeout,
            )
        except FileNotFoundError as exc:
            raise CalendarError("osascript is not available on this system.") from exc
        except asyncio.TimeoutError as exc:
            raise CalendarError(
                "Apple Calendar non ha risposto in tempo. "
                "Riduci i calendari interrogati con CALENDAR_INCLUDED_NAMES oppure "
                "aumenta CALENDAR_TIMEOUT_SECONDS."
            ) from exc

        events: list[CalendarEvent] = []
        failures = []
        for result in results:
            if isinstance(result, Exception):
                failures.append(str(result))
                continue
            events.extend(result)

        elapsed = monotonic_time.monotonic() - started
        if failures:
            logger.warning(
                "Calendar skipped %s slow/failed calendar(s) for range %s -> %s: %s",
                len(failures),
                start.isoformat(),
                end.isoformat(),
                "; ".join(failures[:5]),
            )

        events.sort(key=lambda event: event.start or "")
        logger.info(
            "Calendar query completed in %.2fs for range %s -> %s with %s event(s), %s failure(s)",
            elapsed,
            start.isoformat(),
            end.isoformat(),
            len(events),
            len(failures),
        )

        if not events and failures and len(failures) == len(calendars):
            raise CalendarError(f"All Calendar queries failed: {'; '.join(failures[:3])}")

        return events

    async def _calendar_names(self) -> list[tuple[int, str]]:
        out = await self._run_osascript(_calendar_names_jxa_script(), timeout=self.timeout_seconds)
        try:
            names = json.loads(out or "[]")
        except json.JSONDecodeError as exc:
            raise CalendarError("Apple Calendar returned invalid calendar-name JSON.") from exc
        return [(index, str(name or "Unknown")) for index, name in enumerate(names)]

    async def _events_between_for_calendar(
        self,
        index: int,
        name: str,
        start: datetime,
        end: datetime,
    ) -> list[CalendarEvent]:
        try:
            out = await self._run_osascript(
                _calendar_events_for_index_jxa_script(),
                str(index),
                start.isoformat(),
                end.isoformat(),
                timeout=self.per_calendar_timeout_seconds,
            )
        except CalendarError as exc:
            raise CalendarError(f"{name}: {exc}") from exc

        try:
            payload = json.loads(out or "[]")
        except json.JSONDecodeError as exc:
            raise CalendarError(f"{name}: invalid event JSON") from exc

        return [_calendar_event_from_payload(item) for item in payload]

    async def _events_between_for_calendar_limited(
        self,
        semaphore: asyncio.Semaphore,
        index: int,
        name: str,
        start: datetime,
        end: datetime,
    ) -> list[CalendarEvent]:
        async with semaphore:
            return await self._events_between_for_calendar(index, name, start, end)

    async def _run_osascript(self, script: str, *args: str, timeout: int) -> str:
        process = await asyncio.create_subprocess_exec(
            "osascript",
            "-l",
            "JavaScript",
            "-e",
            script,
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
        except asyncio.TimeoutError as exc:
            process.kill()
            try:
                await process.wait()
            except Exception:
                logger.debug("Timed-out Calendar process did not exit cleanly", exc_info=True)
            raise CalendarError(f"timeout after {timeout}s") from exc

        out = stdout.decode("utf-8", errors="replace").strip()
        err = stderr.decode("utf-8", errors="replace").strip()
        if process.returncode != 0:
            raise CalendarError(_format_calendar_process_error(err or f"osascript exit {process.returncode}"))
        return out

    def _calendar_is_enabled(self, name: str) -> bool:
        normalized = _normalize_calendar_name(name)
        if self.included_calendar_names and normalized not in self.included_calendar_names:
            return False
        if normalized in self.excluded_calendar_names:
            return False
        return True

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


def _format_calendar_process_error(message: str) -> str:
    """Convert common macOS permission errors into actionable guidance."""
    normalized = message.lower()
    permission_markers = (
        "-1743",
        "not authorized",
        "not allowed",
        "not permitted",
        "operation not permitted",
        "not authorised",
    )

    if any(marker in normalized for marker in permission_markers):
        return (
            "macOS sta bloccando l'accesso ad Apple Calendar.\n\n"
            "Apri System Settings > Privacy & Security e controlla:\n"
            "- Automation: abilita Terminal/Python per controllare Calendar.\n"
            "- Calendars: abilita Terminal/Python se presente.\n\n"
            "Poi riavvia Jarvis con: ./jarvis restart\n\n"
            f"Dettaglio macOS: {message}"
        )

    return message


def _normalize_calendar_name(name: str) -> str:
    return " ".join(name.lower().split())


def _calendar_event_from_payload(item: dict[str, Any]) -> CalendarEvent:
    return CalendarEvent(
        title=str(item.get("title") or "Untitled"),
        calendar=str(item.get("calendar") or "Unknown"),
        start=str(item.get("start") or ""),
        end=str(item.get("end") or ""),
        all_day=bool(item.get("all_day")),
        location=item.get("location") or None,
        notes=item.get("notes") or None,
    )


def _calendar_names_jxa_script() -> str:
    return r"""
function run(argv) {
  const app = Application("com.apple.iCal");
  return JSON.stringify(app.calendars().map(function(calendar) {
    try {
      return calendar.name();
    } catch (error) {
      return "Unknown";
    }
  }));
}
"""


def _calendar_events_for_index_jxa_script() -> str:
    return r"""
function run(argv) {
  const calendarIndex = Number(argv[0]);
  const start = new Date(argv[1]);
  const end = new Date(argv[2]);
  const app = Application("com.apple.iCal");
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

  const calendar = app.calendars()[calendarIndex];
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

  output.sort(function(a, b) {
    return String(a.start).localeCompare(String(b.start));
  });

  return JSON.stringify(output);
}
"""
