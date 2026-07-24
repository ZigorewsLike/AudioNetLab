from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
                             QScrollArea, QSizePolicy, QFrame)

from src.global_styles import DEFAULT_SCROLLBAR_STYLE, AppColorSchemes

if TYPE_CHECKING:
    from src.forms import MainForm


@dataclass(frozen=True)
class ChatMessage:
    text: str
    outgoing: bool
    ts: datetime


class MessageBubble(QWidget):
    def __init__(self, msg: ChatMessage, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        bubble_text_label = QLabel(msg.text)
        bubble_text_label.setWordWrap(True)
        bubble_text_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
            | Qt.TextInteractionFlag.TextSelectableByKeyboard
        )
        bubble_text_label.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Preferred)
        bubble_text_label.setMaximumWidth(520)

        bubble_time_label = QLabel(datetime.strftime(msg.ts, "%H:%M"))

        v_layout = QHBoxLayout(self)
        "#689CD2"
        "d3d5d3"
        if msg.outgoing:
            bubble_text_label.setStyleSheet(f"""
            QLabel {{ 
                background: #689CD2; 
                color: #111; 
                padding: 8px 10px; 
                border-radius: 12px;
                border: 1px solid #d3d5d3; 
            }}
            """)
            v_layout.addWidget(bubble_text_label)
            v_layout.addWidget(bubble_time_label, alignment=Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignRight)
        else:
            bubble_text_label.setStyleSheet(f"""
            QLabel {{
                background: #FFFFFF; 
                color: #111; 
                padding: 8px 10px; 
                border-radius: 12px; 
                border: 1px solid #d3d5d3;
            }}
            """)
            v_layout.addWidget(bubble_time_label, alignment=Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignLeft)
            v_layout.addWidget(bubble_text_label)


class ChatWidget(QWidget):
    """
    - history: QScrollArea + вертикальный layout с пузырями
    - input: QLineEdit + QPushButton
    """
    def __init__(self, mf, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.mf: MainForm = mf

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(10)

        self._history_container = QWidget()
        self._history_container.setStyleSheet(f"""
        QWidget {{
            background: {AppColorSchemes.FILE_LIST_ITEM_BODY};
        }}
        """)
        self._history_layout = QVBoxLayout(self._history_container)
        self._history_layout.setContentsMargins(8, 8, 8, 8)
        self._history_layout.setSpacing(6)
        self._history_layout.addStretch(1)

        self.history = QScrollArea()
        self.history.setWidgetResizable(True)
        self.history.setWidget(self._history_container)
        self.history.setStyleSheet(DEFAULT_SCROLLBAR_STYLE)
        self.history.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        bottom = QHBoxLayout()
        self.input = QLineEdit()
        self.input.setPlaceholderText("Напишите сообщение…")
        self.input.returnPressed.connect(self.send_clicked)

        self.send_btn = QPushButton("Send")
        self.send_btn.clicked.connect(self.send_clicked)

        bottom.addWidget(self.input, 1)
        bottom.addWidget(self.send_btn, 0)

        root.addWidget(self.history, 1)
        root.addLayout(bottom, 0)

    def add_message(self, text: str, outgoing: bool) -> None:
        text = (text or "").strip()
        if not text:
            return

        msg = ChatMessage(text=text, outgoing=outgoing, ts=datetime.now())
        bubble = MessageBubble(msg)

        idx_before_stretch = max(0, self._history_layout.count() - 1)
        if idx_before_stretch == 0:
            self._history_layout.insertWidget(
                idx_before_stretch, QLabel(datetime.strftime(datetime.now(), "%d.%m.%Y")),
                alignment=Qt.AlignmentFlag.AlignCenter)
            idx_before_stretch += 1
        self._history_layout.insertWidget(
            idx_before_stretch, bubble,
            alignment=Qt.AlignmentFlag.AlignRight if outgoing else Qt.AlignmentFlag.AlignLeft)

        bar = self.history.verticalScrollBar()
        bar.setValue(bar.maximum())

    def send_clicked(self) -> None:
        text = self.input.text()
        self.input.clear()
        self.add_message(text, outgoing=True)

        self.add_message(f"Echo: {text}", outgoing=False)


if __name__ == "__main__":
    import sys

    app = QApplication(sys.argv)

    w = ChatWidget()
    w.setWindowTitle("Chat Widget")
    w.resize(720, 520)

    # Демо-история
    w.add_message("Привет! Это входящее сообщение.", outgoing=False)
    w.add_message("А это отправленное.", outgoing=True)

    w.show()
    raise SystemExit(app.exec())
