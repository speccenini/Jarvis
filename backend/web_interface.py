"""
Web Interface for Jarvis
Local browser-based UI served by FastAPI
"""

import logging
import time
from datetime import datetime, time as datetime_time, timedelta
from pathlib import Path
from fastapi import FastAPI, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

from calendar_tool import CalendarError, parse_date
from config import Config

logger = logging.getLogger(__name__)


class SearchRequest(BaseModel):
    query: str


class CodexRequest(BaseModel):
    prompt: str


class JarvisWebServer:
    """Web server for Jarvis frontend."""

    def __init__(self, port: int = 8000):
        self.port = port
        self.app = FastAPI(title="Jarvis Web Interface")
        self.start_time = time.time()
        self.browser_tool = None
        self.codex_handler = None
        self.calendar_tool = None
        self.document_service = None
        self._setup_routes()

    def _setup_routes(self):
        """Setup FastAPI routes."""

        # Serve static files
        static_path = Path(__file__).parent / "static"
        self.app.mount("/static", StaticFiles(directory=str(static_path)), name="static")

        # Root route
        @self.app.get("/")
        async def root():
            return FileResponse(str(static_path / "index.html"))

        # API Routes
        @self.app.post("/api/search")
        async def api_search(request: SearchRequest):
            """Handle search requests."""
            try:
                if not self.browser_tool:
                    return {
                        "status": "error",
                        "message": "Browser tool not available",
                    }

                result = self.browser_tool.google_search(request.query)
                logger.info(f"Search executed: {request.query}")

                return {
                    "status": "opened",
                    "message": f"🔍 Aperto browser con ricerca: {request.query}",
                }
            except Exception as e:
                logger.error(f"Search error: {e}")
                return {"status": "error", "message": str(e)}

        @self.app.post("/api/codex")
        async def api_codex(request: CodexRequest):
            """Handle Codex requests."""
            try:
                if not self.codex_handler:
                    return {
                        "status": "error",
                        "error": "Codex handler not available",
                    }

                result = await self.codex_handler(request.prompt)
                logger.info(f"Codex executed: {request.prompt[:50]}")

                return {"status": "success", "result": result}
            except Exception as e:
                logger.error(f"Codex error: {e}")
                return {"status": "error", "error": str(e)}

        @self.app.get("/api/status")
        async def api_status():
            """Get system status."""
            uptime_seconds = int(time.time() - self.start_time)
            uptime_str = f"{uptime_seconds // 60}m {uptime_seconds % 60}s"

            return {
                "backend": "🟢 Running",
                "telegram": "🟢 Connected",
                "workspace": str(Config.JARVIS_WORKSPACE),
                "uptime": uptime_str,
            }

        @self.app.get("/api/calendar/today")
        async def api_calendar_today():
            """Get today's Apple Calendar events."""
            return await self._calendar_response("today")

        @self.app.get("/api/calendar/tomorrow")
        async def api_calendar_tomorrow():
            """Get tomorrow's Apple Calendar events."""
            return await self._calendar_response("tomorrow")

        @self.app.get("/api/calendar/week")
        async def api_calendar_week():
            """Get Apple Calendar events for the next 7 days."""
            return await self._calendar_response("week")

        @self.app.get("/api/calendar/events")
        async def api_calendar_events(
            start: str = Query(..., description="Start date in YYYY-MM-DD format"),
            end: str = Query(..., description="End date in YYYY-MM-DD format, exclusive"),
        ):
            """Get Apple Calendar events between two dates."""
            try:
                if not self.calendar_tool:
                    return {"status": "error", "error": "Calendar tool not available"}

                start_date = parse_date(start, "start")
                end_date = parse_date(end, "end")
                start_dt = datetime.combine(start_date, datetime_time.min)
                end_dt = datetime.combine(end_date, datetime_time.min)

                events = await self.calendar_tool.events_between(start_dt, end_dt)
                return {
                    "status": "success",
                    "range": {
                        "start": start_dt.isoformat(),
                        "end": end_dt.isoformat(),
                    },
                    "events": [event.to_dict() for event in events],
                }
            except CalendarError as e:
                logger.error(f"Calendar error: {e}")
                return {"status": "error", "error": str(e)}

        @self.app.get("/api/documents/status")
        async def api_documents_status():
            """Get local document index status."""
            if not self.document_service:
                return {"status": "error", "error": "Document service not available"}
            return {"status": "success", "index": self.document_service.stats()}

        @self.app.post("/api/documents/index")
        async def api_documents_index():
            """Index local PDF documents."""
            try:
                if not self.document_service:
                    return {"status": "error", "error": "Document service not available"}
                indexed = self.document_service.index_all()
                return {
                    "status": "success",
                    "indexed": [item.__dict__ for item in indexed],
                    "index": self.document_service.stats(),
                }
            except Exception as e:
                logger.error(f"Document index error: {e}")
                return {"status": "error", "error": str(e)}

        @self.app.post("/api/documents/search")
        async def api_documents_search(request: SearchRequest):
            """Search local indexed documents."""
            try:
                if not self.document_service:
                    return {"status": "error", "error": "Document service not available"}
                return {
                    "status": "success",
                    "result": self.document_service.search(request.query),
                }
            except Exception as e:
                logger.error(f"Document search error: {e}")
                return {"status": "error", "error": str(e)}

    def set_browser_tool(self, browser_tool):
        """Set the browser tool instance."""
        self.browser_tool = browser_tool

    def set_codex_handler(self, handler):
        """Set the async codex handler."""
        self.codex_handler = handler

    def set_calendar_tool(self, calendar_tool):
        """Set the calendar tool instance."""
        self.calendar_tool = calendar_tool

    def set_document_service(self, document_service):
        """Set the document service instance."""
        self.document_service = document_service

    def get_app(self):
        """Get the FastAPI app."""
        return self.app

    def get_url(self) -> str:
        """Get the server URL."""
        return f"http://localhost:{self.port}"

    async def _calendar_response(self, period: str):
        try:
            if not self.calendar_tool:
                return {"status": "error", "error": "Calendar tool not available"}

            if period == "today":
                events = await self.calendar_tool.events_for_today()
                start = datetime.combine(datetime.now().date(), datetime_time.min)
                end = start + timedelta(days=1)
            elif period == "tomorrow":
                start = datetime.combine(
                    datetime.now().date(),
                    datetime_time.min,
                ) + timedelta(days=1)
                end = start + timedelta(days=1)
                events = await self.calendar_tool.events_for_tomorrow()
            elif period == "week":
                start = datetime.combine(datetime.now().date(), datetime_time.min)
                end = start + timedelta(days=7)
                events = await self.calendar_tool.events_for_week()
            else:
                return {"status": "error", "error": f"Unknown calendar period: {period}"}

            return {
                "status": "success",
                "range": {
                    "start": start.isoformat(),
                    "end": end.isoformat(),
                },
                "events": [event.to_dict() for event in events],
            }
        except CalendarError as e:
            logger.error(f"Calendar error: {e}")
            return {"status": "error", "error": str(e)}
