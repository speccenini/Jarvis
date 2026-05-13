"""
Tools Registry Module
Central registry for all Jarvis tools.
Tools can be added dynamically as they are implemented.
"""

import logging
from typing import Dict, Callable, Any, Optional

logger = logging.getLogger(__name__)


class Tool:
    """Represents a Jarvis tool."""

    def __init__(
        self,
        name: str,
        description: str,
        handler: Callable,
        requires_confirmation: bool = False,
        requires_auth: bool = True,
    ):
        """
        Initialize a tool.

        Args:
            name: Tool name (e.g., "codex", "calendar", "weather")
            description: Human-readable description
            handler: Async function that executes the tool
            requires_confirmation: If True, ask user before executing
            requires_auth: If True, user must be authorized
        """
        self.name = name
        self.description = description
        self.handler = handler
        self.requires_confirmation = requires_confirmation
        self.requires_auth = requires_auth

    def to_dict(self) -> Dict[str, Any]:
        """Return tool info as dict."""
        return {
            "name": self.name,
            "description": self.description,
            "requires_confirmation": self.requires_confirmation,
            "requires_auth": self.requires_auth,
        }


class ToolsRegistry:
    """Central registry for all available tools."""

    def __init__(self):
        """Initialize the registry."""
        self.tools: Dict[str, Tool] = {}
        self._register_built_in_tools()
        logger.info(f"ToolsRegistry initialized with {len(self.tools)} built-in tool(s)")

    def _register_built_in_tools(self):
        """Register built-in tools that are always available."""
        # Codex is already available via codex_bridge.py
        # We'll add it as a registered tool
        pass

    def register_tool(
        self,
        name: str,
        description: str,
        handler: Callable,
        requires_confirmation: bool = False,
        requires_auth: bool = True,
    ):
        """
        Register a new tool.

        Args:
            name: Tool name
            description: Human-readable description
            handler: Async function that executes the tool
            requires_confirmation: If True, ask user before executing
            requires_auth: If True, user must be authorized
        """
        tool = Tool(
            name=name,
            description=description,
            handler=handler,
            requires_confirmation=requires_confirmation,
            requires_auth=requires_auth,
        )
        self.tools[name] = tool
        logger.info(f"Registered tool: {name}")

    def get_tool(self, name: str) -> Optional[Tool]:
        """
        Get a tool by name.

        Args:
            name: Tool name

        Returns:
            Tool object or None if not found
        """
        return self.tools.get(name)

    def list_tools(self) -> Dict[str, Dict[str, Any]]:
        """
        List all available tools.

        Returns:
            Dict mapping tool names to tool info
        """
        return {name: tool.to_dict() for name, tool in self.tools.items()}

    def has_tool(self, name: str) -> bool:
        """Check if a tool exists."""
        return name in self.tools

    async def execute_tool(self, name: str, *args, **kwargs) -> Any:
        """
        Execute a tool.

        Args:
            name: Tool name
            *args: Positional arguments to pass to the tool handler
            **kwargs: Keyword arguments to pass to the tool handler

        Returns:
            Result from the tool handler

        Raises:
            ValueError: If tool not found
        """
        tool = self.get_tool(name)
        if not tool:
            raise ValueError(f"Tool not found: {name}")

        logger.info(f"Executing tool: {name}")
        return await tool.handler(*args, **kwargs)
