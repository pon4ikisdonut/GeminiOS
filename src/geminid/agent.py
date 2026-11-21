#!/usr/bin/env python3
"""
GeminiOS System Agent Engine (`agent.py`)
Allows Gemini to plan and execute system administration tasks with risk
classification, interactive user confirmation, and full audit logging.
"""

import datetime
import json
import re
import subprocess
from pathlib import Path
from typing import Dict, List

AGENT_SYSTEM_PROMPT = """You are the GeminiOS System Agent running on GeminiOS 1.0 (Linux, KDE Plasma 6, `gem` package manager with optional Arch/AUR bridge).
Given the user's goal, respond ONLY with valid JSON matching this schema:
{
  "summary": "1-sentence plan explanation",
  "steps": [
    {"cmd": "shell command to execute", "reason": "why this step is needed"}
  ]
}
Keep commands minimal, idiomatic for Linux/GeminiOS, and never include markdown code fences around the JSON."""

DESTRUCTIVE_PATTERNS = [
    r"\brm\s+-[a-zA-Z]*r[a-zA-Z]*f[a-zA-Z]*\s+/(\s|$|\*)",
    r"\brm\s+-[a-zA-Z]*f[a-zA-Z]*r[a-zA-Z]*\s+/(\s|$|\*)",
    r"\bmkfs\b",
    r"\bdd\s+if=",
    r":\(\)\s*\{\s*:\|:\s*&\s*\};:",
    r"\bshred\b",
    r">\s*/dev/sd[a-z]",
    r">\s*/dev/nvme",
]

ELEVATED_PATTERNS = [
    r"^\s*sudo\b",
    r"\bsystemctl\s+(start|stop|restart|enable|disable|mask)\b",
    r"\bgem\s+(install|remove|repo)\b",
    r"\bpacman\s+-[SRU]",
    r"\bchmod\b|\bchown\b|\busermod\b|\buseradd\b",
    r"\biptables\b|\bnft\b|\bufw\b",
]


def classify_risk(cmd: str) -> str:
    for pat in DESTRUCTIVE_PATTERNS:
        if re.search(pat, cmd):
            return "destructive"
    for pat in ELEVATED_PATTERNS:
        if re.search(pat, cmd):
            return "elevated"
    return "safe"


def extract_json_plan(raw_text: str) -> Dict:
    cleaned = raw_text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if not match:
            return {"summary": "Could not parse structured plan", "steps": [], "raw": raw_text}
        data = json.loads(match.group(0))

    steps = []
    for step in data.get("steps", []):
        cmd = str(step.get("cmd", "")).strip()
        if not cmd:
            continue
        steps.append({
            "cmd": cmd,
            "reason": str(step.get("reason", "")),
            "risk": classify_risk(cmd),
        })
    return {
        "summary": str(data.get("summary", "Agent execution plan")),
        "steps": steps,
    }


def write_audit_entry(audit_log: Path, cmd: str, risk: str, returncode: int, stdout: str, stderr: str) -> None:
    try:
        audit_log.parent.mkdir(parents=True, exist_ok=True)
        entry = {
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "cmd": cmd,
            "risk": risk,
            "returncode": returncode,
            "stdout_preview": stdout[:300],
            "stderr_preview": stderr[:300],
        }
        with audit_log.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry) + "\n")
    except Exception:
        pass


def execute_step(cmd: str, audit_log: Path, allow_destructive: bool = False) -> Dict:
    risk = classify_risk(cmd)
    if risk == "destructive" and not allow_destructive:
        return {
            "ok": False,
            "risk": risk,
            "returncode": -1,
            "stdout": "",
            "stderr": "Blocked: destructive command is disallowed by /etc/geminid/geminid.conf.",
        }
    proc = subprocess.run(
        ["/bin/bash", "-c", cmd],
        capture_output=True,
        text=True,
        timeout=120,
    )
    write_audit_entry(audit_log, cmd, risk, proc.returncode, proc.stdout, proc.stderr)
    return {
        "ok": proc.returncode == 0,
        "risk": risk,
        "returncode": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
    }
