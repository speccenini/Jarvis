# Jarvis AI Assistant — Iterative Implementation Plan

## 1. Goal

Build a personal AI assistant named **Jarvis**, running locally on **macOS**, accessible through **Telegram**, connected to a local **Codex CLI** instance, and progressively integrated with local documents, Apple Calendar, Apple Weather/WeatherKit, browser automation, voice interaction, and eventually Apple Home/HomeKit or a Home Assistant bridge.

The backend must be implemented in **Python**.

---

## 2. Product Vision

Jarvis should act as a private, local-first personal assistant with these capabilities:

1. Answer questions through Telegram.
2. Use a local knowledge base built from personal documents.
3. Delegate coding, file analysis, and repo work to Codex CLI.
4. Read local Apple Calendar data.
5. Retrieve weather data through Apple WeatherKit, or a compatible fallback provider if WeatherKit credentials are unavailable.
6. Open web pages or perform browser actions on the Mac when explicitly requested.
7. Later support voice interaction.
8. Later inspect or control smart-home devices through HomeKit-compatible infrastructure.

The system must be implemented incrementally. Do not try to build everything at once.

---

## 3. Guiding Principles

### 3.1 Local-first

Prefer local execution on the Mac for sensitive capabilities:

- Codex CLI execution
- document indexing
- browser control
- Apple Calendar access
- voice capture/playback
- HomeKit/Home Assistant bridge access

### 3.2 Explicit permissions

Jarvis must never execute sensitive actions silently.

Actions requiring confirmation:

- running shell commands
- modifying files
- opening websites if the URL is not obviously safe
- creating, editing, or deleting calendar events
- controlling smart-home devices
- sending messages or emails
- running Codex with write permissions

### 3.3 Tool separation

Jarvis should not be one monolithic script. Implement a small backend core with explicit tools:

- `telegram_adapter`
- `llm_orchestrator`
- `codex_tool`
- `document_search_tool`
- `calendar_tool`
- `weather_tool`
- `browser_tool`
- `voice_tool`
- `home_tool`

### 3.4 Auditability

Every action should be logged with:

- timestamp
- Telegram user ID
- normalized user request
- selected tool
- arguments passed to tool
- whether confirmation was required
- result summary
- error summary, if any

Do not log secrets or full private document contents.

---

## 4. Recommended Architecture

```text
Telegram App / Phone
        |
        v
Telegram Bot API
        |
        v
Python Backend on macOS
        |
        +-- Telegram Adapter
        +-- Conversation Router / Orchestrator
        +-- User Authorization Layer
        +-- Tool Registry
        |       |
        |       +-- Codex CLI Tool
        |       +-- Document RAG Tool
        |       +-- Apple Calendar Tool
        |       +-- WeatherKit Tool
        |       +-- Browser Automation Tool
        |       +-- Voice Tool, later
        |       +-- HomeKit/Home Assistant Tool, later
        |
        +-- SQLite State DB
        +-- Local Vector Store
        +-- Logs
```

---

## 5. Suggested Technology Stack

### 5.1 Backend

- Python 3.12+
- `fastapi` for HTTP API and webhook mode
- `uvicorn` for local development server
- `python-telegram-bot` or direct Telegram Bot API client
- `pydantic` for typed configs and tool schemas
- `sqlite` for state, audit logs, and conversation metadata
- `httpx` for outbound HTTP calls
- `python-dotenv` or environment variables for secrets

### 5.2 Telegram integration

Start with long polling for local development.

Later add webhook mode through one of:

- local tunnel: `ngrok`, `cloudflared`, or Tailscale Funnel
- reverse proxy on VPS
- direct public endpoint only if the Mac is safely exposed, which is usually not recommended

### 5.3 Codex integration

Use local **Codex CLI** via subprocess.

Codex must run in a constrained working directory, for example:

```text
~/Jarvis/workspaces/
~/Jarvis/repos/
~/Jarvis/scratch/
```

Never allow arbitrary shell execution from Telegram without a confirmation gate.

### 5.4 Document analysis

Use local RAG:

- document ingestion pipeline
- chunking
- local vector store
- metadata index
- source references in answers

Possible libraries:

- `pypdf` for PDFs
- `python-docx` for DOCX
- `markdown` / plain text loaders
- `chromadb` or `lancedb` for vector search
- OpenAI embeddings or a local embedding model, depending on privacy/cost preference

### 5.5 Apple Calendar access

Recommended first implementation:

