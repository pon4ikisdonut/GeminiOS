#!/usr/bin/env python3
"""
GeminiOS 1.0 Graphical OS Installer (`gemini_installer.py`)
Material Design 3 Dark PyQt6 wizard for installing GeminiOS to disk.
"""

import json
import subprocess
import sys
from pathlib import Path

from PyQt6.QtCore import Qt, QThread, QUrl, pyqtSignal
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QStackedWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

BACKEND_PATH = "/usr/lib/geminios/install_backend.py"

INSTALLER_QSS = """
QWidget {
    background-color: #111318;
    color: #E2E2E9;
    font-family: 'Roboto', 'Noto Sans', sans-serif;
}
QLabel#Title {
    font-size: 24px;
    font-weight: 600;
    color: #E2E2E9;
}
QLabel#Accent {
    font-size: 13px;
    color: #A8C7FA;
}
QLabel#Warn {
    font-size: 13px;
    color: #FFB4AB;
    font-weight: 600;
}
QLineEdit, QComboBox {
    background-color: #1D2026;
    color: #E2E2E9;
    border: 1px solid #44474E;
    border-radius: 12px;
    padding: 9px 12px;
    font-size: 14px;
}
QTextEdit {
    background-color: #191C22;
    color: #C4C6D0;
    border: 1px solid #2F333C;
    border-radius: 14px;
    padding: 10px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 12px;
}
QPushButton {
    background-color: #A8C7FA;
    color: #062E6F;
    border: none;
    border-radius: 18px;
    padding: 10px 22px;
    font-size: 14px;
    font-weight: 600;
}
QPushButton#Secondary {
    background-color: #282A30;
    color: #E2E2E9;
}
QPushButton#Danger {
    background-color: #FFB4AB;
    color: #690005;
}
QProgressBar {
    background-color: #1D2026;
    border-radius: 6px;
    height: 12px;
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
    padding: 10px 20px;
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


def list_target_disks():
    try:
        proc = subprocess.run(
            ["lsblk", "-J", "-d", "-o", "NAME,SIZE,MODEL,TYPE"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        data = json.loads(proc.stdout)
        disks = []
        for dev in data.get("blockdevices", []):
            if dev.get("type") != "disk":
                continue
            name = dev.get("name", "")
            if name.startswith(("loop", "zram", "sr")):
                continue
            model = (dev.get("model") or "Disk").strip()
            size = dev.get("size", "?")
            disks.append((f"/dev/{name}", f"/dev/{name} — {size} ({model})"))
        return disks
    except Exception:
        return []


class InstallWorker(QThread):
    progress_sig = pyqtSignal(int, str)
    log_sig = pyqtSignal(str)
    done_sig = pyqtSignal(bool, str)

    def __init__(self, cmd):
        super().__init__()
        self.cmd = cmd

    def run(self):
        try:
            proc = subprocess.Popen(
                self.cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
            assert proc.stdout is not None
            for line in proc.stdout:
                s = line.rstrip()
                if s.startswith("PROGRESS:"):
                    parts = s.split(":", 2)
                    if len(parts) == 3:
                        self.progress_sig.emit(int(parts[1]), parts[2])
                else:
                    self.log_sig.emit(s)
            rc = proc.wait()
            if rc == 0:
                self.done_sig.emit(True, "GeminiOS 1.0.1 has been installed successfully!")
            else:
                self.done_sig.emit(False, f"Installer exited with code {rc}. Check log above.")
        except Exception as exc:
            self.done_sig.emit(False, f"Installation failed: {exc}")


class GeminiInstaller(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Install GeminiOS 1.0.1")
        self.resize(720, 560)
        self.setStyleSheet(INSTALLER_QSS)
        self.disks = list_target_disks()

        root = QVBoxLayout(self)
        root.setContentsMargins(32, 26, 32, 24)
        self.stack = QStackedWidget()
        root.addWidget(self.stack, 1)

        # Page 0: Disk & Filesystem
        p0 = QWidget()
        l0 = QVBoxLayout(p0)
        t0 = QLabel("✦ Install GeminiOS 1.0.1 to Disk")
        t0.setObjectName("Title")
        a0 = QLabel("GeminiOS, powered by Linux — With Love, With Gemini")
        a0.setObjectName("Accent")
        l0.addWidget(t0)
        l0.addWidget(a0)
        l0.addSpacing(14)

        form0 = QFormLayout()
        self.disk_combo = QComboBox()
        if self.disks:
            for dev, label in self.disks:
                self.disk_combo.addItem(label, dev)
        else:
            self.disk_combo.addItem("No target disk detected (attach a virtual/physical drive)", "")

        self.fs_combo = QComboBox()
        self.fs_combo.addItems(["ext4", "btrfs"])

        self.swap_combo = QComboBox()
        self.swap_combo.addItem("4 GB swapfile (Recommended)", 4)
        self.swap_combo.addItem("8 GB swapfile", 8)
        self.swap_combo.addItem("No swap", 0)

        mode_str = "UEFI (GPT + EFI System Partition)" if Path("/sys/firmware/efi").exists() else "Legacy BIOS (GPT + bios_grub)"
        form0.addRow("Target Disk:", self.disk_combo)
        form0.addRow("Filesystem:", self.fs_combo)
        form0.addRow("Swap:", self.swap_combo)
        form0.addRow("Boot Mode:", QLabel(mode_str))
        l0.addLayout(form0)
        l0.addSpacing(12)
        l0.addWidget(create_opg_raduga_banner(p0))
        l0.addStretch()
        self.stack.addWidget(p0)

        # Page 1: Account & Locale
        p1 = QWidget()
        l1 = QVBoxLayout(p1)
        t1 = QLabel("User & System")
        t1.setObjectName("Title")
        l1.addWidget(t1)
        l1.addSpacing(12)
        form1 = QFormLayout()
        self.user_edit = QLineEdit("pon4ik")
        self.pass_edit = QLineEdit()
        self.pass_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.pass_edit.setPlaceholderText("Enter password")
        self.pass2_edit = QLineEdit()
        self.pass2_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.pass2_edit.setPlaceholderText("Confirm password")
        self.host_edit = QLineEdit("geminios")
        self.tz_combo = QComboBox()
        self.tz_combo.addItems(["Europe/Kyiv", "UTC", "Europe/Warsaw", "Europe/Berlin", "America/New_York"])
        self.keymap_combo = QComboBox()
        self.keymap_combo.addItems(["us", "ru", "ua"])
        form1.addRow("Username:", self.user_edit)
        form1.addRow("Password:", self.pass_edit)
        form1.addRow("Confirm Password:", self.pass2_edit)
        form1.addRow("Hostname:", self.host_edit)
        form1.addRow("Timezone:", self.tz_combo)
        form1.addRow("Console Keymap:", self.keymap_combo)
        l1.addLayout(form1)
        l1.addStretch()
        self.stack.addWidget(p1)

        # Page 2: Gemini AI & Repositories
        p2 = QWidget()
        l2 = QVBoxLayout(p2)
        t2 = QLabel("Gemini AI & Package Bridges")
        t2.setObjectName("Title")
        l2.addWidget(t2)
        l2.addSpacing(10)
        self.api_edit = QLineEdit()
        self.api_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_edit.setPlaceholderText("Optional: Google Gemini API Key (AIza...)")
        self.arch_cb = QCheckBox("Enable Arch Linux Official Repository Bridge (`gem repo enable arch`)")
        self.arch_cb.setChecked(True)
        self.aur_cb = QCheckBox("Enable AUR Bridge (`yay` + `makepkg`)")
        self.aur_cb.setChecked(True)
        l2.addWidget(self.api_edit)
        l2.addSpacing(12)
        l2.addWidget(self.arch_cb)
        l2.addWidget(self.aur_cb)
        l2.addSpacing(16)
        self.summary_lbl = QLabel("")
        self.summary_lbl.setWordWrap(True)
        self.warn_lbl = QLabel("WARNING: All existing data on the selected disk will be erased!")
        self.warn_lbl.setObjectName("Warn")
        l2.addWidget(self.summary_lbl)
        l2.addWidget(self.warn_lbl)
        l2.addStretch()
        self.stack.addWidget(p2)

        # Page 3: Progress & Log
        p3 = QWidget()
        l3 = QVBoxLayout(p3)
        t3 = QLabel("✦ Installing GeminiOS 1.0.1...")
        t3.setObjectName("Title")
        self.status_lbl = QLabel("Starting installation...")
        self.pbar = QProgressBar()
        self.pbar.setRange(0, 100)
        self.promo_banner = create_opg_raduga_banner(p3)
        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)
        l3.addWidget(t3)
        l3.addWidget(self.status_lbl)
        l3.addWidget(self.pbar)
        l3.addSpacing(10)
        l3.addWidget(self.promo_banner)
        l3.addSpacing(10)
        l3.addWidget(self.log_box, 1)
        self.stack.addWidget(p3)

        # Navigation
        nav = QHBoxLayout()
        self.back_btn = QPushButton("Back")
        self.back_btn.setObjectName("Secondary")
        self.back_btn.clicked.connect(self.go_back)
        self.next_btn = QPushButton("Next")
        self.next_btn.clicked.connect(self.go_next)
        self.telegram_btn = QPushButton("Чат ОПГ «Радуга»")
        self.telegram_btn.setObjectName("TelegramBtn")
        self.telegram_btn.setVisible(False)
        self.telegram_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.telegram_btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://t.me/OPG_R4duga")))
        self.reboot_btn = QPushButton("Reboot Now")
        self.reboot_btn.setVisible(False)
        self.reboot_btn.clicked.connect(lambda: subprocess.Popen(["systemctl", "reboot"]))
        nav.addWidget(self.back_btn)
        nav.addStretch()
        nav.addWidget(self.telegram_btn)
        nav.addWidget(self.reboot_btn)
        nav.addWidget(self.next_btn)
        root.addLayout(nav)
        self._refresh_nav()

    def _refresh_nav(self):
        idx = self.stack.currentIndex()
        self.back_btn.setVisible(idx in (1, 2))
        if idx == 2:
            self.summary_lbl.setText(
                f"Target: {self.disk_combo.currentData()} ({self.fs_combo.currentText()})\n"
                f"User: {self.user_edit.text().strip()} @ {self.host_edit.text().strip()} ({self.tz_combo.currentText()})"
            )
            self.next_btn.setText("Erase Disk & Install")
            self.next_btn.setObjectName("Danger")
            self.next_btn.setStyleSheet(INSTALLER_QSS)
        elif idx == 3:
            self.next_btn.setVisible(False)
        else:
            self.next_btn.setText("Next")
            self.next_btn.setObjectName("")
            self.next_btn.setStyleSheet(INSTALLER_QSS)

    def go_back(self):
        self.stack.setCurrentIndex(max(0, self.stack.currentIndex() - 1))
        self._refresh_nav()

    def go_next(self):
        idx = self.stack.currentIndex()
        if idx == 0:
            if not self.disk_combo.currentData():
                QMessageBox.warning(self, "No Disk", "No target disk detected. Attach a disk in QEMU/VMware/PC first.")
                return
            self.stack.setCurrentIndex(1)
            self._refresh_nav()
        elif idx == 1:
            if not self.user_edit.text().strip():
                QMessageBox.warning(self, "Missing Username", "Please enter a username.")
                return
            if not self.pass_edit.text() or self.pass_edit.text() != self.pass2_edit.text():
                QMessageBox.warning(self, "Password Mismatch", "Passwords must not be empty and must match.")
                return
            self.stack.setCurrentIndex(2)
            self._refresh_nav()
        elif idx == 2:
            ans = QMessageBox.question(
                self,
                "Confirm Disk Erase",
                f"Erase ALL data on {self.disk_combo.currentData()} and install GeminiOS 1.0.1?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if ans != QMessageBox.StandardButton.Yes:
                return
            self.start_install()

    def start_install(self):
        self.stack.setCurrentIndex(3)
        self._refresh_nav()
        cmd = [
            "pkexec", "/usr/bin/python3", BACKEND_PATH,
            "--disk", self.disk_combo.currentData(),
            "--fs", self.fs_combo.currentText(),
            "--swap-gb", str(self.swap_combo.currentData()),
            "--username", self.user_edit.text().strip(),
            "--password", self.pass_edit.text(),
            "--hostname", self.host_edit.text().strip() or "geminios",
            "--timezone", self.tz_combo.currentText(),
            "--keymap", self.keymap_combo.currentText(),
        ]
        if self.api_edit.text().strip():
            cmd.extend(["--api-key", self.api_edit.text().strip()])
        if self.arch_cb.isChecked():
            cmd.append("--enable-arch")
        if self.aur_cb.isChecked():
            cmd.append("--enable-aur")

        self.worker = InstallWorker(cmd)
        self.worker.progress_sig.connect(self._on_progress)
        self.worker.log_sig.connect(self.log_box.append)
        self.worker.done_sig.connect(self._on_done)
        self.worker.start()

    def _on_progress(self, pct: int, msg: str):
        self.pbar.setValue(pct)
        self.status_lbl.setText(msg)

    def _on_done(self, ok: bool, msg: str):
        if ok:
            self.status_lbl.setText("✦ GeminiOS 1.0.1 успешно установлен! Залетайте в чат ОПГ «Радуга» (t.me/OPG_R4duga)!")
            self.pbar.setValue(100)
            self.telegram_btn.setVisible(True)
            self.reboot_btn.setVisible(True)
        else:
            self.status_lbl.setText(msg)
            QMessageBox.critical(self, "Installation Error", msg)


def main() -> int:
    app = QApplication(sys.argv)
    win = GeminiInstaller()
    win.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
