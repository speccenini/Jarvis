# Jarvis Backend - Core Component

This is the minimal backend component of Jarvis that runs always-on and connects to Telegram.

## Architecture

```
Telegram Messages
        ↓
    run_backend.py (launcher)
        ↓
    jarvis_core.py (orchestrator & message router)
        ↓
    +-- audit_logger.py (action logging)
    +-- user_auth.py (authorization)
    +-- tools_registry.py (tool discovery & execution)
    +-- codex_bridge.py (Codex CLI wrapper)
    +-- config.py (centralized configuration)
```

## Quick Start

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure .env (already done)

Your `.env` file should have:
```env
TELEGRAM_BOT_TOKEN=your_token
AUTHORIZED_TELEGRAM_USER_ID=your_user_id
JARVIS_WORKSPACE=/Users/stef/Documents/Jarvis
CODEX_TIMEOUT_SECONDS=120
```

Optional Home/HomeKit integration:

```env
# disabled | shortcut | homeassistant
HOME_PROVIDER=disabled

# For HOME_PROVIDER=shortcut
HOMEKIT_STATUS_SHORTCUT=Jarvis Home Status

# For HOME_PROVIDER=homeassistant
HOME_ASSISTANT_URL=http://homeassistant.local:8123
HOME_ASSISTANT_TOKEN=your_long_lived_access_token
HOME_TIMEOUT_SECONDS=20
```

Optional document RAG configuration:

```env
DOCUMENTS_PDF_DIR=/Users/stef/Documents/Jarvis/data/documents/pdf
DOCUMENTS_TEXT_DIR=/Users/stef/Documents/Jarvis/data/documents/text
DOCUMENTS_CHROMA_DIR=/Users/stef/Documents/Jarvis/data/documents/chroma
DOCUMENTS_METADATA_DB=/Users/stef/Documents/Jarvis/data/documents/metadata.sqlite
DOCUMENTS_TOP_K=6

# auto uses OpenAI embeddings if OPENAI_API_KEY exists, otherwise local hashing
EMBEDDING_PROVIDER=auto
OPENAI_API_KEY=
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
```

Telegram access is controlled by `backend/telegram_whitelist.json`:

```json
{
  "authorized_user_ids": [
    123456789
  ]
}
```

The real whitelist file is local-only and ignored by Git. A template is tracked
as `backend/telegram_whitelist.example.json`. If the whitelist file is missing,
Jarvis falls back to `AUTHORIZED_TELEGRAM_USER_ID` from `.env`.

Filesystem access is controlled by `backend/filesystem_allowlist.json`:

```json
{
  "allowed_roots": [
    {
      "name": "jarvis_workspace",
      "path": "/Users/stef/Documents/Jarvis/data/workspace",
      "read": true,
      "write": false
    }
  ]
}
```

The real filesystem allowlist is local-only and ignored by Git. A template is
tracked as `backend/filesystem_allowlist.example.json`. If the file is missing,
Jarvis falls back to `JARVIS_WORKSPACE` only.

### 3. Manage the backend service

From the repository root:

```bash
./jarvis start
./jarvis stop
./jarvis restart
./jarvis status
./jarvis logs
./jarvis calendar-auth
```

The script starts `backend/run_backend.py` in the background, stores the PID in
`data/run/jarvis.pid`, and writes output to `data/logs/jarvis_backend.out`.

### 4. Run the backend manually

```bash
python run_backend.py
```

Or directly:

```bash
python jarvis_core.py
```

The backend will start in polling mode and wait for Telegram messages.

## Available Commands

Once running, you can send these commands via Telegram:

- `/start` - Initialize connection
- `/health` - Check if backend is running
- `/pexhelp` - Show available help topics
- `/pexhelp <tool>` - Show usage for one tool, for example `/pexhelp tools`
- `/tools` - List available tools
- `/codex <prompt>` - Run a Codex query
- `/guide <instruction>` - Add persistent working guidance for Codex
- `/docs index` - Index local PDF documents
- `/docs status` - Show document index status
- `/docs search <query>` - Search indexed document chunks
- `/docs <question>` - Answer a question using indexed document chunks
- `/calendar oggi` - List today's Apple Calendar events
- `/calendar domani` - List tomorrow's Apple Calendar events
- `/calendar settimana` - List Apple Calendar events for the next 7 days
- `/home status` - Read smart-home status
- `/home devices` - List Home Assistant entities/devices
- Any text message - Echo response (more tools coming soon)

You can also ask naturally in Telegram:

```text
Che appuntamenti ho domani?
Che riunioni ho questa settimana?
Mostrami la mia agenda oggi.
```

