#!/usr/bin/env python3
"""
GeminiOS System Doctor (`gemini-doctor`)
Inspects systemd failed units, recent journald errors, disk/memory pressure,
and asks geminid for root-cause analysis and optional agent auto-remediation.
"""

import argparse
import json
import subprocess
import sys
import urllib.request

GEMINID_URL = "http://127.0.0.1:11435"


def collect_diagnostics() -> str:
    sections = []
    cmds = [
        ("Failed Systemd Units", ["systemctl", "--failed", "--no-pager"]),
        ("Recent Journal Errors", ["journalctl", "-p", "err", "-n", "30", "--no-pager"]),
        ("Disk Usage", ["df", "-h", "/"]),
        ("Memory Usage", ["free", "-h"]),
    ]
    for title, cmd in cmds:
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            out = (proc.stdout or proc.stderr).strip()
        except Exception as exc:
            out = f"(unavailable: {exc})"
        sections.append(f"=== {title} ===\n{out[:3000]}")
    return "\n\n".join(sections)


def main() -> int:
    parser = argparse.ArgumentParser(description="GeminiOS AI System Doctor")
    parser.add_argument("--fix", action="store_true", help="Propose executable fixes via Gemini Agent Mode")
    args = parser.parse_args()

    print("[gemini-doctor] Collecting system diagnostics...")
    diag = collect_diagnostics()
    prompt = (
        "Analyze these GeminiOS system diagnostics. List concrete issues (if any) "
        "and exact commands to fix them:\n\n" + diag
    )

    if args.fix:
        return subprocess.run(["gemini", "--agent", prompt]).returncode

    req = urllib.request.Request(
        f"{GEMINID_URL}/v1/chat",
        data=json.dumps({"prompt": prompt, "prefer": "auto"}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        print(f"\n[Gemini Doctor — {data.get('backend')}]\n{data.get('response', '')}\n")
        return 0
    except Exception as exc:
        print(f"[gemini-doctor] Diagnostics collected, but geminid is unreachable: {exc}", file=sys.stderr)
        print(diag)
        return 1


if __name__ == "__main__":
    sys.exit(main())
