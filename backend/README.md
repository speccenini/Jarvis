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

### 3. Run the backend

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
- `/tools` - List available tools
- `/codex <prompt>` - Run a Codex query
- Any text message - Echo response (more tools coming soon)

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
