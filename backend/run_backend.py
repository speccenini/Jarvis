#!/usr/bin/env python3
"""
Jarvis Backend Launcher
Quick start script to run the Jarvis backend.
"""

import sys
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent
sys.path.insert(0, str(backend_path))

from jarvis_core import JarvisCore

if __name__ == "__main__":
    try:
        core = JarvisCore()
        core.run()
    except KeyboardInterrupt:
        print("\n✋ Jarvis backend stopped.")
    except Exception as e:
        print(f"\n❌ Error starting Jarvis backend: {e}")
        sys.exit(1)
