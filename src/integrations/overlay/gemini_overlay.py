#!/usr/bin/env python3
"""
GeminiOS Global Spotlight & AI Agent Overlay (`gemini-overlay`)
Material Design 3 Dark floating launcher bound to Super+G in KDE Plasma 6.
Includes Quick Action Chips, inline API Key setup, clean error parsing,
Clipboard AI handoff (--prompt), and Agent Mode with confirmation.
"""

import argparse
import json
import subprocess
import sys
import urllib.error
import urllib.request

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

GEMINID_URL = "http://127.0.0.1:11435"

M3_DARK_QSS = """
QWidget#Root {
    background-color: #111318;
    border: 1px solid #44474E;
    border-radius: 28px;
}
QLabel#Header {
    color: #A8C7FA;
    font-size: 16px;
    font-weight: 600;
}
QLabel#Sub {
    color: #8E9099;
    font-size: 12px;
}
QLineEdit {
    background-color: #1D2026;
    color: #E2E2E9;
    border: 1px solid #44474E;
    border-radius: 22px;
    padding: 12px 18px;
    font-size: 15px;
}
QLineEdit:focus {
    border: 2px solid #A8C7FA;
}
QTextEdit {
    background-color: #191C22;
    color: #E2E2E9;
    border: none;
    border-radius: 18px;
    padding: 14px;
    font-size: 13px;
}
QPushButton {
    background-color: #A8C7FA;
    color: #062E6F;
    border: none;
    border-radius: 18px;
    padding: 8px 18px;
    font-weight: 600;
}
QPushButton:hover {
    background-color: #C2E7FF;
}
QPushButton#Chip {
    background-color: #1D2026;
    color: #C4C6D0;
    border: 1px solid #44474E;
    border-radius: 14px;
    padding: 5px 12px;
    font-size: 12px;
    font-weight: 500;
}
QPushButton#Chip:hover {
    background-color: #282A30;
    color: #A8C7FA;
    border-color: #A8C7FA;
}
QCheckBox {
    color: #C4C6D0;
    font-size: 12px;
}
"""


class GeminiWorker(QThread):
    finished = pyqtSignal(dict)

    def __init__(self, prompt: str, agent_mode: bool):
        super().__init__()
        self.prompt = prompt
        self.agent_mode = agent_mode

    def run(self):
        endpoint = "/v1/agent/plan" if self.agent_mode else "/v1/chat"
        payload = {"goal": self.prompt} if self.agent_mode else {"prompt": self.prompt, "prefer": "auto"}
        req = urllib.request.Request(
            f"{GEMINID_URL}{endpoint}",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=90) as resp:
                self.finished.emit(json.loads(resp.read().decode("utf-8")))
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="ignore")
            try:
                self.finished.emit(json.loads(raw))
            except Exception:
                self.finished.emit({"ok": False, "response": f"HTTP {exc.code}: {raw}"})
        except Exception as exc:
            self.finished.emit({"ok": False, "response": f"geminid unreachable: {exc}"})