- read-only access through macOS automation layer
- use AppleScript/JXA as the Python bridge initially
- later evaluate a native Swift helper using EventKit for more robust calendar access

Initial scope:

- list today's events
- list tomorrow's events
- search events by date range
- summarize free/busy slots

Do not implement event creation/editing in MVP.

### 5.6 Apple Weather

Preferred:

- Apple WeatherKit REST API

Requirements:

- Apple Developer Program membership
- WeatherKit-enabled service identifier
- private key / team ID / key ID
- JWT signing in backend

Initial scope:

- current weather for a configured default location
- daily forecast
- weather summary via Telegram command

Fallback if WeatherKit setup is delayed:

- implement a provider interface and use another weather provider temporarily
- keep the public tool name as `weather_tool`

### 5.7 Browser automation

Use **Playwright for Python**.

Initial scope:

- open a URL in the local browser
- optionally take screenshot
- optionally extract page title and text

Do not allow arbitrary login interaction or credential handling in MVP.

### 5.8 Voice assistant, later

Phase 1:

- Telegram voice messages as input
- speech-to-text transcription
- text response

Phase 2:

- local microphone hotkey or push-to-talk
- text-to-speech answer

Phase 3:

- wake-word detection, only if privacy and reliability are acceptable

### 5.9 HomeKit / smart home

Direct HomeKit control from Python is not the best first step.

Recommended practical path:

1. Use Home Assistant as a bridge if available or acceptable.
2. Expose HomeKit-compatible devices to Home Assistant where possible.
3. Jarvis talks to Home Assistant via its REST API or WebSocket API.
4. Implement read-only status first.
5. Add control actions only with explicit confirmation.

Initial Home scope:

- list rooms/devices
- get status of lights, temperature, sensors
- ask “what is on?”
- later: turn lights on/off with confirmation

---

## 6. Minimum Viable Product

The MVP should be deliberately small.

### MVP objective

A local Python backend reachable from Telegram that can:

1. Authenticate one allowed Telegram user.
2. Answer simple assistant messages.
3. Run a safe Codex CLI request in a predefined workspace.
4. Search a small local document folder.
5. Return answers with clear tool-result boundaries.
6. Log all requests and tool calls.

### MVP exclusions

Do not include these in the first MVP:

- HomeKit control
- voice assistant
- calendar write access
- browser login automation
- unrestricted shell access
- multi-user support
- public internet exposure beyond what is needed for Telegram polling

---

## 7. Repository Structure

Create this structure:

```text
jarvis/
  README.md
  pyproject.toml
  .env.example
  .gitignore
  src/
    jarvis/
      __init__.py
      main.py
      config.py
      logging_config.py
      auth.py
      router.py
      models.py
      state/
        db.py
        migrations.py
      telegram/
        bot.py
        handlers.py
        formatting.py
      tools/
        __init__.py
        base.py
        codex.py
        documents.py
        calendar.py
        weather.py
        browser.py
        home.py
        voice.py
      services/
        llm.py
        memory.py
        confirmation.py
      utils/
        subprocess_runner.py
        secrets.py
  tests/
    test_auth.py
    test_router.py
    test_codex_tool.py
    test_documents_tool.py
  scripts/
    init_db.py
    ingest_documents.py
    run_local.sh
  data/
    documents/
    index/
    logs/
    sqlite/
  workspaces/
    scratch/
    repos/
```

---

## 8. Configuration

Create `.env.example`:

```env
JARVIS_ENV=dev
JARVIS_NAME=Jarvis
JARVIS_ALLOWED_TELEGRAM_USER_IDS=123456789

TELEGRAM_BOT_TOKEN=replace_me

OPENAI_API_KEY=replace_me_if_needed
OPENAI_MODEL=gpt-4.1-mini
OPENAI_EMBEDDING_MODEL=text-embedding-3-small

JARVIS_BASE_DIR=/Users/<user>/Jarvis
JARVIS_DOCUMENT_DIR=/Users/<user>/Jarvis/data/documents
JARVIS_WORKSPACE_DIR=/Users/<user>/Jarvis/workspaces
JARVIS_SQLITE_PATH=/Users/<user>/Jarvis/data/sqlite/jarvis.db

CODEX_BIN=codex
CODEX_DEFAULT_WORKDIR=/Users/<user>/Jarvis/workspaces/scratch
CODEX_TIMEOUT_SECONDS=120
CODEX_REQUIRE_CONFIRMATION=true

APPLE_DEFAULT_LOCATION_NAME=Uster
APPLE_DEFAULT_LATITUDE=47.3500
APPLE_DEFAULT_LONGITUDE=8.7167

WEATHER_PROVIDER=weatherkit
WEATHERKIT_TEAM_ID=replace_me
WEATHERKIT_KEY_ID=replace_me
WEATHERKIT_SERVICE_ID=replace_me
WEATHERKIT_PRIVATE_KEY_PATH=/Users/<user>/Jarvis/secrets/weatherkit.p8

BROWSER_HEADLESS=false
BROWSER_DEFAULT=chromium

HOME_PROVIDER=disabled
HOME_ASSISTANT_URL=http://homeassistant.local:8123
HOME_ASSISTANT_TOKEN=replace_me
```

