#!/usr/bin/env python3
"""
GeminiOS System Health Watcher (`system_watcher.py`)
Monitors systemd failed units in the background and alerts the user via
desktop notifications with Gemini Doctor suggestions.
"""

import shutil
import subprocess
import sys
import time


def get_failed_units() -> set:
    try:
        proc = subprocess.run(
            ["systemctl", "--failed", "--no-legend", "--plain"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        units = set()
        for line in proc.stdout.splitlines():
            parts = line.split()
            if parts:
                units.add(parts[0])
        return units
    except Exception:
        return set()


def main() -> int:
    seen = set()
    while True:
        failed = get_failed_units()
        new_failures = failed - seen
        if new_failures and shutil.which("notify-send"):
            names = ", ".join(sorted(new_failures))
            subprocess.run(
                [
                    "notify-send",
                    "-u", "normal",
                    "GeminiOS AI System Guard",
                    f"Failed service detected: {names}. Run `gemini-doctor --fix` or press Super+G.",
                ],
                check=False,
            )
        seen = failed
        time.sleep(30)
    return 0


if __name__ == "__main__":
    sys.exit(main())
