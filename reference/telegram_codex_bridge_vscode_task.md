# Implement Telegram → Jarvis Backend → Codex CLI in VS Code

## Goal

Implement the missing bridge so that when I write this in Telegram:

```text
/codex che file vedi in questa directory?
```

the response appears **in Telegram**, not only in the local Codex console.

Architecture:

```text
Telegram Bot
  ↓
jarvis_telegram.py
  ↓
codex_bridge.py
  ↓
codex exec
  ↓
stdout captured by Python
  ↓
Telegram reply
```

---

## Important rule

Do **not** call interactive Codex with:

```bash
codex
```

The backend must call Codex in non-interactive mode:

```bash
codex exec "prompt"
```

Codex `exec` writes the result to `stdout`, so Python can capture it and send it back to Telegram.

---

## Files to create or modify

### 1. `.env`

Ensure these values exist:

```env
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
AUTHORIZED_TELEGRAM_USER_ID=your_telegram_user_id
JARVIS_WORKSPACE=/Users/stefano/JarvisWorkspace
CODEX_TIMEOUT_SECONDS=180
```

The `.env` file must be ignored by Git.

---

### 2. `codex_bridge.py`

Create this file:

```python
import os
import asyncio
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

JARVIS_WORKSPACE = Path(os.getenv("JARVIS_WORKSPACE", "~/JarvisWorkspace")).expanduser()
CODEX_TIMEOUT_SECONDS = int(os.getenv("CODEX_TIMEOUT_SECONDS", "180"))


class CodexError(Exception):
    pass


async def run_codex(prompt: str) -> str:
    if not JARVIS_WORKSPACE.exists():
        raise CodexError(f"Workspace does not exist: {JARVIS_WORKSPACE}")

    safe_prompt = f"""
You are called by Jarvis from a Telegram backend.

Rules:
- Answer in plain text.
- Do not open an interactive UI.
- Do not ask questions unless absolutely necessary.
- Work only inside this directory: {JARVIS_WORKSPACE}
- For now, do not modify files.
- If the user asks what files you see, list the files in the current workspace.

User request:
{prompt}
"""

    command = [
        "codex",
        "exec",
        "--cd",
        str(JARVIS_WORKSPACE),
        "--color",
        "never",
        "--sandbox",
        "read-only",
        "--skip-git-repo-check",
        safe_prompt,
    ]

    try:
        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(JARVIS_WORKSPACE),
        )

        stdout, stderr = await asyncio.wait_for(
            process.communicate(),
            timeout=CODEX_TIMEOUT_SECONDS,
        )

    except asyncio.TimeoutError:
        process.kill()
        raise CodexError("Codex execution timed out.")

    out = stdout.decode("utf-8", errors="replace").strip()
    err = stderr.decode("utf-8", errors="replace").strip()

    print("=== CODEX STDOUT ===")
    print(out)
    print("=== CODEX STDERR ===")
    print(err)

    if process.returncode != 0:
        raise CodexError(err or f"Codex failed with exit code {process.returncode}")

    if not out:
        if err:
            return f"Codex produced no stdout. stderr was:\n{err[-3000:]}"
        return "Codex completed but produced no output."

    return out[-3900:]
```

---

### 3. `jarvis_telegram.py`

Import the bridge:

```python
from codex_bridge import run_codex, CodexError
```

Inside `handle_message()`, add or replace the `/codex` block:

```python
if text.lower().startswith("/codex "):
    prompt = text[len("/codex "):].strip()

    if not prompt:
        await update.message.reply_text("Scrivi un prompt dopo /codex.")
        return

    try:
        result = await run_codex(prompt)
        await update.message.reply_text(result[:4000])
    except CodexError as e:
        await update.message.reply_text(f"Errore Codex: {e}")

    return
```

Keep the existing Telegram user whitelist check before this block.

---

## Local test from terminal

Before testing Telegram, run:

```bash
cd /Users/stefano/JarvisWorkspace
codex exec --cd /Users/stefano/JarvisWorkspace "che file vedi in questa directory?"
```

Expected result:

- output appears directly in the terminal
- no interactive Codex TUI opens

---

## Telegram test

Start the backend:

```bash
cd /path/to/jarvis-project
source .venv/bin/activate
python jarvis_telegram.py
```

Then send this to the Telegram bot:

```text
/codex che file vedi in questa directory?
```

Expected result:

- Codex runs locally
- Python captures stdout
- Telegram receives the answer

---

## Acceptance criteria

The implementation is correct when:

1. `/codex ...` does not open an interactive Codex session.
2. Codex is invoked through `codex exec`.
3. The Python backend captures `stdout`.
4. The final answer is sent back to Telegram.
5. Codex runs only inside `JARVIS_WORKSPACE`.
6. Sandbox mode is `read-only` for the first version.
7. Unauthorized Telegram users receive `Access denied`.

---

## Security notes

Do not use:

```bash
codex --dangerously-bypass-approvals-and-sandbox
```

Do not give Codex access to the full filesystem.

Start with:

```bash
--sandbox read-only
```

Later, if file modification is needed, add a separate explicit command such as:

```text
/codex-write ...
```

with confirmation before execution.
