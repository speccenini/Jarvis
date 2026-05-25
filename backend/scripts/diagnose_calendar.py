#!/usr/bin/env python3
"""Standalone diagnostics for Jarvis local macOS Calendar access."""

from __future__ import annotations

import argparse
import asyncio
import json
import subprocess
import sys
import time
from datetime import date, datetime, time as datetime_time, timedelta
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from calendar_tool import AppleCalendarTool, CalendarError
from config import Config


def run_osascript_probe(label: str, script: str, timeout: int) -> bool:
    print(f"\n== {label} ==")
    started = time.monotonic()
    try:
        completed = subprocess.run(
            ["osascript", "-l", "JavaScript", "-e", script],
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except FileNotFoundError:
        print("FAIL: osascript is not available")
        return False
    except subprocess.TimeoutExpired:
        print(f"FAIL: timed out after {timeout}s")
        return False

    elapsed = time.monotonic() - started
    stdout = completed.stdout.strip()
    stderr = completed.stderr.strip()

    print(f"exit_code={completed.returncode} elapsed={elapsed:.2f}s")
    if stdout:
        print(f"stdout={stdout[:1200]}")
    if stderr:
        print(f"stderr={stderr[:1200]}")

    return completed.returncode == 0


async def run_tool_probe(label: str, coro) -> bool:
    print(f"\n== {label} ==")
    started = time.monotonic()
    try:
        events = await coro
    except CalendarError as exc:
        elapsed = time.monotonic() - started
        print(f"FAIL elapsed={elapsed:.2f}s error={exc}")
        return False

    elapsed = time.monotonic() - started
    print(f"OK elapsed={elapsed:.2f}s events={len(events)}")
    for event in events[:10]:
        print(
            json.dumps(
                {
                    "title": event.title,
                    "calendar": event.calendar,
                    "start": event.start,
                    "end": event.end,
                    "all_day": event.all_day,
                },
                ensure_ascii=False,
            )
        )
    if len(events) > 10:
        print(f"... {len(events) - 10} more events")
    return True


async def main() -> int:
    parser = argparse.ArgumentParser(description="Diagnose local macOS Calendar access")
    parser.add_argument("--timeout", type=int, default=Config.CALENDAR_TIMEOUT_SECONDS)
    parser.add_argument(
        "--per-calendar-timeout",
        type=int,
        default=Config.CALENDAR_PER_CALENDAR_TIMEOUT_SECONDS,
    )
    parser.add_argument("--concurrency", type=int, default=Config.CALENDAR_QUERY_CONCURRENCY)
    parser.add_argument("--days", type=int, default=7, help="Range length for events_between probe")
    parser.add_argument(
        "--per-calendar",
        action="store_true",
        help="Probe each calendar independently to find slow calendars",
    )
    args = parser.parse_args()

    print("Jarvis Calendar diagnostic")
    print(f"backend={BACKEND_DIR}")
    print(f"timeout={args.timeout}s")
    print(f"per_calendar_timeout={args.per_calendar_timeout}s")
    print(f"concurrency={args.concurrency}")
    print(f"date={datetime.now().astimezone().isoformat(timespec='seconds')}")
    print("method=osascript -l JavaScript (JXA) -> com.apple.iCal")

    checks = []
    checks.append(
        run_osascript_probe(
            "JXA permission/count calendars",
            'const app = Application("com.apple.iCal"); JSON.stringify({app_name: app.name(), calendar_count: app.calendars().length});',
            args.timeout,
        )
    )
    checks.append(
        run_osascript_probe(
            "JXA list calendar names",
            """
const app = Application("com.apple.iCal");
JSON.stringify(app.calendars().map(function(calendar) {
  try { return calendar.name(); } catch (error) { return "<unreadable>"; }
}));
""",
            args.timeout,
        )
    )

    if args.per_calendar:
        checks.extend(run_per_calendar_probes(args.timeout))

    tool = AppleCalendarTool(
        timeout_seconds=args.timeout,
        per_calendar_timeout_seconds=args.per_calendar_timeout,
        query_concurrency=args.concurrency,
        included_calendar_names=Config.CALENDAR_INCLUDED_NAMES,
        excluded_calendar_names=Config.CALENDAR_EXCLUDED_NAMES,
    )
    today = date.today()
    start = datetime.combine(today, datetime_time.min)
    end = start + timedelta(days=args.days)
    checks.append(await run_tool_probe("AppleCalendarTool today", tool.events_for_today()))
    checks.append(await run_tool_probe("AppleCalendarTool tomorrow", tool.events_for_tomorrow()))
    checks.append(
        await run_tool_probe(
            f"AppleCalendarTool events_between {today.isoformat()} +{args.days}d",
            tool.events_between(start, end),
        )
    )

    if all(checks):
        print("\nRESULT: OK")
        return 0

    print("\nRESULT: FAIL")
    return 1


def run_per_calendar_probes(timeout: int) -> list[bool]:
    print("\n== Per-calendar event probes ==")
    names_script = """
const app = Application("com.apple.iCal");
JSON.stringify(app.calendars().map(function(calendar) {
  try { return calendar.name(); } catch (error) { return "<unreadable>"; }
}));
"""
    completed = subprocess.run(
        ["osascript", "-l", "JavaScript", "-e", names_script],
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if completed.returncode != 0:
        print(f"Could not list calendars: {completed.stderr.strip()}")
        return [False]

    names = json.loads(completed.stdout.strip() or "[]")
    results = []
    for index, name in enumerate(names):
        script = f"""
const start = new Date("{date.today().isoformat()}T00:00:00");
const end = new Date("{(date.today() + timedelta(days=7)).isoformat()}T00:00:00");
const app = Application("com.apple.iCal");
const calendar = app.calendars()[{index}];
let events = [];
try {{
  events = calendar.events.whose({{
    startDate: {{_greaterThan: start, _lessThan: end}}
  }})();
}} catch (error) {{
  events = calendar.events().filter(function(event) {{
    const eventStart = new Date(event.startDate());
    return eventStart >= start && eventStart < end;
  }});
}}
JSON.stringify({{index: {index}, name: {json.dumps(name)}, count: events.length}});
"""
        started = time.monotonic()
        try:
            probe = subprocess.run(
                ["osascript", "-l", "JavaScript", "-e", script],
                check=False,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            print(f"- [{index}] {name}: TIMEOUT after {timeout}s")
            results.append(False)
            continue

        elapsed = time.monotonic() - started
        if probe.returncode == 0:
            print(f"- [{index}] {name}: OK {elapsed:.2f}s {probe.stdout.strip()}")
            results.append(True)
        else:
            print(f"- [{index}] {name}: FAIL {elapsed:.2f}s {probe.stderr.strip()}")
            results.append(False)

    return results


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
