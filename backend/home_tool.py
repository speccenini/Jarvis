"""
Read-only smart home status providers.

HomeKit is intentionally not exposed as a simple local Python API. This module
supports practical read-only bridges:
- Home Assistant REST API
- macOS Shortcuts command that returns a HomeKit status summary
"""

import asyncio
import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any


class HomeError(Exception):
    """Raised when home status cannot be queried."""


@dataclass(frozen=True)
class HomeEntity:
    entity_id: str
    name: str
    state: str
    domain: str
    area: str | None = None


class HomeTool:
    """Read-only home status tool."""

    def __init__(
        self,
        provider: str,
        timeout_seconds: int = 20,
        home_assistant_url: str = "",
        home_assistant_token: str = "",
        shortcut_name: str = "Jarvis Home Status",
    ):
        self.provider = provider
        self.timeout_seconds = timeout_seconds
        self.home_assistant_url = home_assistant_url.rstrip("/")
        self.home_assistant_token = home_assistant_token
        self.shortcut_name = shortcut_name

    async def status(self) -> str:
        if self.provider == "homeassistant":
            entities = await self._home_assistant_entities()
            return self._format_status(entities)

        if self.provider == "shortcut":
            return await self._run_shortcut()

        raise HomeError(
            "Home provider is not configured. Set HOME_PROVIDER=homeassistant "
            "or HOME_PROVIDER=shortcut in backend/.env."
        )

    async def devices(self) -> str:
        if self.provider != "homeassistant":
            raise HomeError("Device listing is available with HOME_PROVIDER=homeassistant.")

        entities = await self._home_assistant_entities()
        return self._format_devices(entities)

    async def _home_assistant_entities(self) -> list[HomeEntity]:
        if not self.home_assistant_url or not self.home_assistant_token:
            raise HomeError(
                "Home Assistant is not configured. Set HOME_ASSISTANT_URL and "
                "HOME_ASSISTANT_TOKEN in backend/.env."
            )

        url = f"{self.home_assistant_url}/api/states"
        request = urllib.request.Request(
            url,
            headers={
                "Authorization": f"Bearer {self.home_assistant_token}",
                "Accept": "application/json",
            },
        )

        def fetch_states() -> list[dict[str, Any]]:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                return json.loads(response.read().decode("utf-8"))

        try:
            states = await asyncio.to_thread(fetch_states)
        except urllib.error.HTTPError as exc:
            raise HomeError(f"Home Assistant returned HTTP {exc.code}.") from exc
        except urllib.error.URLError as exc:
            raise HomeError(f"Cannot reach Home Assistant: {exc.reason}") from exc
        except TimeoutError as exc:
            raise HomeError("Home Assistant request timed out.") from exc
        except (OSError, json.JSONDecodeError) as exc:
            raise HomeError(f"Home Assistant request failed: {exc}") from exc

        return [self._entity_from_state(state) for state in states]

    async def _run_shortcut(self) -> str:
        command = ["shortcuts", "run", self.shortcut_name]
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
            raise HomeError("macOS shortcuts command is not available.") from exc
        except asyncio.TimeoutError as exc:
            process.kill()
            raise HomeError("HomeKit shortcut timed out.") from exc

        out = stdout.decode("utf-8", errors="replace").strip()
        err = stderr.decode("utf-8", errors="replace").strip()

        if process.returncode != 0:
            raise HomeError(err or f"Shortcut failed with exit code {process.returncode}.")

        if not out:
            return f"Shortcut '{self.shortcut_name}' completed but returned no status."

        return out[-3900:]

    @staticmethod
    def _entity_from_state(state: dict[str, Any]) -> HomeEntity:
        entity_id = str(state.get("entity_id", "unknown"))
        attributes = state.get("attributes") or {}
        domain = entity_id.split(".", 1)[0] if "." in entity_id else "unknown"
        return HomeEntity(
            entity_id=entity_id,
            name=str(attributes.get("friendly_name") or entity_id),
            state=str(state.get("state", "unknown")),
            domain=domain,
            area=attributes.get("area_id") or attributes.get("room") or None,
        )

    @staticmethod
    def _format_status(entities: list[HomeEntity]) -> str:
        interesting_domains = {"light", "switch", "climate", "cover", "lock", "sensor", "binary_sensor"}
        visible = [entity for entity in entities if entity.domain in interesting_domains]
        active = [
            entity for entity in visible
            if entity.state not in {"off", "unavailable", "unknown", "closed", "locked"}
        ]

        lines = [
            "Home status:",
            f"- Devices/entities visible: {len(visible)}",
            f"- Active/notable states: {len(active)}",
        ]

        for entity in active[:30]:
            lines.append(f"- {entity.name}: {entity.state} ({entity.entity_id})")

        if len(active) > 30:
            lines.append(f"... altri {len(active) - 30} stati non mostrati.")

        return "\n".join(lines)

    @staticmethod
    def _format_devices(entities: list[HomeEntity]) -> str:
        if not entities:
            return "No Home Assistant entities found."

        lines = ["Home devices/entities:"]
        for entity in sorted(entities, key=lambda item: item.entity_id)[:80]:
            lines.append(f"- {entity.name}: {entity.state} ({entity.entity_id})")

        if len(entities) > 80:
            lines.append(f"... altre {len(entities) - 80} entità non mostrate.")

        return "\n".join(lines)
