#!/usr/bin/env python3
"""
GeminiOS First-Boot Setup Wizard (`gemini-oobe`)
Material Design 3 Dark PyQt6 wizard:
1. Welcome to GeminiOS (With Love, With Gemini)
2. Google Gemini API Key configuration
3. Hardware check + optional automatic local Gemma fallback download
4. Optional Arch Linux & AUR repository bridge toggle
"""

import json
import subprocess
import sys
import urllib.request
from pathlib import Path

from PyQt6.QtCore import Qt, QThread, QUrl, pyqtSignal
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

GEMINID_URL = "http://127.0.0.1:11435"
MARKER_FILE = Path.home() / ".config/geminios-oobe-done"

OOBE_QSS = """
QWidget {
    background-color: #111318;
    color: #E2E2E9;
    font-family: 'Roboto', 'Noto Sans', sans-serif;
}
QLabel#Title {
    font-size: 26px;
    font-weight: 600;
    color: #E2E2E9;
}
QLabel#Accent {
    font-size: 14px;
    color: #A8C7FA;
}
QLabel#Body {
    font-size: 14px;
    color: #C4C6D0;
}
QLineEdit {
    background-color: #1D2026;
    border: 1px solid #44474E;
    border-radius: 14px;
    padding: 12px 14px;
    font-size: 14px;
}
QPushButton {
    background-color: #A8C7FA;
    color: #062E6F;
    border: none;
    border-radius: 20px;
    padding: 10px 24px;
    font-size: 14px;
    font-weight: 600;
}
QPushButton#Secondary {
    background-color: #282A30;
    color: #E2E2E9;
}
QProgressBar {
    background-color: #1D2026;
    border-radius: 6px;
    height: 10px;
    text-align: center;
}
QProgressBar::chunk {
    background-color: #A8C7FA;
    border-radius: 6px;
}
QFrame#PromoCard {
    background-color: #191E28;
    border: 1px solid #36445B;
    border-radius: 14px;
    padding: 10px 14px;
}
QLabel#PromoTitle {
    font-size: 14px;
    font-weight: 700;
    color: #A8C7FA;
}
QLabel#PromoText {
    font-size: 12px;
    color: #C4C6D0;
}
QPushButton#PromoBtn {
    background-color: #2F3B52;
    color: #D3E3FD;
    border: 1px solid #48597A;
    border-radius: 14px;
    padding: 6px 14px;
    font-size: 12px;
    font-weight: 600;
}
QPushButton#PromoBtn:hover {
    background-color: #3C4B69;
    border-color: #7CA1FF;
}
QPushButton#TelegramBtn {
    background-color: #2AABEE;
    color: #FFFFFF;
    border: none;
    border-radius: 18px;
    padding: 8px 18px;
    font-size: 13px;
    font-weight: 600;
}
QPushButton#TelegramBtn:hover {
    background-color: #229ED9;
}
"""


def create_opg_raduga_banner(parent=None) -> QFrame:
    card = QFrame(parent)
    card.setObjectName("PromoCard")
    layout = QHBoxLayout(card)
    layout.setContentsMargins(12, 8, 12, 8)
    layout.setSpacing(12)

    icon_label = QLabel("🌈")
    icon_label.setStyleSheet("font-size: 26px; background: transparent;")
    layout.addWidget(icon_label)

    text_layout = QVBoxLayout()
    text_layout.setSpacing(2)
    title = QLabel("Чат комьюнити: ОПГ «Радуга»")
    title.setObjectName("PromoTitle")
    subtitle = QLabel("Общение, разработка GeminiOS, релизы и идеи в Telegram (t.me/OPG_R4duga)")
    subtitle.setObjectName("PromoText")
    text_layout.addWidget(title)
    text_layout.addWidget(subtitle)
    layout.addLayout(text_layout, 1)

    btn = QPushButton("Вступить в чат")
    btn.setObjectName("PromoBtn")
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://t.me/OPG_R4duga")))
    layout.addWidget(btn)

    return card