---

## 9. Telegram Command Design

Implement commands progressively.

### MVP commands

```text
/start
/help
/status
/ask <question>
/codex <task>
/docs <question>
/confirm <id>
/cancel <id>
```

### Later commands

```text
/calendar today
/calendar tomorrow
/calendar week
/weather
/open <url>
/home status
/home devices
/voice on
/voice off
```

### Natural language support

After commands are stable, add routing for natural language:

```text
Jarvis, ask Codex to inspect this repo and summarize the architecture.
Jarvis, what meetings do I have tomorrow?
Jarvis, open the SAP note page in my browser.
Jarvis, how is the weather tomorrow morning?
```

---

## 10. Confirmation Flow

Implement a generic confirmation mechanism before dangerous actions.

Example:

```text
User: /codex modify the Flask app to add authentication
Jarvis: This may modify files in /Users/.../workspaces/scratch. Confirm? /confirm 8f2a91 or /cancel 8f2a91
User: /confirm 8f2a91
Jarvis: Running Codex now...
```

Persist pending confirmations in SQLite:

```sql
CREATE TABLE confirmations (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  action_type TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  expires_at TEXT NOT NULL,
  status TEXT NOT NULL
);
```

---

## 11. Iterative Implementation Plan

## Phase 0 — Project Bootstrap

### Goal

Create the repository, configuration system, local run script, and base application skeleton.

### Tasks for Codex

1. Create the repository structure defined above.
2. Add `pyproject.toml` with dependencies.
3. Add `.env.example`.
4. Implement `config.py` using Pydantic settings.
5. Implement structured logging.
6. Add `scripts/run_local.sh`.
7. Add a minimal `README.md` with setup instructions.

### Acceptance criteria

- `python -m jarvis.main` starts without error.
- Environment variables are loaded.
- Logs are written to console and file.
- Unit tests run.

---

## Phase 1 — Telegram MVP

### Goal

Jarvis is reachable from Telegram and answers basic commands.

### Tasks for Codex

1. Implement Telegram bot with long polling.
2. Restrict access to allowed Telegram user IDs.
3. Implement `/start`, `/help`, `/status`.
4. Implement `/ask <message>` with a simple LLM response.
5. Add basic error handling.
6. Add audit logging for every message.

### Acceptance criteria

- Unauthorized users are rejected.
- Authorized user can send `/status` and receive a health response.
- Authorized user can send `/ask hello` and receive a response.
- All requests are logged.

---

## Phase 2 — Codex CLI Tool

### Goal

Jarvis can delegate bounded tasks to Codex CLI.

### Tasks for Codex

1. Implement `tools/codex.py`.
2. Use `subprocess` to run the configured Codex binary.
3. Enforce a working directory allowlist.
4. Add timeout handling.
5. Capture stdout/stderr.
6. Require confirmation before running Codex unless the request is read-only.
7. Implement `/codex <task>`.

### First safe implementation

Codex should initially run in read-only/explanation mode where possible.

Do not allow:

- arbitrary shell commands from Telegram
- workspace outside allowlisted folders
- commands with unbounded runtime
- modification of files without confirmation

### Acceptance criteria

- `/codex summarize this project` runs inside `CODEX_DEFAULT_WORKDIR`.
- Long-running Codex calls timeout cleanly.
- Failed Codex calls return a useful error summary.
- Write-like requests trigger confirmation.

---

## Phase 3 — Local Documents RAG

### Goal

Jarvis can answer questions over local documents.

### Tasks for Codex

1. Implement `scripts/ingest_documents.py`.
2. Support `.txt`, `.md`, `.pdf`, `.docx` initially.
3. Extract text and metadata.
4. Chunk documents.
5. Store chunks in a local vector store.
6. Implement `tools/documents.py`.
7. Implement `/docs <question>`.
8. Return source filenames and short citations.

