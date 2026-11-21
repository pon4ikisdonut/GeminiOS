#!/usr/bin/env python3
"""
GeminiOS AI Backends (`backends.py`)
Supports official Google Gemini REST API (primary) and local Gemma via Ollama
(automatic offline/error fallback when user consented and hardware supports it).
"""

import json
import os
import urllib.error
import urllib.request
from typing import Dict, List, Optional, Tuple


SYSTEM_PROMPT_DEFAULT = (
    "You are Gemini, natively integrated into GeminiOS 1.0 (an independent Linux distribution "
    "with KDE Plasma 6 Material Design 3, the `gem` package manager, and an optional Arch/AUR bridge). "
    "Give concise, technically accurate, directly actionable answers. "
    "When answering in terminal consoles, do not use markdown asterisk formatting (**bold**, *italic*), "
    "raw asterisks for bullet points (* item), or markdown hashtags (#, ##). "
    "Use clean plain text, standard dashes (-) or unicode bullets (•) for lists, and natural spacing."
)


class HybridBackend:
    def __init__(self, config: Dict):
        self.config = config

    def _gemini_cfg(self) -> Dict:
        return self.config.get("gemini", {})

    def _fallback_cfg(self) -> Dict:
        return self.config.get("fallback", {})

    def get_api_key(self) -> str:
        return os.environ.get("GEMINI_API_KEY") or self._gemini_cfg().get("api_key", "").strip()

    def call_gemini_api(
        self,
        prompt: str,
        system_prompt: str = SYSTEM_PROMPT_DEFAULT,
        use_pro: bool = False,
        messages: Optional[List[Dict]] = None,
    ) -> Tuple[bool, str]:
        api_key = self.get_api_key()
        if not api_key:
            return False, "Gemini API key is not configured."

        gcfg = self._gemini_cfg()
        model = gcfg.get("pro_model" if use_pro else "model", "gemini-3.5-flash-lite")
        base = gcfg.get("api_base", "https://generativelanguage.googleapis.com/v1beta").rstrip("/")
        timeout = int(gcfg.get("timeout_seconds", 30))

        # Build multi-turn conversational contents
        contents = []
        if messages:
            for m in messages:
                role = "model" if m.get("role") in ("assistant", "model") else "user"
                text = (m.get("content") or m.get("text") or "").strip()
                if not text:
                    continue
                if contents and contents[-1]["role"] == role:
                    contents[-1]["parts"].append({"text": text})
                else:
                    contents.append({"role": role, "parts": [{"text": text}]})

        # Append prompt if not already the last turn
        if prompt:
            prompt_str = prompt.strip()
            if not contents or contents[-1]["role"] != "user":
                contents.append({"role": "user", "parts": [{"text": prompt_str}]})
            elif contents and contents[-1]["parts"] and contents[-1]["parts"][-1].get("text") != prompt_str:
                contents.append({"role": "user", "parts": [{"text": prompt_str}]})

        # Ensure first turn is from user
        while contents and contents[0]["role"] == "model":
            contents.pop(0)

        if not contents:
            if not prompt:
                return False, "Empty prompt and messages."
            contents = [{"role": "user", "parts": [{"text": prompt}]}]

        url = f"{base}/models/{model}:generateContent?key={api_key}"
        payload = {
            "system_instruction": {"parts": [{"text": system_prompt}]},
            "contents": contents,
            "generationConfig": {"temperature": 0.4},
        }
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            candidates = data.get("candidates", [])
            if not candidates:
                return False, "Gemini API returned no candidates."
            parts = candidates[0].get("content", {}).get("parts", [])
            text = "".join(p.get("text", "") for p in parts).strip()
            return True, text
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="ignore")
            return False, f"Gemini API HTTP {exc.code}: {body[:240]}"
        except Exception as exc:
            return False, f"Gemini API unreachable: {exc}"

    def call_ollama_gemma(
        self,
        prompt: str,
        system_prompt: str = SYSTEM_PROMPT_DEFAULT,
        messages: Optional[List[Dict]] = None,
    ) -> Tuple[bool, str]:
        fcfg = self._fallback_cfg()
        if not fcfg.get("enabled", False):
            return False, "Local Gemma fallback is disabled."

        ollama_url = fcfg.get("ollama_url", "http://127.0.0.1:11434").rstrip("/")
        model = fcfg.get("model", "gemma3:4b")
        if model == "auto":
            model = "gemma3:4b"

        # Try multi-turn /api/chat if message history exists
        if messages:
            chat_msgs = [{"role": "system", "content": system_prompt}]
            for m in messages:
                r = "assistant" if m.get("role") in ("assistant", "model") else "user"
                c = (m.get("content") or m.get("text") or "").strip()
                if c:
                    chat_msgs.append({"role": r, "content": c})
            if prompt and (not chat_msgs or chat_msgs[-1]["content"] != prompt):
                chat_msgs.append({"role": "user", "content": prompt})

            payload = {
                "model": model,
                "messages": chat_msgs,
                "stream": False,
            }
            req = urllib.request.Request(
                f"{ollama_url}/api/chat",
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            try:
                with urllib.request.urlopen(req, timeout=90) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                return True, data.get("message", {}).get("content", "").strip()
            except Exception:
                pass  # Fallback to /api/generate

        combined_prompt = prompt
        if messages:
            hist_lines = []
            for m in messages:
                rn = "Assistant" if m.get("role") in ("assistant", "model") else "User"
                hist_lines.append(f"{rn}: {m.get('content', '')}")
            if prompt:
                hist_lines.append(f"User: {prompt}")
            combined_prompt = "\n".join(hist_lines)

        payload = {
            "model": model,
            "system": system_prompt,
            "prompt": combined_prompt,
            "stream": False,
        }
        req = urllib.request.Request(
            f"{ollama_url}/api/generate",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=90) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            return True, data.get("response", "").strip()
        except Exception as exc:
            return False, f"Local Gemma (Ollama) unreachable: {exc}"

    def generate(
        self,
        prompt: str,
        system_prompt: str = SYSTEM_PROMPT_DEFAULT,
        prefer: str = "auto",
        use_pro: bool = False,
        messages: Optional[List[Dict]] = None,
    ) -> Dict:
        """
        prefer: 'auto' (Gemini Cloud -> Gemma Local fallback), 'cloud', or 'local'.
        """
        if prefer == "local":
            ok, out = self.call_ollama_gemma(prompt, system_prompt, messages=messages)
            return {"ok": ok, "backend": "gemma-local", "response": out}

        ok, out = self.call_gemini_api(prompt, system_prompt, use_pro=use_pro, messages=messages)
        if ok or prefer == "cloud":
            return {"ok": ok, "backend": "gemini-cloud", "response": out}

        # Automatic fallback to local Gemma if enabled
        if self._fallback_cfg().get("enabled", False):
            f_ok, f_out = self.call_ollama_gemma(prompt, system_prompt, messages=messages)
            if f_ok:
                return {
                    "ok": True,
                    "backend": "gemma-local-fallback",
                    "cloud_error": out,
                    "response": f_out,
                }
            return {
                "ok": False,
                "backend": "none",
                "response": f"Cloud failed ({out}) and local Gemma fallback failed ({f_out}).",
            }

        return {"ok": False, "backend": "gemini-cloud", "response": out}

        return {"ok": False, "backend": "gemini-cloud", "response": out}