class SetupApplyWorker(QThread):
    status = pyqtSignal(str)
    done = pyqtSignal(bool)

    def __init__(self, api_key: str, install_gemma: bool, enable_arch: bool, enable_aur: bool):
        super().__init__()
        self.api_key = api_key
        self.install_gemma = install_gemma
        self.enable_arch = enable_arch
        self.enable_aur = enable_aur

    def _post(self, path: str, payload: dict):
        req = urllib.request.Request(
            f"{GEMINID_URL}{path}",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=600) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def run(self):
        try:
            if self.api_key:
                self.status.emit("Saving Google Gemini API key...")
                self._post("/v1/config", {"api_key": self.api_key})

            if self.install_gemma:
                self.status.emit("Downloading local Gemma fallback via Ollama (this may take a few minutes)...")
                self._post("/v1/gemma/install", {"model": "auto"})

            if self.enable_arch:
                self.status.emit("Enabling Arch Linux official repository bridge...")
                subprocess.run(["pkexec", "gem", "repo", "enable", "arch"], check=False)

            if self.enable_aur:
                self.status.emit("Enabling AUR bridge (yay)...")
                subprocess.run(["pkexec", "gem", "repo", "enable", "aur"], check=False)

            MARKER_FILE.parent.mkdir(parents=True, exist_ok=True)
            MARKER_FILE.write_text("completed\n", encoding="utf-8")
            self.status.emit("All set! Welcome to GeminiOS.")
            self.done.emit(True)
        except Exception as exc:
            self.status.emit(f"Finished with warning: {exc}")
            self.done.emit(False)