### Acceptance criteria

- Documents placed in `data/documents/` are indexed.
- `/docs what does the contract say about X?` retrieves relevant chunks.
- Answers include filenames and chunk references.
- If no evidence is found, Jarvis says so.

---

## Phase 4 — Conversation Router

### Goal

Jarvis can route natural language messages to the right tool.

### Tasks for Codex

1. Implement `router.py` with intent classification.
2. Supported intents:
   - general question
   - Codex task
   - document search
   - weather query
   - calendar query
   - browser action
   - home query
3. Keep command mode as fallback.
4. Add tool schemas.
5. Add confidence threshold.
6. Ask for clarification only when truly necessary.

### Acceptance criteria

- “Jarvis, ask Codex to summarize this repo” routes to Codex.
- “Jarvis, search my documents for mortgage” routes to document search.
- “Jarvis, what is my agenda tomorrow?” routes to calendar once implemented.
- Low-confidence intents return a short clarification request.

---

## Phase 5 — Apple Calendar Read-only

### Goal

Jarvis can read calendar information from the Mac.

### Recommended implementation path

Start with AppleScript/JXA called from Python.

Later replace or supplement with a Swift helper using EventKit.

### Tasks for Codex

1. Implement `tools/calendar.py` with a provider abstraction.
2. Implement `AppleScriptCalendarProvider`.
3. Add macOS permission handling notes to README.
4. Implement:
   - `/calendar today`
   - `/calendar tomorrow`
   - `/calendar week`
5. Normalize event output.
6. Do not implement write actions yet.

### Acceptance criteria

- Jarvis can list today's events.
- Jarvis can list tomorrow's events.
- Jarvis handles missing macOS permissions clearly.
- Calendar answers include event time, title, and calendar name.

---

## Phase 6 — WeatherKit Tool

### Goal

Jarvis can answer weather questions for the default location.

### Tasks for Codex

1. Implement `tools/weather.py` with provider interface.
2. Implement WeatherKit JWT generation.
3. Implement WeatherKit REST API client.
4. Add `/weather` command.
5. Add natural language weather routing.
6. Add fallback provider interface, even if no fallback is configured yet.

### Acceptance criteria

- `/weather` returns current conditions for default location.
- “Weather tomorrow morning?” returns a daily/hourly forecast summary.
- If WeatherKit credentials are missing, Jarvis returns a clear setup error.

---

## Phase 7 — Browser Tool

### Goal

Jarvis can open web pages locally on request.

### Tasks for Codex

1. Implement `tools/browser.py` using Playwright or macOS `open` command for first version.
2. Add `/open <url>`.
3. Validate URL scheme: only `https://` and optionally `http://`.
4. Require confirmation for suspicious URLs.
5. Later add Playwright screenshot and extraction.

### Acceptance criteria

- `/open https://example.com` opens the page on the Mac.
- Invalid URLs are rejected.
- Browser actions are logged.

---

## Phase 8 — Hardening and Security

### Goal

Make the assistant safe enough for daily use.

### Tasks for Codex

1. Add rate limits per Telegram user.
2. Add command-level permission checks.
3. Add action confirmations with expiry.
4. Mask secrets in logs.
5. Add startup checks for config and directory permissions.
6. Add test coverage for authorization and confirmation flow.
7. Add a `SAFE_MODE=true` option that disables dangerous tools.

### Acceptance criteria

- Unauthorized user cannot call any tool.
- Dangerous tools cannot run without confirmation.
- Logs do not expose tokens.
- Safe mode disables Codex write actions, browser, and home control.

---

## Phase 9 — Voice via Telegram

### Goal

Jarvis can process Telegram voice messages.

### Tasks for Codex

1. Detect Telegram voice messages.
2. Download voice file.
3. Transcribe audio using selected STT provider.
4. Route transcription like a normal text message.
5. Return text answer first.
6. Optional: return audio response later.

### Acceptance criteria

- User sends a Telegram voice message.
- Jarvis transcribes it.
- Jarvis answers the transcribed request.
- Transcription is included or summarized for transparency.

---

## Phase 10 — Local Voice Assistant

### Goal

Allow talking to Jarvis directly from the Mac.

### Tasks for Codex

1. Implement push-to-talk CLI or small local app.
2. Capture microphone audio.
3. Transcribe audio.
4. Send request to the same backend router.
5. Use TTS for response.
6. Keep this separate from Telegram adapter.

### Acceptance criteria

