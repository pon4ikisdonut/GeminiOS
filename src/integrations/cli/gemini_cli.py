#!/usr/bin/env python3
"""
GeminiOS CLI Assistant (`gemini` / `ask`)
Supports direct Q&A, stdin piping, Agent Mode with interactive confirmation,
cloud/local backend selection, API key configuration, and Gemma setup.
"""

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

GEMINID_URL = os.environ.get("GEMINID_URL", "http://127.0.0.1:11435")


def api_request(path: str, payload: dict = None) -> dict:
    url = f"{GEMINID_URL}{path}"
    if payload is not None:
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
    else:
        req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="ignore")
        try:
            return json.loads(raw)
        except Exception:
            return {"ok": False, "response": f"HTTP {exc.code}: {raw}"}
    except Exception as exc:
        return {"ok": False, "response": f"Cannot connect to geminid at {GEMINID_URL}: {exc}"}


def format_terminal_output(text: str) -> str:
    """
    Cleans markdown formatting for the terminal console:
    - Removes all bold/italic markdown asterisks (**word**, *word*)
    - Converts markdown bullet lists (* item, - item) to clean bullets (• item)
    - Formats headers cleanly without hashes (# Header -> Header)
    - Strips any remaining stray asterisks
    - Formats inline code and code blocks cleanly
    """
    if not text:
        return ""

    is_tty = sys.stdout.isatty()
    bold_code = "\033[1m" if is_tty else ""
    cyan_code = "\033[38;5;153m" if is_tty else ""
    blue_code = "\033[1;34m" if is_tty else ""
    reset_code = "\033[0m" if is_tty else ""

    lines = []
    in_code_block = False

    for line in text.splitlines():
        if line.strip().startswith("```"):
            in_code_block = not in_code_block
            continue

        if in_code_block:
            lines.append(f"    {line}")
            continue

        # Headers: # Header -> Header
        header_match = re.match(r"^(?:#{1,6}\s+)(.+)$", line)
        if header_match:
            title = header_match.group(1).strip()
            title = title.replace("**", "").replace("*", "").replace("#", "")
            lines.append(f"{blue_code}{title}{reset_code}")
            continue

        # Bullet points: * item or - item -> • item
        bullet_match = re.match(r"^(\s*)[\*\-]\s+(.+)$", line)
        if bullet_match:
            indent = bullet_match.group(1)
            item_text = bullet_match.group(2)
            item_text = re.sub(r"\*\*(.+?)\*\*", rf"{bold_code}\1{reset_code}", item_text)
            item_text = re.sub(r"(?<!\*)\*([^\*\n]+?)\*(?!\*)", r"\1", item_text)
            item_text = re.sub(r"`([^`\n]+?)`", rf"{cyan_code}\1{reset_code}", item_text)
            item_text = item_text.replace("**", "").replace("*", "").replace("#", "")
            lines.append(f"{indent}• {item_text}")
            continue

        # Regular lines: replace headers, bold, italic, code
        processed = re.sub(r"(?:^|\s)#{1,6}\s+", " ", line)
        processed = re.sub(r"\*\*(.+?)\*\*", rf"{bold_code}\1{reset_code}", processed)
        processed = re.sub(r"(?<!\*)\*([^\*\n]+?)\*(?!\*)", r"\1", processed)
        processed = re.sub(r"`([^`\n]+?)`", rf"{cyan_code}\1{reset_code}", processed)
        processed = processed.replace("**", "").replace("*", "")
        lines.append(processed)

    return "\n".join(lines).strip()