class GeminiOverlay(QWidget):
    def __init__(self, initial_prompt: str = ""):
        super().__init__()
        self.setObjectName("Root")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.resize(720, 470)
        self.setStyleSheet(M3_DARK_QSS)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)

        top = QHBoxLayout()
        title = QLabel("✦ GeminiOS Spotlight")
        title.setObjectName("Header")
        self.status_lbl = QLabel("Checking AI backend...")
        self.status_lbl.setObjectName("Sub")
        top.addWidget(title)
        top.addStretch()
        top.addWidget(self.status_lbl)
        layout.addLayout(top)

        input_row = QHBoxLayout()
        self.input_box = QLineEdit()
        self.input_box.setPlaceholderText("Ask Gemini anything or give a system Agent command...")
        self.input_box.returnPressed.connect(self.on_submit)
        self.send_btn = QPushButton("Ask")
        self.send_btn.clicked.connect(self.on_submit)
        input_row.addWidget(self.input_box, 1)
        input_row.addWidget(self.send_btn)
        layout.addLayout(input_row)

        # Material 3 Quick Action Chips
        chips = QHBoxLayout()
        chips.setSpacing(8)
        for label, cb in [
            ("✦ Set API Key", self.on_set_key),
            ("✦ System Doctor", self.on_doctor),
            ("✦ Explain Clipboard", self.on_clipboard),
            ("✦ Enable Local Gemma", self.on_enable_gemma),
        ]:
            btn = QPushButton(label)
            btn.setObjectName("Chip")
            btn.clicked.connect(cb)
            chips.addWidget(btn)
        chips.addStretch()
        layout.addLayout(chips)

        opts = QHBoxLayout()
        self.agent_cb = QCheckBox("Agent Mode (propose & execute system commands with confirmation)")
        opts.addWidget(self.agent_cb)
        opts.addStretch()
        layout.addLayout(opts)

        self.output = QTextEdit()
        self.output.setReadOnly(True)
        self.output.setFont(QFont("JetBrains Mono", 10))
        self.output.setPlaceholderText("Gemini responses and Agent plans appear here... (Esc to close)")
        layout.addWidget(self.output, 1)

        self.worker = None
        self.refresh_status()

        if initial_prompt:
            self.input_box.setText(initial_prompt)
            self.on_submit()

    def refresh_status(self):
        try:
            with urllib.request.urlopen(f"{GEMINID_URL}/v1/status", timeout=3) as resp:
                st = json.loads(resp.read().decode("utf-8"))
            if st.get("cloud_configured"):
                self.status_lbl.setText(f"● Gemini Cloud ({st.get('cloud_model')}) · Esc to close")
            elif st.get("fallback_enabled"):
                self.status_lbl.setText(f"● Gemma Local ({st.get('fallback_model')}) · Esc to close")
            else:
                self.status_lbl.setText("● Setup Required (click 'Set API Key' or 'Enable Local Gemma')")
        except Exception:
            self.status_lbl.setText("● geminid offline")

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.close()
        else:
            super().keyPressEvent(event)

    def on_set_key(self):
        key, ok = QInputDialog.getText(
            self,
            "Google Gemini API Key",
            "Paste your Google Gemini API key (AIza...):",
            QLineEdit.EchoMode.Password,
        )
        if ok and key.strip():
            req = urllib.request.Request(
                f"{GEMINID_URL}/v1/config",
                data=json.dumps({"api_key": key.strip()}).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            try:
                urllib.request.urlopen(req, timeout=5)
                self.output.setPlainText("Gemini API key saved! You can now ask anything.")
                self.refresh_status()
            except Exception as exc:
                self.output.setPlainText(f"Failed to save key: {exc}")

    def on_doctor(self):
        subprocess.Popen(["konsole", "--hold", "-e", "gemini-doctor"])

    def on_clipboard(self):
        clip = QApplication.clipboard().text().strip()
        if not clip:
            self.output.setPlainText("Clipboard is empty.")
            return
        self.input_box.setText(f"Explain or fix this clipboard content concisely:\n{clip[:4000]}")
        self.on_submit()

    def on_enable_gemma(self):
        subprocess.Popen(["konsole", "--hold", "-e", "gemini", "enable-gemma"])

    def on_submit(self):
        text = self.input_box.text().strip()
        if not text:
            return
        self.output.setPlainText("Thinking with Gemini...")
        self.send_btn.setEnabled(False)
        self.worker = GeminiWorker(text, self.agent_cb.isChecked())
        self.worker.finished.connect(self.on_response)
        self.worker.start()

    def on_response(self, data: dict):
        self.send_btn.setEnabled(True)
        if not data.get("ok"):
            msg = data.get("response", "Unknown error")
            self.output.setPlainText(
                f"{msg}\n\nTip: click '✦ Set API Key' above to enter your Google Gemini API key, "
                f"or click '✦ Enable Local Gemma' to run offline."
            )
            return

        if "plan" in data:
            plan = data["plan"]
            lines = [f"[{data.get('backend')}] Plan: {plan.get('summary', '')}\n"]
            for idx, step in enumerate(plan.get("steps", []), 1):
                lines.append(f"{idx}. [{step.get('risk', 'safe').upper()}] $ {step['cmd']}")
                if step.get("reason"):
                    lines.append(f"   {step['reason']}")
            self.output.setPlainText("\n".join(lines))

            for step in plan.get("steps", []):
                if step.get("risk") == "destructive":
                    continue
                reply = QMessageBox.question(
                    self,
                    "GeminiOS Agent Confirmation",
                    f"Execute command?\n\n{step['cmd']}\n\nReason: {step.get('reason', '')}",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                )
                if reply == QMessageBox.StandardButton.Yes:
                    req = urllib.request.Request(
                        f"{GEMINID_URL}/v1/agent/execute",
                        data=json.dumps({"cmd": step["cmd"], "confirmed": True}).encode("utf-8"),
                        headers={"Content-Type": "application/json"},
                        method="POST",
                    )
                    with urllib.request.urlopen(req, timeout=120) as resp:
                        res = json.loads(resp.read().decode("utf-8"))
                    self.output.append(f"\n$ {step['cmd']}\n{res.get('stdout', '')}{res.get('stderr', '')}")
        else:
            self.output.setPlainText(f"[{data.get('backend')}]\n\n{data.get('response', '')}")


def main() -> int:
    parser = argparse.ArgumentParser(description="GeminiOS Spotlight Overlay")
    parser.add_argument("--prompt", default="", help="Initial prompt to run immediately")
    args, qt_args = parser.parse_known_args()

    app = QApplication([sys.argv[0]] + qt_args)
    win = GeminiOverlay(initial_prompt=args.prompt)
    screen = app.primaryScreen().availableGeometry()
    win.move(
        screen.center().x() - win.width() // 2,
        screen.top() + int(screen.height() * 0.14),
    )
    win.show()
    win.input_box.setFocus()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
