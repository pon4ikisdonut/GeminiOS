#!/usr/bin/env python3
"""
GeminiOS Clipboard AI (`gemini-clip`)
Bound to Super+Shift+G: reads current clipboard text and opens GeminiOS Spotlight
to immediately explain, translate, or debug it.
"""

import shutil
import subprocess
import sys


def get_clipboard() -> str:
    for cmd in (["wl-paste", "-n"], ["xclip", "-o", "-selection", "clipboard"]):
        if shutil.which(cmd[0]):
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=3)
            if proc.returncode == 0 and proc.stdout.strip():
                return proc.stdout.strip()
    return ""


def main() -> int:
    clip = get_clipboard()
    if not clip:
        subprocess.run(["notify-send", "GeminiOS Clipboard AI", "Clipboard is empty."], check=False)
        return 0
    prompt = f"Explain, summarize, or fix this clipboard snippet concisely:\n{clip[:4000]}"
    subprocess.Popen(["/usr/bin/gemini-overlay", "--prompt", prompt])
    return 0


if __name__ == "__main__":
    sys.exit(main())