- User presses a hotkey or runs a command.
- Jarvis listens, transcribes, answers, and speaks back.
- The same tools and permissions are reused.

---

## Phase 11 — Home Status via Home Assistant

### Goal

Jarvis can read smart-home status.

### Recommended approach

Use Home Assistant as the integration layer instead of direct HomeKit control from Python.

### Tasks for Codex

1. Implement `tools/home.py` with provider abstraction.
2. Implement `HomeAssistantProvider`.
3. Add `/home status`.
4. Add `/home devices`.
5. Add read-only entity queries.
6. Do not implement control actions yet.

### Acceptance criteria

- Jarvis lists configured home entities.
- Jarvis can answer “which lights are on?”
- Jarvis can answer “what is the temperature at home?” if sensors exist.

---

## Phase 12 — Home Control with Confirmation

### Goal

Allow limited smart-home control.

### Tasks for Codex

1. Implement explicit service calls through Home Assistant.
2. Start with lights only.
3. Require confirmation for every state-changing action.
4. Add allowlist of controllable entities.
5. Add denylist for risky devices.
6. Add emergency stop command.

### Acceptance criteria

- “Turn on living room light” asks for confirmation.
- After confirmation, Jarvis calls Home Assistant service.
- Unknown or non-allowlisted devices are rejected.
- All actions are logged.

---

## 12. Tool Contracts

### 12.1 Base tool interface

```python
from abc import ABC, abstractmethod
from pydantic import BaseModel

class ToolResult(BaseModel):
    ok: bool
    summary: str
    data: dict | None = None
    error: str | None = None
    requires_confirmation: bool = False
    confirmation_id: str | None = None

class BaseTool(ABC):
    name: str
    description: str

    @abstractmethod
    async def run(self, user_id: str, args: dict) -> ToolResult:
        ...
```

### 12.2 Codex tool arguments

```python
class CodexArgs(BaseModel):
    task: str
    workdir: str | None = None
    mode: str = "read_only"  # read_only | write_allowed
```

### 12.3 Document search arguments

```python
class DocumentSearchArgs(BaseModel):
    question: str
    top_k: int = 5
```

### 12.4 Calendar arguments

```python
class CalendarArgs(BaseModel):
    range: str  # today | tomorrow | week | custom
    start_date: str | None = None
    end_date: str | None = None
```

### 12.5 Weather arguments

```python
class WeatherArgs(BaseModel):
    location_name: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    range: str = "current"  # current | today | tomorrow | week
```

### 12.6 Browser arguments

```python
class BrowserArgs(BaseModel):
    url: str
    action: str = "open"  # open | screenshot | extract_text
```

### 12.7 Home arguments

```python
class HomeArgs(BaseModel):
    action: str  # status | list_devices | turn_on | turn_off
    entity_id: str | None = None
    room: str | None = None
```

---

## 13. Suggested First Codex Prompts

Use these prompts with Codex in order.

### Prompt 1 — Bootstrap

```text
Create the Python project skeleton for Jarvis according to jarvis_ai_assistant_implementation_plan.md. Implement Phase 0 only. Do not implement Telegram, Codex, documents, calendar, weather, browser, voice, or home tools yet. Add tests for config loading and application startup.
```

### Prompt 2 — Telegram MVP

```text
Implement Phase 1 from jarvis_ai_assistant_implementation_plan.md. Add Telegram long polling, allowed-user authorization, /start, /help, /status, and /ask. Keep the LLM service behind an interface so it can be replaced later. Add tests for authorization and command routing.
```

### Prompt 3 — Codex tool

```text
Implement Phase 2. Add a Codex CLI tool using subprocess with workdir allowlisting, timeout, stdout/stderr capture, and confirmation for write-like tasks. Implement /codex and /confirm /cancel flow. Add SQLite persistence for pending confirmations and audit logs.
```

### Prompt 4 — Document RAG

```text
Implement Phase 3. Add document ingestion for txt, md, pdf, and docx files. Create a local vector index and implement /docs. Answers must cite source filenames and chunk IDs. Add tests using small sample documents.
```

### Prompt 5 — Calendar

```text
Implement Phase 5. Add read-only Apple Calendar access using an AppleScript or JXA provider called from Python. Implement /calendar today, /calendar tomorrow, and /calendar week. Handle macOS permission errors clearly.
```

### Prompt 6 — Weather

```text
Implement Phase 6. Add a WeatherKit provider with JWT generation and REST API calls. Implement /weather and natural language routing for basic weather questions. If credentials are missing, return a clear setup message.
```

