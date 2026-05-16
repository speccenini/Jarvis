import asyncio
import json
from pathlib import Path
from dotenv import load_dotenv

from config import Config

load_dotenv()

JARVIS_WORKSPACE = Config.JARVIS_WORKSPACE
CODEX_WORKSPACE = JARVIS_WORKSPACE / "workspace"
CODEX_TIMEOUT_SECONDS = Config.CODEX_TIMEOUT_SECONDS


class CodexError(Exception):
    pass


async def run_codex(prompt: str) -> str:
    if not CODEX_WORKSPACE.exists():
        raise CodexError(f"Codex workspace does not exist: {CODEX_WORKSPACE}")

    allowed_roots = sorted(
        set(Config.allowed_filesystem_roots(access="read")) | {CODEX_WORKSPACE.resolve()}
    )
    workspace_aliases = _ensure_workspace_symlinks(allowed_roots)
    allowed_roots_text = "\n".join(f"  - {path}" for path in allowed_roots)
    allowed_roots_context = _build_allowed_roots_context(allowed_roots)
    workspace_aliases_text = _format_workspace_aliases(workspace_aliases)
    codex_guidance = _load_codex_guidance()

    safe_prompt = f"""
You are called by Jarvis from a Telegram backend.

Rules:
- Answer in plain text.
- Do not open an interactive UI.
- Do not ask questions unless absolutely necessary.
- Your default working directory is: {CODEX_WORKSPACE}
- You may read files only inside these allowlisted roots:
{allowed_roots_text}
- The default workspace contains these symlink aliases to allowlisted roots:
{workspace_aliases_text}
- Do not read files outside the allowlisted roots.
- For now, do not modify files.
- If the user asks what files you see, list files from the relevant allowlisted root or its workspace symlink alias.
- Do not answer that the workspace is empty unless the user specifically asks only about the default workspace.
- If the request mentions taxes/tasse, invoices, house/casa, home, or documents, inspect the matching allowlisted root or symlink alias before answering that files are missing.
- If a root name below matches the request, use that path directly.

Allowlisted filesystem roots and visible top-level entries:
{allowed_roots_context}

User-specific working guide:
{codex_guidance}

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
    ]

    for root in allowed_roots:
        if root != CODEX_WORKSPACE.resolve():
            command.extend(["--add-dir", str(root)])

    command.append(safe_prompt)

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


def _build_allowed_roots_context(allowed_roots: list[Path]) -> str:
    named_roots = _load_allowlist_names()
    blocks = []

    for root in allowed_roots:
        name = named_roots.get(root, root.name or str(root))
        entries = _list_root_entries(root)
        entries_text = "\n".join(f"    - {entry}" for entry in entries)
        if not entries_text:
            entries_text = "    - <no visible entries>"

        blocks.append(f"  - {name}: {root}\n{entries_text}")

    return "\n".join(blocks)


def _ensure_workspace_symlinks(allowed_roots: list[Path]) -> dict[str, Path]:
    named_roots = _load_allowlist_names()
    aliases = {}

    for root in allowed_roots:
        resolved_root = root.resolve()
        if resolved_root == CODEX_WORKSPACE.resolve():
            continue

        alias_name = _safe_alias_name(named_roots.get(resolved_root, resolved_root.name))
        if not alias_name:
            continue

        alias_path = CODEX_WORKSPACE / alias_name
        if alias_path.exists() or alias_path.is_symlink():
            try:
                if alias_path.resolve() == resolved_root:
                    aliases[alias_name] = resolved_root
                    continue
            except OSError:
                continue

            numbered_alias_path = _next_available_alias_path(alias_name)
            if not numbered_alias_path:
                continue
            alias_path = numbered_alias_path
            alias_name = alias_path.name

        try:
            alias_path.symlink_to(resolved_root, target_is_directory=True)
            aliases[alias_name] = resolved_root
        except OSError:
            continue

    return aliases


def _safe_alias_name(name: str) -> str:
    safe = "".join(
        character.lower() if character.isalnum() else "_"
        for character in str(name).strip()
    )
    return "_".join(part for part in safe.split("_") if part)


def _next_available_alias_path(alias_name: str, limit: int = 20) -> Path | None:
    for index in range(2, limit + 1):
        candidate = CODEX_WORKSPACE / f"{alias_name}_{index}"
        if not candidate.exists() and not candidate.is_symlink():
            return candidate
    return None


def _format_workspace_aliases(aliases: dict[str, Path]) -> str:
    if not aliases:
        return "  - <no aliases available>"

    return "\n".join(
        f"  - {alias_name}/ -> {target}"
        for alias_name, target in sorted(aliases.items())
    )


def _load_codex_guidance(max_chars: int = 6000) -> str:
    guide_file = Config.CODEX_GUIDE_FILE
    if not guide_file.exists():
        return "- No user-specific guide has been created yet."

    try:
        content = guide_file.read_text(encoding="utf-8").strip()
    except OSError:
        return "- User-specific guide exists but could not be read."

    if not content:
        return "- User-specific guide is empty."

    return content[-max_chars:]


def _load_allowlist_names() -> dict[Path, str]:
    if not Config.FILESYSTEM_ALLOWLIST_FILE.exists():
        return {}

    try:
        with open(Config.FILESYSTEM_ALLOWLIST_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}

    names = {}
    for entry in data.get("allowed_roots", []):
        if not isinstance(entry, dict) or not entry.get("path"):
            continue

        try:
            path = Path(entry["path"]).expanduser().resolve()
        except (OSError, RuntimeError):
            continue

        name = entry.get("name") or path.name
        names[path] = str(name)

    return names


def _list_root_entries(root: Path, limit: int = 40) -> list[str]:
    try:
        entries = sorted(
            root.iterdir(),
            key=lambda item: (not item.is_dir(), item.name.lower()),
        )
    except OSError:
        return ["<not readable by Jarvis process>"]

    visible_entries = []
    for entry in entries:
        if entry.name.startswith("."):
            continue

        suffix = "/" if entry.is_dir() else ""
        visible_entries.append(f"{entry.name}{suffix}")

        if len(visible_entries) >= limit:
            remaining = len(entries) - limit
            if remaining > 0:
                visible_entries.append(f"... {remaining} more entries")
            break

    return visible_entries