def run_agent(goal: str, prefer: str) -> int:
    print(f"[Gemini Agent] Planning task: {goal} ...")
    res = api_request("/v1/agent/plan", {"goal": goal, "prefer": prefer})
    if not res.get("ok"):
        print("[Gemini Agent] Error:", res.get("response", "Unknown error"), file=sys.stderr)
        return 1

    plan = res.get("plan", {})
    print(f"\nPlan ({res.get('backend')}): {plan.get('summary', '')}\n")
    steps = plan.get("steps", [])
    if not steps:
        print("No executable commands proposed.")
        return 0

    for idx, step in enumerate(steps, 1):
        cmd = step["cmd"]
        risk = step.get("risk", "safe").upper()
        reason = step.get("reason", "")
        print(f"  [{idx}/{len(steps)}] ({risk}) $ {cmd}")
        if reason:
            print(f"        Reason: {reason}")
        if risk == "DESTRUCTIVE":
            print("        Blocked by safety policy (destructive command).")
            continue
        ans = input("        Execute this command? [y/N]: ").strip().lower()
        if ans in ("y", "yes", "д", "да"):
            exec_res = api_request("/v1/agent/execute", {"cmd": cmd, "confirmed": True})
            if exec_res.get("stdout"):
                print(exec_res["stdout"].rstrip())
            if exec_res.get("stderr"):
                print(exec_res["stderr"].rstrip(), file=sys.stderr)
            print(f"        -> Exit code: {exec_res.get('returncode')}")
        else:
            print("        -> Skipped.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="gemini", description="GeminiOS Native AI CLI")
    parser.add_argument("prompt", nargs="*", help="Question, task, or subcommand (`status`, `set-key`, `enable-gemma`)")
    parser.add_argument("-a", "--agent", action="store_true", help="Run in System Agent Mode with step confirmation")
    parser.add_argument("--local", action="store_true", help="Force local Gemma fallback backend")
    parser.add_argument("--cloud", action="store_true", help="Force Google Gemini Cloud API")
    parser.add_argument("--pro", action="store_true", help="Use Gemini Pro model")
    parser.add_argument("-f", "--file", type=Path, default=None, help="Attach file contents as context")
    args = parser.parse_args()

    if args.prompt and args.prompt[0] == "status":
        print(json.dumps(api_request("/v1/status"), indent=2))
        return 0

    if args.prompt and args.prompt[0] == "set-key":
        key = args.prompt[1] if len(args.prompt) > 1 else input("Enter Google Gemini API Key: ").strip()
        res = api_request("/v1/config", {"api_key": key})
        print("API key updated." if res.get("ok") else f"Failed: {res}")
        return 0 if res.get("ok") else 1

    if args.prompt and args.prompt[0] == "enable-gemma":
        hw = api_request("/v1/hwcheck")
        print(f"Hardware check: {hw.get('ram_gb')} GB RAM, GPU VRAM: {hw.get('gpu', {}).get('vram_gb')} GB")
        print(f"Recommendation: {hw.get('recommended_model')} ({hw.get('note')})")
        if not hw.get("capable"):
            return 1
        ans = input(f"Download and enable `{hw.get('recommended_model')}` via Ollama? [y/N]: ").strip().lower()
        if ans in ("y", "yes", "д", "да"):
            res = api_request("/v1/gemma/install", {"model": "auto"})
            print(json.dumps(res, indent=2))
            return 0 if res.get("ok") else 1
        return 0

    prefer = "local" if args.local else ("cloud" if args.cloud else "auto")
    prompt_text = " ".join(args.prompt).strip()

    if not sys.stdin.isatty():
        piped = sys.stdin.read().strip()
        if piped:
            prompt_text = f"{prompt_text}\n\n--- STDIN ---\n{piped[:16000]}"

    if args.file and args.file.exists():
        content = args.file.read_text(encoding="utf-8", errors="ignore")[:16000]
        prompt_text = f"{prompt_text}\n\n--- FILE: {args.file.name} ---\n{content}"

    if not prompt_text:
        parser.print_help()
        return 0

    if args.agent:
        return run_agent(prompt_text, prefer)

    res = api_request("/v1/chat", {"prompt": prompt_text, "prefer": prefer, "pro": args.pro})
    if not res.get("ok"):
        print(f"[Gemini Error] {res.get('response')}", file=sys.stderr)
        return 1
    backend = res.get("backend", "gemini")
    formatted = format_terminal_output(res.get("response", ""))
    print(f"[{backend}]\n{formatted}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
