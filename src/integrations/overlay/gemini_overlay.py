#!/usr/bin/env python3
"""
GeminiOS Spotlight & AI Assistant Application (`gemini-overlay` / `gemini-spotlight`)
Full-fledged Material Design 3 Dark desktop AI application for GeminiOS.

Features:
- Full desktop application window (KDE Plasma 6 / Wayland / X11 taskbar & Alt+Tab integration)
- Never disappears or closes on window switch / focus loss
- Instant global toggle via Super+G (QLocalServer single-instance)
- Persistent multi-session chat history (~/.local/share/geminios/chats.json)
- Search filter across past conversation history
- Dynamic Material Design 3 Chat Bubbles with Markdown formatting and Copy button
- Modes: [💬 Чат], [⚡ Agent Mode], [🔍 Поиск], [💻 Код]
- Interactive Welcome Cards with instant prompt suggestions
- Export chat transcript to Markdown / Text
- Quick tools: System Doctor, Clipboard AI, Gemma Local, API Key, License Activation
- Stop generation support (via Stop button or Escape)
"""

import argparse
import datetime
import html
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Dict, List, Optional

from PyQt6.QtCore import QPoint, QSize, Qt, QThread, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QIcon, QKeySequence, QShortcut
from PyQt6.QtNetwork import QLocalServer, QLocalSocket
from PyQt6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QTextBrowser,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

GEMINID_URL = os.environ.get("GEMINID_URL", "http://127.0.0.1:11435")
SOCKET_NAME = f"geminios-overlay-{os.getuid()}" if hasattr(os, "getuid") else "geminios-overlay-sock"
STORAGE_DIR = Path.home() / ".local/share/geminios"
CHATS_FILE = STORAGE_DIR / "chats.json"

M3_STYLESHEET = """
QWidget#RootWindow {
    background-color: #111318;
    color: #E2E2E9;
    font-family: 'Roboto', 'Noto Sans', sans-serif;
}

/* Sidebar */
QFrame#Sidebar {
    background-color: #151820;
    border-right: 1px solid #282C38;
}

QLabel#SidebarTitle {
    color: #E2E2E9;
    font-size: 15px;
    font-weight: 700;
}

QLabel#SidebarSub {
    color: #8E9099;
    font-size: 11px;
}

QPushButton#NewChatBtn {
    background-color: #A8C7FA;
    color: #062E6F;
    border: none;
    border-radius: 14px;
    padding: 9px 16px;
    font-size: 13px;
    font-weight: 700;
}

QPushButton#NewChatBtn:hover {
    background-color: #C2E7FF;
}

QLineEdit#SearchBox {
    background-color: #1D212B;
    color: #E2E2E9;
    border: 1px solid #363C4C;
    border-radius: 12px;
    padding: 7px 12px;
    font-size: 12px;
}

QLineEdit#SearchBox:focus {
    border-color: #A8C7FA;
}

QListWidget#HistoryList {
    background: transparent;
    border: none;
    color: #C4C6D0;
    font-size: 12px;
}

QListWidget#HistoryList::item {
    border-radius: 10px;
    padding: 8px 10px;
    margin: 2px 0px;
}

QListWidget#HistoryList::item:hover {
    background-color: #212632;
    color: #E2E2E9;
}

QListWidget#HistoryList::item:selected {
    background-color: #26334D;
    color: #A8C7FA;
    font-weight: 600;
}

QPushButton#SidebarChip {
    background-color: #1C202A;
    color: #C4C6D0;
    border: 1px solid #323846;
    border-radius: 10px;
    padding: 6px 10px;
    font-size: 11px;
    font-weight: 500;
    text-align: left;
}

QPushButton#SidebarChip:hover {
    background-color: #272E3D;
    color: #A8C7FA;
    border-color: #A8C7FA;
}

/* Main Chat Area */
QFrame#ChatArea {
    background-color: #111318;
}

QLabel#ChatHeaderTitle {
    color: #E2E2E9;
    font-size: 15px;
    font-weight: 600;
}

QLabel#BackendBadge {
    color: #A8C7FA;
    background-color: #182234;
    border: 1px solid #334460;
    border-radius: 10px;
    padding: 4px 12px;
    font-size: 11px;
    font-weight: 600;
}

/* Mode Switcher Chips */
QPushButton#ModeChip {
    background-color: #1C202A;
    color: #C4C6D0;
    border: 1px solid #323846;
    border-radius: 13px;
    padding: 5px 14px;
    font-size: 12px;
    font-weight: 500;
}

QPushButton#ModeChip:hover {
    background-color: #262D3C;
    color: #E2E2E9;
}

QPushButton#ModeChip:checked {
    background-color: #A8C7FA;
    color: #062E6F;
    border: none;
    font-weight: 700;
}

QPushButton#HeaderActionBtn {
    background-color: #1D212B;
    color: #C4C6D0;
    border: 1px solid #363C4C;
    border-radius: 10px;
    padding: 5px 10px;
    font-size: 12px;
}

QPushButton#HeaderActionBtn:hover {
    background-color: #282F3E;
    color: #A8C7FA;
}

/* Scroll Area */
QScrollArea#MessageScroll {
    background: transparent;
    border: none;
}

QWidget#MessageContainer {
    background: transparent;
}

/* Chat Input Bar */
QFrame#InputContainer {
    background-color: #191D26;
    border: 1px solid #373D4D;
    border-radius: 18px;
    padding: 4px 8px;
}

QFrame#InputContainer:focus-within {
    border-color: #A8C7FA;
}

QTextEdit#InputEdit {
    background: transparent;
    color: #E2E2E9;
    border: none;
    font-size: 13px;
    padding: 6px 8px;
}

QPushButton#SendBtn {
    background-color: #A8C7FA;
    color: #062E6F;
    border: none;
    border-radius: 16px;
    width: 36px;
    height: 36px;
    font-size: 15px;
    font-weight: 700;
}

QPushButton#SendBtn:hover {
    background-color: #C2E7FF;
}

QPushButton#SendBtn:disabled {
    background-color: #262B36;
    color: #616776;
}

QPushButton#StopBtn {
    background-color: #93000A;
    color: #FFDAD6;
    border: none;
    border-radius: 16px;
    padding: 6px 14px;
    font-size: 12px;
    font-weight: 600;
}

QPushButton#StopBtn:hover {
    background-color: #BA1A1A;
}

/* Suggestion Card */
QPushButton#SuggestCard {
    background-color: #191D26;
    color: #C4C6D0;
    border: 1px solid #303644;
    border-radius: 14px;
    padding: 12px 16px;
    font-size: 12px;
    text-align: left;
}

QPushButton#SuggestCard:hover {
    background-color: #242B39;
    color: #E2E2E9;
    border-color: #A8C7FA;
}

/* Action icons */
QPushButton#TrashBtn {
    background: transparent;
    color: #8E9099;
    border: none;
    font-size: 11px;
    padding: 4px;
}

QPushButton#TrashBtn:hover {
    color: #FFB4AB;
}
"""