### Prompt 7 — Browser

```text
Implement Phase 7. Add /open <url>. Start with macOS open command or Playwright. Validate URL scheme, log the action, and require confirmation for suspicious URLs. Do not automate login or credential entry.
```

### Prompt 8 — Home status

```text
Implement Phase 11 read-only smart-home support through Home Assistant. Add /home status and /home devices. Do not implement state-changing actions yet.
```

---

## 14. Security Checklist

Before using Jarvis daily, verify:

- Telegram bot token is not committed.
- `.env` is ignored by Git.
- Allowed Telegram user ID is configured.
- Codex workdirs are allowlisted.
- Codex write actions require confirmation.
- Browser tool rejects invalid URLs.
- Calendar is read-only.
- WeatherKit private key is stored outside the repo.
- Home Assistant token is stored outside the repo.
- Logs do not contain secrets.
- SQLite database has local filesystem permissions only for the current user.
- There is a `SAFE_MODE` or equivalent emergency disable switch.

---

## 15. Definition of Done for MVP

The MVP is complete when:

1. Jarvis runs locally on macOS.
2. Telegram bot responds only to the authorized user.
3. `/ask` works.
4. `/codex` can run a bounded Codex task in an allowlisted workspace.
5. `/docs` answers questions over indexed local documents.
6. All actions are logged.
7. Dangerous actions require confirmation.
8. Setup steps are documented in `README.md`.
9. Tests cover config, authorization, routing, and at least one tool.

---

## 16. Recommended Delivery Order

Build in this exact order:

1. Phase 0 — Project bootstrap
2. Phase 1 — Telegram MVP
3. Phase 2 — Codex CLI integration
4. Phase 3 — Document RAG
5. Phase 8 — Security hardening, first pass
6. Phase 5 — Apple Calendar read-only
7. Phase 6 — WeatherKit
8. Phase 7 — Browser open URL
9. Phase 4 — Natural language router refinement
10. Phase 9 — Telegram voice messages
11. Phase 11 — Home Assistant read-only
12. Phase 12 — Home control with confirmation
13. Phase 10 — Local voice assistant

Reason: Telegram + Codex + documents form the useful core. Calendar, weather, browser, voice, and home control are valuable but should not delay the private assistant MVP.

---

## 17. External Documentation References

Use these as implementation references:

- OpenAI Codex CLI: https://developers.openai.com/codex/cli
- OpenAI Codex CLI reference: https://developers.openai.com/codex/cli/reference
- OpenAI Codex configuration: https://developers.openai.com/codex/config-basic
- Telegram Bot API: https://core.telegram.org/bots/api
- Apple WeatherKit: https://developer.apple.com/weatherkit/
- Apple WeatherKit REST API: https://developer.apple.com/documentation/weatherkitrestapi/
- Apple EventKit: https://developer.apple.com/documentation/eventkit
- Apple HomeKit: https://developer.apple.com/documentation/homekit/
- Playwright Python: https://playwright.dev/python/docs/api/class-browser
- Home Assistant HomeKit Controller: https://www.home-assistant.io/integrations/homekit_controller/
- Home Assistant HomeKit Bridge: https://www.home-assistant.io/integrations/homekit/

---

## 18. Important Design Notes

### 18.1 Codex is a tool, not the whole assistant

Jarvis should not simply forward every Telegram message to Codex. Codex is best used for:

- modifying code
- inspecting repositories
- writing scripts
- analyzing local project files
- implementing tasks

Normal conversation, calendar, weather, document search, browser, and home automation should be handled by Jarvis tools directly.

### 18.2 HomeKit is the hardest integration

Apple HomeKit is secure and intentionally controlled. Direct Python control of the Apple Home graph is not the best MVP path. For practical implementation, use Home Assistant as the interoperability layer, then connect Jarvis to Home Assistant.

### 18.3 Browser automation should stay constrained

Opening a page is safe. Driving logged-in websites or entering credentials is not an MVP feature. Add browser automation only after the confirmation, audit, and permission layers are solid.

### 18.4 Voice should reuse the same backend

Do not build a separate voice assistant brain. Voice should be another adapter, like Telegram. The central router and tools should remain shared.

---

## 19. First Milestone Target

The first milestone should be:

```text
Jarvis v0.1
- local Python backend
- Telegram long polling
- authorized user only
- /ask
- /status
- /codex with confirmation
- basic audit logs
```

After v0.1, add documents and make it useful as a personal assistant.

