# macOS Calendar Diagnostic

Date: 2026-05-25

## Summary

Jarvis currently reads the local macOS Apple Calendar through `osascript` using
JavaScript for Automation (JXA). It does not use iCloud CalDAV, Shortcuts,
Swift/EventKit, PyObjC, or direct Calendar SQLite access.

The original reliability problems had two separate causes:

1. The JXA code used `Application("Calendar")`, which is fragile on localized
   macOS installations. On this Mac the application name resolves as
   `Kalender`. Using the stable bundle identifier `Application("com.apple.iCal")`
   works.
2. Calendar.app can hang when querying events from some individual calendars.
   Permissions are OK, but several calendars exceed a 5 second per-calendar
   probe timeout.

## Current implementation

Relevant files:

- `backend/calendar_tool.py`
- `backend/calendar_auth_check.py`
- `backend/scripts/diagnose_calendar.py`
- `backend/jarvis_core.py`
- `backend/web_interface.py`

Access method:

```text
Python asyncio subprocess
  -> osascript -l JavaScript
  -> JXA Application("com.apple.iCal")
  -> local Calendar.app calendars/events
```

Telegram uses the same `AppleCalendarTool`, but the Telegram flow was not
redesigned for this diagnostic task.

## Permission test results

Standalone diagnostic command:

```bash
./jarvis calendar-diagnose --timeout 20 --per-calendar-timeout 5 --concurrency 3 --days 7
```

Observed permission probes:

```text
JXA permission/count calendars: OK
app_name: Kalender
calendar_count: 20

JXA list calendar names: OK
```

This means macOS Automation permission is currently sufficient for Terminal /
Python / osascript to reach Calendar.app.

## Timeout diagnosis

The aggregate "all calendars in one osascript" query timed out. Per-calendar
diagnostics showed mixed results.

Calendars that responded within 5 seconds in the diagnostic run included:

- `FC Uster - Senioren 40`
- `FC Uster - Junioren D/9 c`
- `NotRelevant`
- `UniMarconi`
- `Polar training results`
- `baby-sitter`
- `Geplante Erinnerungen`
- `Geburtstage`
- `Siri-Vorschläge`

Calendars that timed out at 5 seconds included:

- `Marco`
- `Chiara`
- `Micol`
- `Stefan P`
- `Family`
- `FC Uster - Heimspielplan`
- `Stefano Gmail`
- holiday calendars such as `Festività ...` / `Schweizerische Feiertage`

The likely cause is Calendar.app/JXA performance over calendars with many
events, subscriptions, remote sync state, or holiday-generated event sets.

## Stabilization applied

The Calendar provider now:

- uses `Application("com.apple.iCal")` instead of the localized app name
- lists calendars first
- queries calendars individually
- limits concurrent osascript calls
- applies a per-calendar timeout
- skips and logs slow/failed calendars instead of blocking the entire request

New configuration options:

```env
CALENDAR_TIMEOUT_SECONDS=20
CALENDAR_PER_CALENDAR_TIMEOUT_SECONDS=5
CALENDAR_QUERY_CONCURRENCY=3
CALENDAR_INCLUDED_NAMES=
CALENDAR_EXCLUDED_NAMES=
```

If Calendar answers are too slow or miss important calendars, tune
`CALENDAR_INCLUDED_NAMES` to a comma-separated list of calendars Jarvis should
query. This is the safest short-term stabilization path while keeping the
current osascript implementation.

Current local preference:

```env
CALENDAR_INCLUDED_NAMES=Stefan P,Family
CALENDAR_PER_CALENDAR_TIMEOUT_SECONDS=15
CALENDAR_QUERY_CONCURRENCY=1
```

The user-facing preference is "Stefano Peccenini" and "Family"; on this Mac the
Apple calendar list exposes that personal calendar as `Stefan P`.

## Required macOS permissions

Open:

```text
System Settings > Privacy & Security
```

Check:

- `Automation`: allow Terminal/Python/osascript to control Calendar.
- `Calendars`: allow Terminal/Python/osascript if macOS shows those entries.

Permission helper:

```bash
./jarvis calendar-auth
```

Diagnostic helper:

```bash
./jarvis calendar-diagnose --timeout 20 --per-calendar-timeout 5 --concurrency 3 --days 7
```

## Remaining risk

The current osascript/JXA approach is workable but not ideal for large or slow
Calendar.app datasets. If reliable access to all personal calendars is required,
the next technical step should be a small native EventKit helper in Swift or
PyObjC. That is outside this diagnostic task.