class GeminiWorker(QThread):
    finished = pyqtSignal(dict)

    def __init__(self, prompt: str, mode: str):
        super().__init__()
        self.prompt = prompt
        self.mode = mode

    def run(self):
        is_agent = (self.mode == "agent")
        endpoint = "/v1/agent/plan" if is_agent else "/v1/chat"
        payload = {"goal": self.prompt} if is_agent else {"prompt": self.prompt, "prefer": "auto"}

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
            self.finished.emit({"ok": False, "response": f"geminid daemon unreachable: {exc}"})


class MessageBubble(QFrame):
    """Material Design 3 Message Bubble with Markdown formatting and Copy button."""

    def __init__(self, role: str, text: str, timestamp: str = "", backend: str = ""):
        super().__init__()
        self.setFrameShape(QFrame.Shape.NoFrame)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 4)

        bubble = QFrame()
        bubble_layout = QVBoxLayout(bubble)
        bubble_layout.setContentsMargins(14, 10, 14, 10)
        bubble_layout.setSpacing(6)

        if role == "user":
            bubble.setStyleSheet("""
                QFrame {
                    background-color: #0B57D0;
                    border-radius: 18px;
                    border-top-right-radius: 4px;
                }
            """)
            meta = QLabel(f"You · {timestamp}")
            meta.setStyleSheet("color: #D3E3FD; font-size: 11px; font-weight: 600;")
            bubble_layout.addWidget(meta)

            content = QLabel(text)
            content.setStyleSheet("color: #FFFFFF; font-size: 13px; line-height: 1.4;")
            content.setWordWrap(True)
            content.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            bubble_layout.addWidget(content)

            row = QHBoxLayout()
            row.addStretch()
            row.addWidget(bubble)
            layout.addLayout(row)
        else:
            bubble.setStyleSheet("""
                QFrame {
                    background-color: #191D26;
                    border: 1px solid #303746;
                    border-radius: 18px;
                    border-top-left-radius: 4px;
                }
            """)
            header_row = QHBoxLayout()
            badge = QLabel(f"✦ Gemini ({backend or 'AI'}) · {timestamp}")
            badge.setStyleSheet("color: #A8C7FA; font-size: 11px; font-weight: 600;")
            header_row.addWidget(badge)
            header_row.addStretch()

            copy_btn = QPushButton("Скопировать")
            copy_btn.setStyleSheet("""
                QPushButton {
                    background-color: #242A38;
                    color: #C4C6D0;
                    border: 1px solid #3A4356;
                    border-radius: 8px;
                    padding: 3px 10px;
                    font-size: 10px;
                    font-weight: 500;
                }
                QPushButton:hover {
                    background-color: #313A4D;
                    color: #A8C7FA;
                }
            """)

            def on_copy():
                QApplication.clipboard().setText(text)
                copy_btn.setText("Скопировано! ✓")

            copy_btn.clicked.connect(on_copy)
            header_row.addWidget(copy_btn)
            bubble_layout.addLayout(header_row)

            # Rich text / formatted content
            content = QTextBrowser()
            content.setOpenExternalLinks(True)
            content.setReadOnly(True)
            content.setStyleSheet("""
                QTextBrowser {
                    background: transparent;
                    color: #E2E2E9;
                    border: none;
                    font-size: 13px;
                }
            """)
            content.setHtml(self._format_markdown_html(text))
            content.document().adjustSize()
            doc_h = int(content.document().size().height())
            content.setFixedHeight(max(32, doc_h + 16))
            bubble_layout.addWidget(content)

            row = QHBoxLayout()
            row.addWidget(bubble)
            row.addStretch()
            layout.addLayout(row)

    def _format_markdown_html(self, raw: str) -> str:
        escaped = html.escape(raw)
        lines = []
        in_code = False
        code_buf = []

        for line in escaped.splitlines():
            if line.startswith("```"):
                if in_code:
                    code_html = "\n".join(code_buf)
                    lines.append(f"<pre style='background:#12151D; color:#A8C7FA; padding:10px; border-radius:8px; font-family:JetBrains Mono, monospace;'>{code_html}</pre>")
                    code_buf = []
                    in_code = False
                else:
                    in_code = True
                continue
            if in_code:
                code_buf.append(line)
            else:
                if line.startswith("# "):
                    lines.append(f"<h2 style='color:#A8C7FA; margin:6px 0;'>{line[2:]}</h2>")
                elif line.startswith("## "):
                    lines.append(f"<h3 style='color:#E2E2E9; margin:4px 0;'>{line[3:]}</h3>")
                elif line.startswith("### "):
                    lines.append(f"<h4 style='color:#A8C7FA; margin:3px 0;'>{line[4:]}</h4>")
                elif line.startswith("- ") or line.startswith("* "):
                    content = line[2:]
                    content = re.sub(r"\*\*(.+?)\*\*", r"<b style='color:#FFFFFF;'>\1</b>", content)
                    content = re.sub(r"`([^`]+?)`", r"<code style='background:#12151D; color:#A8C7FA; padding:2px 4px; border-radius:4px; font-family:JetBrains Mono, monospace;'>\1</code>", content)
                    lines.append(f"<div style='margin-left:14px; margin-top:2px;'>• {content}</div>")
                else:
                    content = re.sub(r"\*\*(.+?)\*\*", r"<b style='color:#FFFFFF;'>\1</b>", line)
                    content = re.sub(r"(?<!\*)\*([^\*\n]+?)\*(?!\*)", r"<i>\1</i>", content)
                    content = re.sub(r"`([^`]+?)`", r"<code style='background:#12151D; color:#A8C7FA; padding:2px 4px; border-radius:4px; font-family:JetBrains Mono, monospace;'>\1</code>", content)
                    lines.append(f"<p style='margin:4px 0;'>{content}</p>")

        if in_code and code_buf:
            code_html = "\n".join(code_buf)
            lines.append(f"<pre style='background:#12151D; color:#A8C7FA; padding:10px; border-radius:8px; font-family:JetBrains Mono, monospace;'>{code_html}</pre>")

        return "".join(lines)


