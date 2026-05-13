"""
Browser Tool - Open web pages and perform searches
"""

import logging
import webbrowser
from typing import Optional
from urllib.parse import quote

logger = logging.getLogger(__name__)


class BrowserTool:
    """Handles browser automation and web searches."""

    @staticmethod
    def google_search(query: str) -> str:
        """
        Open a Google search in the default browser.

        Args:
            query: Search query string

        Returns:
            Status message
        """
        try:
            # Encode the query for URL
            encoded_query = quote(query)
            search_url = f"https://www.google.com/search?q={encoded_query}"

            # Open in default browser
            webbrowser.open(search_url)

            logger.info(f"Opened browser with Google search: {query}")
            return f"🔍 Opened browser with search for: **{query}**"

        except Exception as e:
            logger.error(f"Error opening browser: {e}")
            return f"❌ Error opening browser: {e}"

    @staticmethod
    def open_url(url: str) -> str:
        """
        Open a specific URL in the default browser.

        Args:
            url: URL to open

        Returns:
            Status message
        """
        try:
            # Simple URL validation
            if not url.startswith(("http://", "https://")):
                url = f"https://{url}"

            webbrowser.open(url)

            logger.info(f"Opened URL in browser: {url}")
            return f"🌐 Opened in browser: {url}"

        except Exception as e:
            logger.error(f"Error opening URL: {e}")
            return f"❌ Error opening URL: {e}"

    @staticmethod
    def open_github_search(query: str) -> str:
        """
        Search on GitHub.

        Args:
            query: Search query

        Returns:
            Status message
        """
        try:
            encoded_query = quote(query)
            search_url = f"https://github.com/search?q={encoded_query}"

            webbrowser.open(search_url)

            logger.info(f"Opened GitHub search: {query}")
            return f"🐙 Opened GitHub search for: **{query}**"

        except Exception as e:
            logger.error(f"Error opening GitHub search: {e}")
            return f"❌ Error: {e}"

    @staticmethod
    def open_stackoverflow_search(query: str) -> str:
        """
        Search on Stack Overflow.

        Args:
            query: Search query

        Returns:
            Status message
        """
        try:
            encoded_query = quote(query)
            search_url = f"https://stackoverflow.com/search?q={encoded_query}"

            webbrowser.open(search_url)

            logger.info(f"Opened Stack Overflow search: {query}")
            return f"💻 Opened Stack Overflow search for: **{query}**"

        except Exception as e:
            logger.error(f"Error opening Stack Overflow search: {e}")
            return f"❌ Error: {e}"
