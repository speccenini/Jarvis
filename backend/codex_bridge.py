import os
import asyncio
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

JARVIS_WORKSPACE = Path(os.getenv("JARVIS_WORKSPACE", "~/JarvisWorkspace")).expanduser()
CODEX_WORKSPACE = JARVIS_WORKSPACE / "workspace"
CODEX_TIMEOUT_SECONDS = int(os.getenv("CODEX_TIMEOUT_SECONDS", "180"))


class CodexError(Exception):
    pass


async def run_codex(prompt: str) -> str:
    if not CODEX_WORKSPACE.exists():
        raise CodexError(f"Codex workspace does not exist: {CODEX_WORKSPACE}")

    safe_prompt = f"""
You are called by Jarvis from a Telegram backend.

Rules:
- Answer in plain text.
- Do not open an interactive UI.
- Do not ask questions unless absolutely necessary.
- Work only inside this directory: {CODEX_WORKSPACE}
- For now, do not modify files.
- If the user asks what files you see, list the files in the current workspace.

User request:
{prompt}
"""

    command = [
        "codex",
        "exec",
        "--cd",
        str(CODEX_WORKSPACE),
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
            cwd=str(CODEX_WORKSPACE),
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

    # utile per debug locale
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