"""
Small CLI probe used by ./jarvis calendar-auth.
"""

import asyncio

from calendar_tool import AppleCalendarTool, CalendarError
from config import Config


async def main() -> int:
    try:
        await AppleCalendarTool(timeout_seconds=Config.CALENDAR_TIMEOUT_SECONDS).events_for_today()
    except CalendarError as exc:
        print(exc)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
