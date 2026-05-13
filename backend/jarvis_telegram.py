#!/usr/bin/env python3
"""
Compatibility entrypoint for the Telegram backend.

The canonical implementation lives in jarvis_core.py. Keep this wrapper so
older docs and local commands that run `python jarvis_telegram.py` still start
the same backend instead of a second partial Telegram bot.
"""

from jarvis_core import JarvisCore


def main():
    core = JarvisCore()
    core.run()


if __name__ == "__main__":
    main()