class GeminiOOBE(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Welcome to GeminiOS 1.0.1")
        self.resize(660, 480)
        self.setStyleSheet(OOBE_QSS)

        self.hw = self._fetch_hw()

        root = QVBoxLayout(self)
        root.setContentsMargins(36, 32, 36, 28)

        self.stack = QStackedWidget()
        root.addWidget(self.stack, 1)

        # Page 0: Welcome
        p0 = QWidget()
        l0 = QVBoxLayout(p0)
        t0 = QLabel("✦ Welcome to GeminiOS 1.0.1")
        t0.setObjectName("Title")
        a0 = QLabel("GeminiOS, powered by Linux — With Love, With Gemini")
        a0.setObjectName("Accent")
        b0 = QLabel(
            "Let's configure your Gemini API key, check whether your hardware supports "
            "automatic offline Gemma fallback, and optionally enable the Arch Linux & AUR bridge."
        )
        b0.setObjectName("Body")
        b0.setWordWrap(True)
        l0.addStretch()
        l0.addWidget(t0)
        l0.addWidget(a0)
        l0.addSpacing(12)
        l0.addWidget(b0)
        l0.addSpacing(14)
        l0.addWidget(create_opg_raduga_banner(p0))
        l0.addStretch()
        self.stack.addWidget(p0)

        # Page 1: Gemini API + Local Gemma Fallback
        p1 = QWidget()
        l1 = QVBoxLayout(p1)
        t1 = QLabel("Configure Gemini AI")
        t1.setObjectName("Title")
        l1.addWidget(t1)
        l1.addSpacing(8)
        self.key_input = QLineEdit()
        self.key_input.setPlaceholderText("Paste your Google Gemini API Key (AIza...)")
        self.key_input.setEchoMode(QLineEdit.EchoMode.Password)
        l1.addWidget(self.key_input)
        l1.addSpacing(16)

        hw_text = (
            f"Detected Hardware: {self.hw.get('ram_gb', '?')} GB RAM · "
            f"{self.hw.get('cpu', {}).get('cores', '?')} CPU cores · "
            f"GPU: {self.hw.get('gpu', {}).get('name', 'CPU')} ({self.hw.get('gpu', {}).get('vram_gb', 0)} GB VRAM)\n"
            f"Recommendation: {self.hw.get('recommended_model') or 'Cloud only'} — {self.hw.get('note', '')}"
        )
        hw_label = QLabel(hw_text)
        hw_label.setObjectName("Body")
        hw_label.setWordWrap(True)
        l1.addWidget(hw_label)

        self.gemma_cb = QCheckBox(
            f"Automatically download & enable local Gemma fallback ({self.hw.get('recommended_model') or 'N/A'})"
        )
        self.gemma_cb.setEnabled(bool(self.hw.get("capable", False)))
        self.gemma_cb.setChecked(bool(self.hw.get("capable", False)))
        l1.addWidget(self.gemma_cb)
        l1.addStretch()
        self.stack.addWidget(p1)

        # Page 2: Package Bridges (Arch + AUR)
        p2 = QWidget()
        l2 = QVBoxLayout(p2)
        t2 = QLabel("Software Repositories")
        t2.setObjectName("Title")
        b2 = QLabel(
            "GeminiOS uses the independent `gem` package manager backed by GitHub manifests. "
            "You can also toggle native Arch Linux & AUR (`yay`) bridges right now:"
        )
        b2.setObjectName("Body")
        b2.setWordWrap(True)
        self.arch_cb = QCheckBox("Enable Arch Linux Official Repositories (core, extra, multilib)")
        self.aur_cb = QCheckBox("Enable AUR Bridge (via yay / makepkg)")
        l2.addWidget(t2)
        l2.addSpacing(8)
        l2.addWidget(b2)
        l2.addSpacing(14)
        l2.addWidget(self.arch_cb)
        l2.addWidget(self.aur_cb)
        l2.addStretch()
        self.stack.addWidget(p2)

        # Page 3: Applying
        p3 = QWidget()
        l3 = QVBoxLayout(p3)
        t3 = QLabel("Setting up GeminiOS 1.0.1...")
        t3.setObjectName("Title")
        self.status_lbl = QLabel("Ready to apply settings.")
        self.status_lbl.setObjectName("Body")
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.promo_banner = create_opg_raduga_banner(p3)
        l3.addStretch()
        l3.addWidget(t3)
        l3.addWidget(self.status_lbl)
        l3.addWidget(self.progress)
        l3.addSpacing(16)
        l3.addWidget(self.promo_banner)
        l3.addStretch()
        self.stack.addWidget(p3)

        # Navigation buttons
        nav = QHBoxLayout()
        self.back_btn = QPushButton("Back")
        self.back_btn.setObjectName("Secondary")
        self.back_btn.clicked.connect(self.go_back)
        self.telegram_btn = QPushButton("Чат ОПГ «Радуга»")
        self.telegram_btn.setObjectName("TelegramBtn")
        self.telegram_btn.setVisible(False)
        self.telegram_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.telegram_btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://t.me/OPG_R4duga")))
        self.next_btn = QPushButton("Next")
        self.next_btn.clicked.connect(self.go_next)
        nav.addWidget(self.back_btn)
        nav.addStretch()
        nav.addWidget(self.telegram_btn)
        nav.addWidget(self.next_btn)
        root.addLayout(nav)
        self._refresh_nav()

    def _fetch_hw(self) -> dict:
        try:
            with urllib.request.urlopen(f"{GEMINID_URL}/v1/hwcheck", timeout=4) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception:
            return {"capable": False, "note": "geminid not running yet; configure later via `gemini enable-gemma`."}

    def _refresh_nav(self):
        idx = self.stack.currentIndex()
        self.back_btn.setVisible(idx in (1, 2))
        if idx == 2:
            self.next_btn.setText("Apply & Finish")
        elif idx == 3:
            self.next_btn.setVisible(False)
        else:
            self.next_btn.setText("Next")

    def go_back(self):
        self.stack.setCurrentIndex(max(0, self.stack.currentIndex() - 1))
        self._refresh_nav()

    def go_next(self):
        idx = self.stack.currentIndex()
        if idx < 2:
            self.stack.setCurrentIndex(idx + 1)
            self._refresh_nav()
        elif idx == 2:
            self.stack.setCurrentIndex(3)
            self._refresh_nav()
            self.worker = SetupApplyWorker(
                api_key=self.key_input.text().strip(),
                install_gemma=self.gemma_cb.isChecked(),
                enable_arch=self.arch_cb.isChecked(),
                enable_aur=self.aur_cb.isChecked(),
            )
            self.worker.status.connect(self.status_lbl.setText)
            self.worker.done.connect(self._on_finished)
            self.worker.start()

    def _on_finished(self, _ok: bool):
        self.progress.setRange(0, 1)
        self.progress.setValue(1)
        self.status_lbl.setText("✦ Настройка завершена! Добро пожаловать в комьюнити ОПГ «Радуга» (t.me/OPG_R4duga)!")
        self.telegram_btn.setVisible(True)
        self.next_btn.setText("Close")
        self.next_btn.setVisible(True)
        self.next_btn.clicked.disconnect()
        self.next_btn.clicked.connect(self.close)


def main() -> int:
    if MARKER_FILE.exists() and "--force" not in sys.argv:
        return 0
    app = QApplication(sys.argv)
    w = GeminiOOBE()
    w.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
