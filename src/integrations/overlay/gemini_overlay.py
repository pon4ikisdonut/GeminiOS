#!/usr/bin/env python3
"""
GeminiOS Global Spotlight & AI Assistant Overlay (`gemini-overlay`)
Material Design 3 Dark floating assistant bound to Super+G in KDE Plasma 6.

Features:
- Persistent Multi-Session Chat History (~/.local/share/geminios/chats.json)
- Sidebar with "+ New Chat", past sessions list, and delete actions
- Material Design 3 Chat Bubbles (User in Google Blue, Gemini in Surface Container)
- Mode Chips: [💬 Chat], [⚡ Agent Mode], [🔍 Deep Search]
- Quick Action Chips: [✦ API Key], [✦ System Doctor], [✦ Explain Clipboard]
- Code block formatting with Copy button
- Instant single-instance toggle via QLocalServer (Super+G toggles show/hide)
"""

import argparse
import datetime
import json
import os
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

GEMINID_URL = "http://127.0.0.1:11435"
SOCKET_NAME = f"geminios-overlay-{os.getuid()}" if hasattr(os, "getuid") else "geminios-overlay-sock"
STORAGE_DIR = Path.home() / ".local/share/geminios"
CHATS_FILE = STORAGE_DIR / "chats.json"

M3_STYLESHEET = """
QWidget#RootWindow {
    background-color: #10131A;
    border: 1px solid #43474E;
    border-radius: 24px;
}

/* Sidebar */
QFrame#Sidebar {
    background-color: #14171F;
    border-right: 1px solid #282C36;
    border-top-left-radius: 24px;
    border-bottom-left-radius: 24px;
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
    border-radius: 16px;
    padding: 8px 16px;
    font-size: 13px;
    font-weight: 700;
}

QPushButton#NewChatBtn:hover {
    background-color: #C2E7FF;
}

QListWidget#HistoryList {
    background: transparent;
    border: none;
    color: #C4C6D0;
    font-size: 12px;
}

QListWidget#HistoryList::item {
    border-radius: 12px;
    padding: 8px 10px;
    margin: 2px 0px;
}

QListWidget#HistoryList::item:hover {
    background-color: #20242E;
    color: #E2E2E9;
}

QListWidget#HistoryList::item:selected {
    background-color: #2A3245;
    color: #A8C7FA;
    font-weight: 600;
}

QPushButton#SidebarChip {
    background-color: #1C2029;
    color: #C4C6D0;
    border: 1px solid #333842;
    border-radius: 12px;
    padding: 5px 10px;
    font-size: 11px;
    font-weight: 500;
}

QPushButton#SidebarChip:hover {
    background-color: #282E3B;
    color: #A8C7FA;
    border-color: #A8C7FA;
}

/* Main Chat Area */
QFrame#ChatArea {
    background-color: #10131A;
    border-top-right-radius: 24px;
    border-bottom-right-radius: 24px;
}

QLabel#ChatHeaderTitle {
    color: #E2E2E9;
    font-size: 15px;
    font-weight: 600;
}

QLabel#BackendBadge {
    color: #A8C7FA;
    background-color: #1A2130;
    border: 1px solid #384358;
    border-radius: 10px;
    padding: 3px 10px;
    font-size: 11px;
    font-weight: 500;
}

/* Mode Switcher Chips */
QPushButton#ModeChip {
    background-color: #1C2029;
    color: #C4C6D0;
    border: 1px solid #333842;
    border-radius: 14px;
    padding: 5px 14px;
    font-size: 12px;
    font-weight: 500;
}

QPushButton#ModeChip:hover {
    background-color: #252B37;
    color: #E2E2E9;
}

QPushButton#ModeChip:checked {
    background-color: #A8C7FA;
    color: #062E6F;
    border: none;
    font-weight: 700;
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
    background-color: #1A1D25;
    border: 1px solid #383D48;
    border-radius: 22px;
    padding: 4px;
}

QTextEdit#InputEdit {
    background: transparent;
    color: #E2E2E9;
    border: none;
    font-size: 13px;
    padding: 6px 12px;
}

QPushButton#SendBtn {
    background-color: #A8C7FA;
    color: #062E6F;
    border: none;
    border-radius: 18px;
    width: 36px;
    height: 36px;
    font-size: 15px;
    font-weight: 700;
}

QPushButton#SendBtn:hover {
    background-color: #C2E7FF;
}

QPushButton#SendBtn:disabled {
    background-color: #2A2F3A;
    color: #6A707E;
}

/* Action icons */
QPushButton#TrashBtn {
    background: transparent;
    color: #8E9099;
    border: none;
    font-size: 12px;
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
    """Material 3 Chat Message Bubble (User in Blue, Gemini in Surface Container)."""

    def __init__(self, role: str, text: str, timestamp: str = "", backend: str = ""):
        super().__init__()
        self.setFrameShape(QFrame.Shape.NoFrame)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 4)

        bubble = QFrame()
        bubble_layout = QVBoxLayout(bubble)
        bubble_layout.setContentsMargins(14, 10, 14, 10)
        bubble_layout.setSpacing(4)

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
            content.setStyleSheet("color: #FFFFFF; font-size: 13px;")
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
                    background-color: #1A1E26;
                    border: 1px solid #313745;
                    border-radius: 18px;
                    border-top-left-radius: 4px;
                }
            """)
            header_row = QHBoxLayout()
            badge = QLabel(f"✦ Gemini ({backend or 'AI'}) · {timestamp}")
            badge.setStyleSheet("color: #A8C7FA; font-size: 11px; font-weight: 600;")
            header_row.addWidget(badge)
            header_row.addStretch()

            copy_btn = QPushButton("Copy")
            copy_btn.setStyleSheet("""
                QPushButton {
                    background-color: #252A36;
                    color: #C4C6D0;
                    border: 1px solid #383F50;
                    border-radius: 8px;
                    padding: 2px 8px;
                    font-size: 10px;
                }
                QPushButton:hover {
                    background-color: #323A4A;
                    color: #A8C7FA;
                }
            """)
            copy_btn.clicked.connect(lambda: QApplication.clipboard().setText(text))
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
            content.setFixedHeight(max(30, min(doc_h + 10, 480)))
            bubble_layout.addWidget(content)

            row = QHBoxLayout()
            row.addWidget(bubble)
            row.addStretch()
            layout.addLayout(row)

    def _format_markdown_html(self, raw: str) -> str:
        import html
        escaped = html.escape(raw)
        lines = []
        in_code = False
        code_buf = []

        for line in escaped.splitlines():
            if line.startswith("```"):
                if in_code:
                    code_html = "\n".join(code_buf)
                    lines.append(f"<pre style='background:#12151D; color:#A8C7FA; padding:8px; border-radius:8px; font-family:JetBrains Mono, monospace;'>{code_html}</pre>")
                    code_buf = []
                    in_code = False
                else:
                    in_code = True
                continue
            if in_code:
                code_buf.append(line)
            else:
                if line.startswith("# "):
                    lines.append(f"<h2 style='color:#A8C7FA; margin:4px 0;'>{line[2:]}</h2>")
                elif line.startswith("## "):
                    lines.append(f"<h3 style='color:#E2E2E9; margin:3px 0;'>{line[3:]}</h3>")
                elif line.startswith("- "):
                    lines.append(f"<li style='margin-left:12px;'>{line[2:]}</li>")
                else:
                    lines.append(f"<p style='margin:3px 0;'>{line}</p>")

        if in_code and code_buf:
            code_html = "\n".join(code_buf)
            lines.append(f"<pre style='background:#12151D; color:#A8C7FA; padding:8px; border-radius:8px; font-family:JetBrains Mono, monospace;'>{code_html}</pre>")

        return "".join(lines)