Codex guidance is stored locally in `data/documents/codex_guidance.md` and is
included in every `/codex` request. Use it for folder-specific habits, for
example:

```text
/guide Quando chiedo quanto ho pagato di tasse, esamina sempre Steuererklärung*.pdf nella cartella tasse dell'anno richiesto.
```

## Local HTTP API

The web server exposes local-only API endpoints on `http://localhost:8000`.

Document RAG endpoints:

```bash
curl http://localhost:8000/api/documents/status
curl -X POST http://localhost:8000/api/documents/index
curl -X POST http://localhost:8000/api/documents/search \
  -H "Content-Type: application/json" \
  -d '{"query":"tasse 2025"}'
```

Command-line document indexing and search:

```bash
python backend/scripts/index_documents.py
python backend/scripts/query_documents.py "tasse 2025"
```

Apple Calendar access is read-only:

```bash
curl http://localhost:8000/api/calendar/today
curl http://localhost:8000/api/calendar/tomorrow
curl http://localhost:8000/api/calendar/week
curl "http://localhost:8000/api/calendar/events?start=2026-05-13&end=2026-05-14"
```

The first Calendar request may trigger a macOS privacy permission prompt for
Terminal or the Python runner. Grant Calendar/Automation access in System
Settings if macOS blocks the request.

If Telegram shows Calendar error `-1743`, macOS denied Apple Events access.
Open System Settings > Privacy & Security and check:

- Automation: allow Terminal/Python to control Calendar.
- Calendars: allow Terminal/Python if it appears there.

Then restart Jarvis:

```bash
./jarvis calendar-auth
./jarvis restart
```

## Home / HomeKit

Direct HomeKit access from Python is limited. Jarvis supports two read-only
providers:

- `HOME_PROVIDER=shortcut`: runs a macOS Shortcut, default name
  `Jarvis Home Status`, and returns the shortcut output to Telegram.
- `HOME_PROVIDER=homeassistant`: calls Home Assistant REST API using
  `HOME_ASSISTANT_URL` and `HOME_ASSISTANT_TOKEN`.

Supported Telegram commands:

```text
/home status
/home devices
```

No device-control actions are implemented yet.

## Core Components

### jarvis_core.py
Main orchestrator that:
- Initializes all subcomponents
- Routes Telegram messages to appropriate handlers
- Manages conversation flow

### audit_logger.py
Logs all actions to `logs/` directory:
- `audit.log` - All user actions
- `unauthorized.log` - Unauthorized access attempts
- `errors.log` - Error events

### user_auth.py
Simple authorization layer:
- Whitelist of authorized user IDs
- Check permissions before executing tools

### tools_registry.py
Tool registry for extensibility:
- Register new tools easily
- Query available tools
- Execute tools with consistent interface

### config.py
Centralized configuration:
- Load from .env
- Validate on startup
- Accessible throughout the app

### codex_bridge.py (existing)
Wrapper around Codex CLI:
- Execute Codex in constrained environment
- Timeout handling
- Safe prompt injection

## Next Steps

1. ✅ Create core backend (done)
2. 🔜 Add document RAG tool
3. 🔜 Add Apple Calendar tool
4. 🔜 Add Weather tool
5. 🔜 Add browser automation tool
6. 🔜 Add voice interaction

## Logs Location

All logs are stored in: `{JARVIS_WORKSPACE}/logs/`

- Check `audit.log` to see action history
- Check `errors.log` for failures
- Check `unauthorized.log` for access attempts

## Development

### Adding a New Tool

1. Create a new module in `backend/tools/my_tool.py`
2. Implement your tool logic
3. Register it in `jarvis_core.py` during initialization
4. Add handler method in `JarvisCore` class
5. Add command handler in `build_telegram_app()`

Example:

```python
async def handle_my_tool(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
    # ... your logic
    result = await my_tool_function()
    await update.message.reply_text(result)
```

### Testing Tools

```python
# Quick test without Telegram
python -c "
import asyncio
from codex_bridge import run_codex
result = asyncio.run(run_codex('list files'))
print(result)
"
```

## Troubleshooting

### Backend won't start
- Check `.env` has valid `TELEGRAM_BOT_TOKEN`
- Verify workspace path exists
- Check Python version (3.11+)

### No response from Telegram
- Backend must be running (`python run_backend.py`)
- Check `logs/audit.log` for errors
- Verify user ID matches `AUTHORIZED_TELEGRAM_USER_ID`

### Codex errors
- Ensure Codex CLI is installed: `which codex`
- Check `CODEX_TIMEOUT_SECONDS` is reasonable
- Verify workspace path is accessible

---

**Status**: MVP complete. Ready for tool expansion.
