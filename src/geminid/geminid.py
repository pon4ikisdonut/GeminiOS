#!/usr/bin/env python3
"""
GeminiOS System AI Daemon (`geminid.py`)
Unified local HTTP API (127.0.0.1:11435) serving CLI, Shell hooks, Overlay,
Plasma widget, Dolphin service menu, OOBE wizard, and Agent Mode.
"""

import argparse
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Dict

try:
    import tomllib
except ImportError:
    tomllib = None

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from agent import AGENT_SYSTEM_PROMPT, execute_step, extract_json_plan
from backends import HybridBackend
from hwcheck import evaluate_gemma_capability, install_ollama_and_pull_gemma


class DaemonState:
    def __init__(self, conf_path: Path):
        self.conf_path = conf_path
        self.config = self._load_conf()
        self.backend = HybridBackend(self.config)

    def _load_conf(self) -> Dict:
        if not self.conf_path.exists() or tomllib is None:
            return {"daemon": {"host": "127.0.0.1", "port": 11435}, "gemini": {}, "fallback": {}, "agent": {}}
        with self.conf_path.open("rb") as fh:
            return tomllib.load(fh)

    def reload(self) -> None:
        self.config = self._load_conf()
        self.backend = HybridBackend(self.config)

    def update_config(self, api_key: str = None, fallback_enabled: bool = None, fallback_model: str = None) -> None:
        text = self.conf_path.read_text(encoding="utf-8") if self.conf_path.exists() else ""
        lines = text.splitlines()
        section = ""
        out = []
        for line in lines:
            s = line.strip()
            if s.startswith("[") and s.endswith("]"):
                section = s
                out.append(line)
                continue
            if section == "[gemini]" and s.startswith("api_key") and api_key is not None:
                out.append(f'api_key = "{api_key}"')
            elif section == "[fallback]" and s.startswith("enabled") and fallback_enabled is not None:
                out.append(f"enabled = {'true' if fallback_enabled else 'false'}")
            elif section == "[fallback]" and s.startswith("user_consented") and fallback_enabled is not None:
                out.append(f"user_consented = {'true' if fallback_enabled else 'false'}")
            elif section == "[fallback]" and s.startswith("model") and fallback_model is not None:
                out.append(f'model = "{fallback_model}"')
            else:
                out.append(line)
        self.conf_path.parent.mkdir(parents=True, exist_ok=True)
        self.conf_path.write_text("\n".join(out) + "\n", encoding="utf-8")
        self.reload()


def make_handler(state: DaemonState):
    class GeminiDHandler(BaseHTTPRequestHandler):
        def _send_json(self, status: int, payload: Dict) -> None:
            body = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _read_json(self) -> Dict:
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length) if length > 0 else b"{}"
            return json.loads(raw.decode("utf-8"))

        def log_message(self, fmt, *args):
            return

        def do_GET(self):
            if self.path == "/v1/health":
                self._send_json(200, {"status": "ok", "service": "geminid", "version": "1.0.0"})
            elif self.path == "/v1/status":
                has_key = bool(state.backend.get_api_key())
                fb = state.config.get("fallback", {})
                self._send_json(200, {
                    "cloud_configured": has_key,
                    "cloud_model": state.config.get("gemini", {}).get("model", "gemini-3.5-flash-lite"),
                    "fallback_enabled": bool(fb.get("enabled", False)),
                    "fallback_model": fb.get("model", "auto"),
                    "agent_enabled": bool(state.config.get("agent", {}).get("enabled", True)),
                })
            elif self.path == "/v1/hwcheck":
                self._send_json(200, evaluate_gemma_capability())
            else:
                self._send_json(404, {"error": "Not found"})

        def do_POST(self):
            body = self._read_json()
            if self.path == "/v1/chat":
                prompt = body.get("prompt", "")
                prefer = body.get("prefer", "auto")
                use_pro = bool(body.get("pro", False))
                result = state.backend.generate(prompt=prompt, prefer=prefer, use_pro=use_pro)
                self._send_json(200 if result["ok"] else 502, result)
            elif self.path == "/v1/agent/plan":
                goal = body.get("goal", "")
                prefer = body.get("prefer", "auto")
                res = state.backend.generate(
                    prompt=f"User goal: {goal}",
                    system_prompt=AGENT_SYSTEM_PROMPT,
                    prefer=prefer,
                )
                if not res["ok"]:
                    self._send_json(502, res)
                    return
                plan = extract_json_plan(res["response"])
                self._send_json(200, {"ok": True, "backend": res["backend"], "plan": plan})
            elif self.path == "/v1/agent/execute":
                cmd = body.get("cmd", "")
                if not body.get("confirmed", False):
                    self._send_json(400, {"ok": False, "error": "Explicit user confirmation required."})
                    return
                audit_path = Path(state.config.get("daemon", {}).get("audit_log", "/var/log/geminid/agent-audit.log"))
                allow_dest = bool(state.config.get("agent", {}).get("allow_destructive", False))
                res = execute_step(cmd, audit_path, allow_destructive=allow_dest)
                self._send_json(200, res)
            elif self.path == "/v1/config":
                state.update_config(
                    api_key=body.get("api_key"),
                    fallback_enabled=body.get("fallback_enabled"),
                    fallback_model=body.get("fallback_model"),
                )
                self._send_json(200, {"ok": True})
            elif self.path == "/v1/gemma/install":
                res = install_ollama_and_pull_gemma(body.get("model", "auto"))
                if res.get("ok"):
                    state.update_config(fallback_enabled=True, fallback_model=res["model"])
                self._send_json(200 if res.get("ok") else 500, res)
            else:
                self._send_json(404, {"error": "Not found"})

    return GeminiDHandler


def main() -> int:
    parser = argparse.ArgumentParser(description="GeminiOS System AI Daemon")
    parser.add_argument("--config", type=Path, default=Path("/etc/geminid/geminid.conf"))
    args = parser.parse_args()

    state = DaemonState(args.config)
    dcfg = state.config.get("daemon", {})
    host = dcfg.get("host", "127.0.0.1")
    port = int(dcfg.get("port", 11435))

    server = ThreadingHTTPServer((host, port), make_handler(state))
    server.daemon_threads = True

    def _sig_term(signum, frame):
        try:
            server.shutdown()
        except Exception:
            pass
        sys.exit(0)

    import signal
    signal.signal(signal.SIGTERM, _sig_term)
    signal.signal(signal.SIGINT, _sig_term)

    print(f"[geminid] Listening on http://{host}:{port} ...")
    try:
        server.serve_forever()
    except (KeyboardInterrupt, SystemExit):
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