class GeminiSpotlightWindow(QWidget):
    """Full-featured Material Design 3 Desktop Application with Persistent History."""

    def __init__(self, initial_prompt: str = ""):
        super().__init__()
        self.setObjectName("RootWindow")
        # Standard top-level application window: shows in taskbar, Alt+Tab, and remains open on focus switch
        self.setWindowFlags(Qt.WindowType.Window)
        self.setWindowTitle("Gemini Spotlight")
        self.resize(1020, 680)
        self.setMinimumSize(780, 520)
        self.setStyleSheet(M3_STYLESHEET)

        # Set application icon
        icon_path = Path("/usr/share/icons/hicolor/scalable/apps/gemini-spotlight.svg")
        if not icon_path.exists():
            local_svg = Path(__file__).resolve().parent.parent / "themes/plasma-m3/icons/gemini-spotlight.svg"
            if local_svg.exists():
                icon_path = local_svg
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))

        self.sessions: List[Dict] = []
        self.current_session_id: Optional[str] = None
        self.active_mode = "chat"
        self.worker: Optional[GeminiWorker] = None

        self._init_ui()
        self._load_history()
        self.refresh_status()

        # Keyboard shortcuts (Esc stops current generation or clears input, never kills app)
        QShortcut(QKeySequence("Escape"), self, self.on_escape)
        QShortcut(QKeySequence("Ctrl+N"), self, self.on_new_chat)
        QShortcut(QKeySequence("Ctrl+Q"), self, self.full_quit)
        QShortcut(QKeySequence("Ctrl+W"), self, self.hide)
        QShortcut(QKeySequence("Ctrl+S"), self, self.on_export_chat)

        if initial_prompt:
            self.input_edit.setPlainText(initial_prompt)
            self.on_send()

    def closeEvent(self, event):
        # Hiding keeps daemon single-instance listener alive for instant Super+G toggle
        self.hide()
        event.ignore()

    def full_quit(self):
        QApplication.quit()

    def on_escape(self):
        if self.worker and self.worker.isRunning():
            self.worker.terminate()
            self.backend_badge.setText("● Остановлено")
            self.send_btn.setEnabled(True)
            self.stop_btn.setVisible(False)
        elif self.input_edit.toPlainText().strip():
            self.input_edit.clear()

    def _init_ui(self):
        root_layout = QHBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setStyleSheet("QSplitter::handle { background: transparent; }")

        # 1. Left Sidebar
        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(280)
        side_layout = QVBoxLayout(sidebar)
        side_layout.setContentsMargins(16, 16, 16, 14)
        side_layout.setSpacing(10)

        title_box = QHBoxLayout()
        logo_lbl = QLabel("✦")
        logo_lbl.setStyleSheet("color:#A8C7FA; font-size:22px; font-weight:bold;")
        brand_col = QVBoxLayout()
        brand_col.setSpacing(1)
        b_name = QLabel("Gemini Spotlight")
        b_name.setObjectName("SidebarTitle")
        b_tag = QLabel("GeminiOS 1.0 · Material Design 3")
        b_tag.setObjectName("SidebarSub")
        brand_col.addWidget(b_name)
        brand_col.addWidget(b_tag)
        title_box.addWidget(logo_lbl)
        title_box.addLayout(brand_col)
        title_box.addStretch()
        side_layout.addLayout(title_box)

        new_btn = QPushButton("+ Новый диалог")
        new_btn.setObjectName("NewChatBtn")
        new_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        new_btn.clicked.connect(self.on_new_chat)
        side_layout.addWidget(new_btn)

        self.search_box = QLineEdit()
        self.search_box.setObjectName("SearchBox")
        self.search_box.setPlaceholderText("Поиск по диалогам...")
        self.search_box.textChanged.connect(self._on_search_history)
        side_layout.addWidget(self.search_box)

        hist_lbl = QLabel("История диалогов")
        hist_lbl.setStyleSheet("color:#8E9099; font-size:11px; font-weight:600; text-transform:uppercase;")
        side_layout.addWidget(hist_lbl)

        self.history_list = QListWidget()
        self.history_list.setObjectName("HistoryList")
        self.history_list.currentRowChanged.connect(self._on_session_selected)
        side_layout.addWidget(self.history_list, 1)

        # Bottom Quick Action Chips in Sidebar
        quick_grid = QVBoxLayout()
        quick_grid.setSpacing(6)
        for label, cb in [
            ("✦ Активация GeminiOS", self.on_activate_system),
            ("✦ Ключ Google Gemini API", self.on_set_api_key),
            ("✦ Системный доктор", self.on_run_doctor),
            ("✦ Анализ буфера обмена", self.on_analyze_clipboard),
            ("✦ Локальный движок Gemma", self.on_enable_gemma),
        ]:
            b = QPushButton(label)
            b.setObjectName("SidebarChip")
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(cb)
            quick_grid.addWidget(b)
        side_layout.addLayout(quick_grid)

        del_all_btn = QPushButton("🗑 Очистить всю историю")
        del_all_btn.setObjectName("TrashBtn")
        del_all_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        del_all_btn.clicked.connect(self.on_clear_all_history)
        side_layout.addWidget(del_all_btn)

        splitter.addWidget(sidebar)

        # 2. Main Chat Area
        chat_area = QFrame()
        chat_area.setObjectName("ChatArea")
        chat_layout = QVBoxLayout(chat_area)
        chat_layout.setContentsMargins(20, 16, 20, 16)
        chat_layout.setSpacing(10)

        # Top Bar
        top_bar = QHBoxLayout()
        self.mode_chat = QPushButton("💬 Чат")
        self.mode_chat.setObjectName("ModeChip")
        self.mode_chat.setCheckable(True)
        self.mode_chat.setChecked(True)
        self.mode_chat.clicked.connect(lambda: self._set_mode("chat"))

        self.mode_agent = QPushButton("⚡ Agent Mode")
        self.mode_agent.setObjectName("ModeChip")
        self.mode_agent.setCheckable(True)
        self.mode_agent.clicked.connect(lambda: self._set_mode("agent"))

        self.mode_search = QPushButton("🔍 Поиск")
        self.mode_search.setObjectName("ModeChip")
        self.mode_search.setCheckable(True)
        self.mode_search.clicked.connect(lambda: self._set_mode("search"))

        self.mode_code = QPushButton("💻 Код")
        self.mode_code.setObjectName("ModeChip")
        self.mode_code.setCheckable(True)
        self.mode_code.clicked.connect(lambda: self._set_mode("code"))

        top_bar.addWidget(self.mode_chat)
        top_bar.addWidget(self.mode_agent)
        top_bar.addWidget(self.mode_search)
        top_bar.addWidget(self.mode_code)
        top_bar.addStretch()

        self.backend_badge = QLabel("Проверка бэкенда...")
        self.backend_badge.setObjectName("BackendBadge")
        top_bar.addWidget(self.backend_badge)

        export_btn = QPushButton("💾 Экспорт")
        export_btn.setObjectName("HeaderActionBtn")
        export_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        export_btn.setToolTip("Экспортировать текущий диалог в файл Markdown")
        export_btn.clicked.connect(self.on_export_chat)
        top_bar.addWidget(export_btn)

        clear_chat_btn = QPushButton("🗑 Очистить")
        clear_chat_btn.setObjectName("HeaderActionBtn")
        clear_chat_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        clear_chat_btn.setToolTip("Очистить сообщения в текущем диалоге")
        clear_chat_btn.clicked.connect(self.on_clear_current_chat)
        top_bar.addWidget(clear_chat_btn)

        chat_layout.addLayout(top_bar)

        # Scroll Area for Messages
        self.scroll = QScrollArea()
        self.scroll.setObjectName("MessageScroll")
        self.scroll.setWidgetResizable(True)
        self.msg_container = QWidget()
        self.msg_container.setObjectName("MessageContainer")
        self.msg_layout = QVBoxLayout(self.msg_container)
        self.msg_layout.setContentsMargins(4, 4, 4, 4)
        self.msg_layout.setSpacing(10)
        self.msg_layout.addStretch()
        self.scroll.setWidget(self.msg_container)
        chat_layout.addWidget(self.scroll, 1)

        # Bottom Input Bar
        input_container = QFrame()
        input_container.setObjectName("InputContainer")
        input_box = QHBoxLayout(input_container)
        input_box.setContentsMargins(8, 4, 8, 4)
        input_box.setSpacing(8)

        self.input_edit = QTextEdit()
        self.input_edit.setObjectName("InputEdit")
        self.input_edit.setPlaceholderText("Спросите Gemini о чем угодно или опишите задачу... (Enter — отправить, Shift+Enter — новая строка)")
        self.input_edit.setFixedHeight(48)
        self.input_edit.installEventFilter(self)
        input_box.addWidget(self.input_edit, 1)

        self.stop_btn = QPushButton("⏹ Стоп")
        self.stop_btn.setObjectName("StopBtn")
        self.stop_btn.setVisible(False)
        self.stop_btn.clicked.connect(self.on_escape)
        input_box.addWidget(self.stop_btn)

        self.send_btn = QPushButton("➤")
        self.send_btn.setObjectName("SendBtn")
        self.send_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.send_btn.clicked.connect(self.on_send)
        input_box.addWidget(self.send_btn)

        chat_layout.addWidget(input_container)

        splitter.addWidget(chat_area)
        root_layout.addWidget(splitter)

    def eventFilter(self, obj, event):
        if obj == self.input_edit and event.type() == event.Type.KeyPress:
            if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                    return False
                self.on_send()
                return True
        return super().eventFilter(obj, event)

    def _set_mode(self, mode: str):
        self.active_mode = mode
        self.mode_chat.setChecked(mode == "chat")
        self.mode_agent.setChecked(mode == "agent")
        self.mode_search.setChecked(mode == "search")
        self.mode_code.setChecked(mode == "code")
        if mode == "agent":
            self.input_edit.setPlaceholderText("Опишите системную цель (например: 'установи nginx и настрой автозапуск')...")
        elif mode == "search":
            self.input_edit.setPlaceholderText("Поиск по репозиториям пакетов gem, файлам или документации...")
        elif mode == "code":
            self.input_edit.setPlaceholderText("Напишите задачу по коду (Bash, Python, C, Rust)...")
        else:
            self.input_edit.setPlaceholderText("Спросите Gemini о чем угодно... (Enter — отправить, Shift+Enter — новая строка)")

    def _load_history(self):
        STORAGE_DIR.mkdir(parents=True, exist_ok=True)
        if CHATS_FILE.exists():
            try:
                data = json.loads(CHATS_FILE.read_text(encoding="utf-8"))
                self.sessions = data.get("chats", [])
            except Exception:
                self.sessions = []
        if not self.sessions:
            self._create_session("Новый диалог")
        self._refresh_history_list()

    def _save_history(self):
        STORAGE_DIR.mkdir(parents=True, exist_ok=True)
        payload = {"chats": self.sessions}
        CHATS_FILE.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    def _on_search_history(self, query: str):
        query = query.strip().lower()
        self.history_list.blockSignals(True)
        self.history_list.clear()
        for s in self.sessions:
            title = s.get("title", "Диалог")
            if not query or query in title.lower():
                item = QListWidgetItem(f"💬 {title}")
                item.setData(Qt.ItemDataRole.UserRole, s.get("id"))
                self.history_list.addItem(item)
        self.history_list.blockSignals(False)

    def _refresh_history_list(self):
        self.search_box.clear()
        self.history_list.blockSignals(True)
        self.history_list.clear()
        for s in self.sessions:
            item = QListWidgetItem(f"💬 {s.get('title', 'Диалог')}")
            item.setData(Qt.ItemDataRole.UserRole, s.get("id"))
            self.history_list.addItem(item)
        self.history_list.blockSignals(False)

        if self.sessions:
            idx = 0
            for i, s in enumerate(self.sessions):
                if s.get("id") == self.current_session_id:
                    idx = i
                    break
            self.history_list.setCurrentRow(idx)
            self._load_session_messages(self.sessions[idx])

    def _create_session(self, title: str = "Новый диалог") -> Dict:
        sid = f"chat_{int(time.time())}_{len(self.sessions) + 1}"
        session = {
            "id": sid,
            "title": title,
            "created_at": time.time(),
            "messages": [],
        }
        self.sessions.insert(0, session)
        self.current_session_id = sid
        self._save_history()
        return session

    def on_new_chat(self):
        self._create_session("Новый диалог")
        self._refresh_history_list()
        self.input_edit.clear()
        self.input_edit.setFocus()

    def _on_session_selected(self, row: int):
        if 0 <= row < len(self.sessions):
            session = self.sessions[row]
            self.current_session_id = session.get("id")
            self._load_session_messages(session)

    def _load_session_messages(self, session: Dict):
        # Clear existing message widgets (except bottom stretch)
        while self.msg_layout.count() > 1:
            child = self.msg_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        msgs = session.get("messages", [])
        if not msgs:
            # Interactive Material Design 3 Welcome Cards
            welcome_widget = QWidget()
            w_layout = QVBoxLayout(welcome_widget)
            w_layout.setContentsMargins(20, 30, 20, 20)
            w_layout.setSpacing(16)

            spark_icon = QLabel("✦")
            spark_icon.setStyleSheet("color:#A8C7FA; font-size:42px; font-weight:bold;")
            spark_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
            w_layout.addWidget(spark_icon)

            welcome_title = QLabel("Чем я могу помочь в GeminiOS?")
            welcome_title.setStyleSheet("color:#E2E2E9; font-size:18px; font-weight:600;")
            welcome_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
            w_layout.addWidget(welcome_title)

            welcome_sub = QLabel("Задавайте вопросы, выполняйте системные команды или используйте быстрые подсказки:")
            welcome_sub.setStyleSheet("color:#8E9099; font-size:12px;")
            welcome_sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
            w_layout.addWidget(welcome_sub)

            cards_box = QVBoxLayout()
            cards_box.setSpacing(8)

            suggestions = [
                ("🔍 Как обновлять систему и пакеты через менеджер `gem`?", "Как обновлять систему и пакеты через менеджер gem?"),
                ("⚡ Напиши bash-скрипт для резервного копирования домашней папки", "Напиши надежный bash-скрипт для резервного копирования домашней папки с ротацией архивов."),
                ("🛠 Проверь сетевые сервисы и статус дисков на сервере", "Проверь сетевые сервисы и статус дисков в GeminiOS, покажи полезные диагностические команды."),
                ("💻 Объясни разницу между Wayland и X11 в KDE Plasma 6", "Объясни ключевые различия между сессией Wayland и X11 в среде KDE Plasma 6."),
            ]

            for label, prompt in suggestions:
                btn = QPushButton(label)
                btn.setObjectName("SuggestCard")
                btn.setCursor(Qt.CursorShape.PointingHandCursor)
                btn.clicked.connect(lambda _, p=prompt: self._trigger_suggestion(p))
                cards_box.addWidget(btn)

            w_layout.addLayout(cards_box)
            self.msg_layout.insertWidget(0, welcome_widget)
        else:
            for m in msgs:
                bubble = MessageBubble(
                    role=m.get("role", "user"),
                    text=m.get("content", ""),
                    timestamp=m.get("time", ""),
                    backend=m.get("backend", ""),
                )
                self.msg_layout.insertWidget(self.msg_layout.count() - 1, bubble)

        self._scroll_to_bottom()

    def _trigger_suggestion(self, prompt: str):
        self.input_edit.setPlainText(prompt)
        self.on_send()

    def _scroll_to_bottom(self):
        QApplication.processEvents()
        self.scroll.verticalScrollBar().setValue(self.scroll.verticalScrollBar().maximum())

    def on_send(self):
        text = self.input_edit.toPlainText().strip()
        if not text:
            return

        now_str = datetime.datetime.now().strftime("%H:%M")
        current_sess = None
        for s in self.sessions:
            if s.get("id") == self.current_session_id:
                current_sess = s
                break
        if not current_sess:
            current_sess = self._create_session("Новый диалог")

        if current_sess.get("title") in ("Новый диалог", "New Conversation", ""):
            first_words = " ".join(text.split()[:5])
            current_sess["title"] = first_words[:32]
            self._refresh_history_list()

        # If welcome screen was shown, clear it
        if not current_sess.get("messages"):
            while self.msg_layout.count() > 1:
                child = self.msg_layout.takeAt(0)
                if child.widget():
                    child.widget().deleteLater()

        current_sess["messages"].append({"role": "user", "content": text, "time": now_str})
        self._save_history()

        bubble = MessageBubble(role="user", text=text, timestamp=now_str)
        self.msg_layout.insertWidget(self.msg_layout.count() - 1, bubble)
        self.input_edit.clear()
        self._scroll_to_bottom()

        # Built-in activation trigger
        if text.lower().strip() in ("activate", "активировать", "активация", "активируй", "активируй систему"):
            token = f"GEMINIOS-PRO-{int(time.time())}"
            user_act = Path.home() / ".config/geminios-activated"
            user_act.parent.mkdir(parents=True, exist_ok=True)
            user_act.write_text(f"ACTIVATED=true\nKEY={token}\nTIMESTAMP={int(time.time())}\n", encoding="utf-8")
            try:
                Path("/etc/geminios-activated").write_text(f"ACTIVATED=true\nKEY={token}\nTIMESTAMP={int(time.time())}\n", encoding="utf-8")
            except Exception:
                pass
            subprocess.run(["pkill", "-f", "activation_watermark.py"], check=False)
            reply = f"✦ **GeminiOS успешно активирован!**\n\n- Лицензия: **Gemini Pro Cognitive Core**\n- Ключ активации: `{token}`\n- Водяной знак активации удалён с экрана рабочего стола."
            current_sess["messages"].append({"role": "assistant", "content": reply, "time": now_str, "backend": "System"})
            self._save_history()
            bubble = MessageBubble(role="assistant", text=reply, timestamp=now_str, backend="System")
            self.msg_layout.insertWidget(self.msg_layout.count() - 1, bubble)
            self._scroll_to_bottom()
            return

        self.send_btn.setEnabled(False)
        self.stop_btn.setVisible(True)
        self.backend_badge.setText("✦ Gemini думает...")

        self.worker = GeminiWorker(text, self.active_mode)
        self.worker.finished.connect(self._on_ai_response)
        self.worker.start()

    def _on_ai_response(self, data: dict):
        self.send_btn.setEnabled(True)
        self.stop_btn.setVisible(False)
        self.refresh_status()
        now_str = datetime.datetime.now().strftime("%H:%M")

        if not data.get("ok"):
            err_msg = data.get("response", "Не удалось связаться с Gemini AI.")
            ans = f"**Ошибка**: {err_msg}\n\n*Совет: Нажмите «✦ Ключ Google Gemini API» на панели слева для настройки ключа.*"
            backend = "Error"
        elif "plan" in data:
            plan = data["plan"]
            lines = [f"**План действий Агента**: {plan.get('summary', '')}\n"]
            for idx, step in enumerate(plan.get("steps", []), 1):
                risk = step.get("risk", "safe").upper()
                lines.append(f"{idx}. `[{risk}]` `${step['cmd']}`")
                if step.get("reason"):
                    lines.append(f"   *{step['reason']}*")
            ans = "\n".join(lines)
            backend = "Agent"

            # Execute safe commands if confirmed
            for step in plan.get("steps", []):
                if step.get("risk") == "destructive":
                    continue
                reply = QMessageBox.question(
                    self,
                    "Подтверждение действия Gemini Agent",
                    f"Выполнить запланированную команду?\n\n{step['cmd']}\n\nПричина: {step.get('reason', '')}",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                )
                if reply == QMessageBox.StandardButton.Yes:
                    req = urllib.request.Request(
                        f"{GEMINID_URL}/v1/agent/execute",
                        data=json.dumps({"cmd": step["cmd"], "confirmed": True}).encode("utf-8"),
                        headers={"Content-Type": "application/json"},
                        method="POST",
                    )
                    try:
                        with urllib.request.urlopen(req, timeout=120) as resp:
                            res = json.loads(resp.read().decode("utf-8"))
                        ans += f"\n\n**Результат `{step['cmd']}`**:\n```\n{res.get('stdout', '')}{res.get('stderr', '')}\n```"
                    except Exception as exc:
                        ans += f"\n\n**Ошибка выполнения**: {exc}"
        else:
            ans = data.get("response", "")
            backend = data.get("backend", "Gemini")

        for s in self.sessions:
            if s.get("id") == self.current_session_id:
                s["messages"].append({"role": "assistant", "content": ans, "time": now_str, "backend": backend})
                break
        self._save_history()

        bubble = MessageBubble(role="assistant", text=ans, timestamp=now_str, backend=backend)
        self.msg_layout.insertWidget(self.msg_layout.count() - 1, bubble)
        self._scroll_to_bottom()

    def refresh_status(self):
        try:
            with urllib.request.urlopen(f"{GEMINID_URL}/v1/status", timeout=2) as resp:
                st = json.loads(resp.read().decode("utf-8"))
            if st.get("cloud_configured"):
                self.backend_badge.setText(f"🟢 Gemini Cloud ({st.get('cloud_model', '2.5 Flash')})")
            elif st.get("fallback_enabled"):
                self.backend_badge.setText(f"🟢 Gemma Local ({st.get('fallback_model', '2B')})")
            else:
                self.backend_badge.setText("🟡 Требуется API Key")
        except Exception:
            self.backend_badge.setText("⚪ geminid offline")

    def on_set_api_key(self):
        key, ok = QInputDialog.getText(
            self,
            "Google Gemini API Key",
            "Введите ваш ключ Google Gemini API (AIza...):",
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
                self.refresh_status()
                QMessageBox.information(self, "Ключ сохранен", "Google Gemini API ключ успешно сохранен и активирован!")
            except Exception as exc:
                QMessageBox.warning(self, "Ошибка", f"Не удалось сохранить ключ: {exc}")

    def on_run_doctor(self):
        subprocess.Popen(["konsole", "--hold", "-e", "gemini-doctor"])

    def on_analyze_clipboard(self):
        clip = QApplication.clipboard().text().strip()
        if not clip:
            QMessageBox.information(self, "Буфер обмена", "Буфер обмена в данный момент пуст.")
            return
        self.input_edit.setPlainText(f"Объясни или исправь содержимое буфера обмена:\n{clip[:4000]}")
        self.on_send()

    def on_enable_gemma(self):
        subprocess.Popen(["konsole", "--hold", "-e", "gemini", "enable-gemma"])

    def on_export_chat(self):
        current_sess = None
        for s in self.sessions:
            if s.get("id") == self.current_session_id:
                current_sess = s
                break
        if not current_sess or not current_sess.get("messages"):
            QMessageBox.information(self, "Экспорт", "В текущем диалоге пока нет сообщений для экспорта.")
            return

        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Экспортировать диалог",
            str(Path.home() / f"{current_sess.get('title', 'chat')[:20]}.md"),
            "Markdown (*.md);;Text (*.txt)",
        )
        if filename:
            content = [f"# {current_sess.get('title', 'Диалог с Gemini')}\n\n"]
            for m in current_sess.get("messages", []):
                role = "Пользователь" if m.get("role") == "user" else "Gemini"
                content.append(f"### {role} ({m.get('time', '')})\n{m.get('content', '')}\n\n")
            Path(filename).write_text("".join(content), encoding="utf-8")
            QMessageBox.information(self, "Экспорт завершен", f"Диалог успешно сохранен в:\n{filename}")

    def on_clear_current_chat(self):
        current_sess = None
        for s in self.sessions:
            if s.get("id") == self.current_session_id:
                current_sess = s
                break
        if current_sess:
            current_sess["messages"] = []
            self._save_history()
            self._load_session_messages(current_sess)

    def on_clear_all_history(self):
        reply = QMessageBox.question(
            self,
            "Очистить историю",
            "Вы уверены, что хотите удалить всю историю диалогов?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.sessions = []
            if CHATS_FILE.exists():
                CHATS_FILE.unlink(missing_ok=True)
            self._create_session("Новый диалог")
            self._refresh_history_list()

    def on_activate_system(self):
        key, ok = QInputDialog.getText(
            self,
            "Активация GeminiOS",
            "Введите ключ активации GeminiOS (или оставьте пустым для автоматической активации):",
            QLineEdit.EchoMode.Normal,
        )
        if ok:
            token = key.strip() or f"GEMINIOS-PRO-{int(time.time())}"
            user_act = Path.home() / ".config/geminios-activated"
            user_act.parent.mkdir(parents=True, exist_ok=True)
            user_act.write_text(f"ACTIVATED=true\nKEY={token}\nTIMESTAMP={int(time.time())}\n", encoding="utf-8")
            try:
                Path("/etc/geminios-activated").write_text(f"ACTIVATED=true\nKEY={token}\nTIMESTAMP={int(time.time())}\n", encoding="utf-8")
            except Exception:
                pass
            subprocess.run(["pkill", "-f", "activation_watermark.py"], check=False)
            QMessageBox.information(
                self,
                "Активация завершена",
                f"✦ GeminiOS успешно активирован!\nЛицензия: Pro Cognitive Core\nКлюч: {token}\n\nВодяной знак активации удалён с экрана.",
            )

    def toggle_window(self):
        if self.isVisible() and not self.isMinimized() and self.isActiveWindow():
            self.hide()
        else:
            self.show()
            self.setWindowState(self.windowState() & ~Qt.WindowState.WindowMinimized | Qt.WindowState.WindowActive)
            self.raise_()
            self.activateWindow()
            self.input_edit.setFocus()


def main() -> int:
    parser = argparse.ArgumentParser(description="Gemini Spotlight Application")
    parser.add_argument("--prompt", default="", help="Initial prompt to ask immediately")
    parser.add_argument("--toggle", action="store_true", help="Toggle existing window")
    args, qt_args = parser.parse_known_args()

    app = QApplication([sys.argv[0]] + qt_args)
    app.setApplicationName("Gemini Spotlight")
    app.setDesktopFileName("geminios-overlay.desktop")

    # Single-instance handling via QLocalSocket
    test_socket = QLocalSocket()
    test_socket.connectToServer(SOCKET_NAME)
    if test_socket.waitForConnected(300):
        msg = json.dumps({"action": "toggle", "prompt": args.prompt})
        test_socket.write(msg.encode("utf-8"))
        test_socket.flush()
        test_socket.waitForBytesWritten(500)
        test_socket.disconnectFromServer()
        return 0

    # Start primary application instance
    win = GeminiSpotlightWindow(initial_prompt=args.prompt)

    server = QLocalServer()
    server.removeServer(SOCKET_NAME)
    if server.listen(SOCKET_NAME):
        def handle_client():
            client = server.nextPendingConnection()
            if client and client.waitForReadyRead(500):
                try:
                    payload = json.loads(client.readAll().data().decode("utf-8"))
                    prompt = payload.get("prompt", "")
                    if prompt:
                        win.input_edit.setPlainText(prompt)
                        win.on_send()
                    win.toggle_window()
                except Exception:
                    win.toggle_window()
                client.disconnectFromServer()
        server.newConnection.connect(handle_client)

    screen = app.primaryScreen().availableGeometry()
    win.move(
        screen.center().x() - win.width() // 2,
        screen.top() + int(screen.height() * 0.10),
    )
    win.show()
    win.input_edit.setFocus()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
