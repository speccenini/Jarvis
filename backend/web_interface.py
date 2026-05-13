"""
Web Interface for Jarvis
Local browser-based UI served by FastAPI
"""

import logging
import time
from datetime import datetime
from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

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
                "workspace": "/Users/stef/Documents/Jarvis/data",
                "uptime": uptime_str,
            }

    def set_browser_tool(self, browser_tool):
        """Set the browser tool instance."""
        self.browser_tool = browser_tool

    def set_codex_handler(self, handler):
        """Set the async codex handler."""
        self.codex_handler = handler

    def get_app(self):
        """Get the FastAPI app."""
        return self.app

    def get_url(self) -> str:
        """Get the server URL."""
        return f"http://localhost:{self.port}"