class GeminiSpotlightWindow(QWidget):
    """Full-featured Material Design 3 Spotlight Chat with Persistent History."""

    def __init__(self, initial_prompt: str = ""):
        super().__init__()
        self.setObjectName("RootWindow")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.resize(960, 620)
        self.setStyleSheet(M3_STYLESHEET)

        self.sessions: List[Dict] = []
        self.current_session_id: Optional[str] = None
        self.active_mode = "chat"
        self.worker: Optional[GeminiWorker] = None

        self._init_ui()
        self._load_history()
        self.refresh_status()

        # Keyboard shortcuts
        QShortcut(QKeySequence("Escape"), self, self.hide)
        QShortcut(QKeySequence("Ctrl+N"), self, self.on_new_chat)
        QShortcut(QKeySequence("Ctrl+Q"), self, self.close)

        if initial_prompt:
            self.input_edit.setPlainText(initial_prompt)
            self.on_send()

    def _init_ui(self):
        root_layout = QHBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setStyleSheet("QSplitter::handle { background: transparent; }")

        # 1. Left Sidebar
        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(270)
        side_layout = QVBoxLayout(sidebar)
        side_layout.setContentsMargins(16, 20, 16, 16)
        side_layout.setSpacing(12)

        title_box = QHBoxLayout()
        logo_lbl = QLabel("✦")
        logo_lbl.setStyleSheet("color:#A8C7FA; font-size:20px; font-weight:bold;")
        brand_col = QVBoxLayout()
        brand_col.setSpacing(1)
        b_name = QLabel("Gemini Spotlight")
        b_name.setObjectName("SidebarTitle")
        b_tag = QLabel("Google Material 3 · GeminiOS")
        b_tag.setObjectName("SidebarSub")
        brand_col.addWidget(b_name)
        brand_col.addWidget(b_tag)
        title_box.addWidget(logo_lbl)
        title_box.addLayout(brand_col)
        title_box.addStretch()
        side_layout.addLayout(title_box)

        new_btn = QPushButton("+ New Chat")
        new_btn.setObjectName("NewChatBtn")
        new_btn.clicked.connect(self.on_new_chat)
        side_layout.addWidget(new_btn)

        hist_lbl = QLabel("Recent Conversations")
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
            ("✦ Activate GeminiOS", self.on_activate_system),
            ("✦ Google Gemini API Key", self.on_set_api_key),
            ("✦ System Doctor", self.on_run_doctor),
            ("✦ Analyze Clipboard", self.on_analyze_clipboard),
            ("✦ Local Gemma Engine", self.on_enable_gemma),
        ]:
            b = QPushButton(label)
            b.setObjectName("SidebarChip")
            b.clicked.connect(cb)
            quick_grid.addWidget(b)
        side_layout.addLayout(quick_grid)

        del_all_btn = QPushButton("🗑 Clear All History")
        del_all_btn.setObjectName("TrashBtn")
        del_all_btn.clicked.connect(self.on_clear_all_history)
        side_layout.addWidget(del_all_btn)

        splitter.addWidget(sidebar)

        # 2. Main Chat Area
        chat_area = QFrame()
        chat_area.setObjectName("ChatArea")
        chat_layout = QVBoxLayout(chat_area)
        chat_layout.setContentsMargins(20, 20, 20, 16)
        chat_layout.setSpacing(10)

        # Top Bar
        top_bar = QHBoxLayout()
        self.mode_chat = QPushButton("💬 Chat")
        self.mode_chat.setObjectName("ModeChip")
        self.mode_chat.setCheckable(True)
        self.mode_chat.setChecked(True)
        self.mode_chat.clicked.connect(lambda: self._set_mode("chat"))

        self.mode_agent = QPushButton("⚡ Agent Mode")
        self.mode_agent.setObjectName("ModeChip")
        self.mode_agent.setCheckable(True)
        self.mode_agent.clicked.connect(lambda: self._set_mode("agent"))

        self.mode_search = QPushButton("🔍 Deep Search")
        self.mode_search.setObjectName("ModeChip")
        self.mode_search.setCheckable(True)
        self.mode_search.clicked.connect(lambda: self._set_mode("search"))

        top_bar.addWidget(self.mode_chat)
        top_bar.addWidget(self.mode_agent)
        top_bar.addWidget(self.mode_search)
        top_bar.addStretch()

        self.backend_badge = QLabel("Checking backend...")
        self.backend_badge.setObjectName("BackendBadge")
        top_bar.addWidget(self.backend_badge)

        close_btn = QPushButton("✕")
        close_btn.setStyleSheet("background:transparent; color:#8E9099; border:none; font-size:14px; padding:4px;")
        close_btn.clicked.connect(self.hide)
        top_bar.addWidget(close_btn)

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
        input_box.setContentsMargins(6, 4, 6, 4)
        input_box.setSpacing(8)

        self.input_edit = QTextEdit()
        self.input_edit.setObjectName("InputEdit")
        self.input_edit.setPlaceholderText("Ask Gemini anything or describe a system task... (Enter to send, Shift+Enter for newline)")
        self.input_edit.setFixedHeight(48)
        self.input_edit.installEventFilter(self)
        input_box.addWidget(self.input_edit, 1)

        self.send_btn = QPushButton("➤")
        self.send_btn.setObjectName("SendBtn")
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
        if mode == "agent":
            self.input_edit.setPlaceholderText("Describe a system goal (e.g. 'install git and configure nginx')...")
        elif mode == "search":
            self.input_edit.setPlaceholderText("Search documentation, files, or packages...")
        else:
            self.input_edit.setPlaceholderText("Ask Gemini anything... (Enter to send, Shift+Enter for newline)")

    def _load_history(self):
        STORAGE_DIR.mkdir(parents=True, exist_ok=True)
        if CHATS_FILE.exists():
            try:
                data = json.loads(CHATS_FILE.read_text(encoding="utf-8"))
                self.sessions = data.get("chats", [])
            except Exception:
                self.sessions = []
        if not self.sessions:
            self._create_session("New Conversation")
        self._refresh_history_list()

    def _save_history(self):
        STORAGE_DIR.mkdir(parents=True, exist_ok=True)
        payload = {"chats": self.sessions}
        CHATS_FILE.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    def _refresh_history_list(self):
        self.history_list.blockSignals(True)
        self.history_list.clear()
        for s in self.sessions:
            item = QListWidgetItem(f"💬 {s.get('title', 'Chat')}")
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

    def _create_session(self, title: str = "New Conversation") -> Dict:
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
        self._create_session("New Conversation")
        self._refresh_history_list()
        self.input_edit.clear()
        self.input_edit.setFocus()

    def _on_session_selected(self, row: int):
        if 0 <= row < len(self.sessions):
            session = self.sessions[row]
            self.current_session_id = session.get("id")
            self._load_session_messages(session)

    def _load_session_messages(self, session: Dict):
        # Clear existing message widgets (except top stretch)
        while self.msg_layout.count() > 1:
            child = self.msg_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        msgs = session.get("messages", [])
        if not msgs:
            empty = QLabel("✦ Start chatting with Google Gemini or ask a system task.")
            empty.setStyleSheet("color:#6A707E; font-size:13px; font-style:italic; padding:20px;")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.msg_layout.insertWidget(0, empty)
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
            current_sess = self._create_session("New Conversation")

        if current_sess.get("title") in ("New Conversation", ""):
            first_words = " ".join(text.split()[:5])
            current_sess["title"] = first_words[:30]
            self._refresh_history_list()

        current_sess["messages"].append({"role": "user", "content": text, "time": now_str})
        self._save_history()

        bubble = MessageBubble(role="user", text=text, timestamp=now_str)
        self.msg_layout.insertWidget(self.msg_layout.count() - 1, bubble)
        self.input_edit.clear()
        self._scroll_to_bottom()

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
        self.backend_badge.setText("Thinking...")

        self.worker = GeminiWorker(text, self.active_mode)
        self.worker.finished.connect(self._on_ai_response)
        self.worker.start()

    def _on_ai_response(self, data: dict):
        self.send_btn.setEnabled(True)
        self.refresh_status()
        now_str = datetime.datetime.now().strftime("%H:%M")

        if not data.get("ok"):
            err_msg = data.get("response", "Unknown error contacting Gemini AI.")
            ans = f"**Error**: {err_msg}\n\n*Tip: Click '✦ Google Gemini API Key' on the sidebar to configure your key.*"
            backend = "Error"
        elif "plan" in data:
            plan = data["plan"]
            lines = [f"**Agent Plan**: {plan.get('summary', '')}\n"]
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
                    "GeminiOS Agent Confirmation",
                    f"Execute planned command?\n\n{step['cmd']}\n\nReason: {step.get('reason', '')}",
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
                        ans += f"\n\n**Output of `{step['cmd']}`**:\n```\n{res.get('stdout', '')}{res.get('stderr', '')}\n```"
                    except Exception as exc:
                        ans += f"\n\n**Execution failed**: {exc}"
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
                self.backend_badge.setText(f"● Gemini Cloud ({st.get('cloud_model')})")
            elif st.get("fallback_enabled"):
                self.backend_badge.setText(f"● Gemma Local ({st.get('fallback_model')})")
            else:
                self.backend_badge.setText("● Setup Required (API Key)")
        except Exception:
            self.backend_badge.setText("● geminid offline")

    def on_set_api_key(self):
        key, ok = QInputDialog.getText(
            self,
            "Google Gemini API Key",
            "Enter your Google Gemini API key (AIza...):",
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
                QMessageBox.information(self, "API Key Saved", "Gemini API key configured successfully!")
            except Exception as exc:
                QMessageBox.warning(self, "Error", f"Failed to save API key: {exc}")

    def on_run_doctor(self):
        subprocess.Popen(["konsole", "--hold", "-e", "gemini-doctor"])

    def on_analyze_clipboard(self):
        clip = QApplication.clipboard().text().strip()
        if not clip:
            QMessageBox.information(self, "Clipboard", "Clipboard is currently empty.")
            return
        self.input_edit.setPlainText(f"Explain or fix this clipboard content concisely:\n{clip[:4000]}")
        self.on_send()

    def on_enable_gemma(self):
        subprocess.Popen(["konsole", "--hold", "-e", "gemini", "enable-gemma"])

    def on_clear_all_history(self):
        reply = QMessageBox.question(
            self,
            "Clear History",
            "Are you sure you want to delete all chat history?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.sessions = []
            if CHATS_FILE.exists():
                CHATS_FILE.unlink(missing_ok=True)
            self._create_session("New Conversation")
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
        if self.isVisible() and self.isActiveWindow():
            self.hide()
        else:
            self.show()
            self.raise_()
            self.activateWindow()
            self.input_edit.setFocus()


def main() -> int:
    parser = argparse.ArgumentParser(description="GeminiOS Spotlight Overlay")
    parser.add_argument("--prompt", default="", help="Initial prompt to ask immediately")
    parser.add_argument("--toggle", action="store_true", help="Toggle existing window")
    args, qt_args = parser.parse_known_args()

    app = QApplication([sys.argv[0]] + qt_args)

    # Single-instance handling via QLocalSocket
    test_socket = QLocalSocket()
    test_socket.connectToServer(SOCKET_NAME)
    if test_socket.waitForConnected(300):
        # Already running: signal existing instance to toggle or accept prompt
        msg = json.dumps({"action": "toggle", "prompt": args.prompt})
        test_socket.write(msg.encode("utf-8"))
        test_socket.flush()
        test_socket.waitForBytesWritten(500)
        test_socket.disconnectFromServer()
        return 0

    # Start primary instance
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
        screen.top() + int(screen.height() * 0.12),
    )
    win.show()
    win.input_edit.setFocus()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
