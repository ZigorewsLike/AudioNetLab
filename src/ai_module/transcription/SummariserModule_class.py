import json
import re
from datetime import datetime
import mimetypes
from bisect import bisect_right
from typing import TYPE_CHECKING, List, Union, Optional

import requests
from PyQt6.QtCore import Qt, pyqtSlot
from PyQt6.QtGui import QResizeEvent, QFont, QMouseEvent, QShowEvent
from PyQt6.QtWidgets import QWidget, QPushButton, QFrame, QScrollArea, QVBoxLayout, QLabel, QMenu, QComboBox, QCheckBox, \
    QFormLayout

from src.core.log_system import print_d
from src.global_styles import DEFAULT_SCROLLBAR_STYLE

if TYPE_CHECKING:
    from src.forms import MainForm


class SummariserModule(QWidget):
    def __init__(self, mf, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.mf: MainForm = mf
        # TODO: Вынести в настройки
        self.host = 'http://127.0.0.1:13000'
        self.end_point = 'text/summary/process'

        self.language_combobox = QComboBox()
        self.language_combobox.addItem("Russian")
        self.language_combobox.addItem("English")

        self.form_layout = QFormLayout(self)
        self.form_layout.addRow("Язык пересказа: ", self.language_combobox)

        self.label = QLabel("<span style='font-weight: bold;'>Общий смысл песни:</span><br><br>", self)
        self.label.setWordWrap(True)

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self.label.move(10, self.language_combobox.height() + 20)
        self.label.setFixedWidth(self.width() - 20)

    def set_text(self, text: str) -> None:
        self.label.setText(f"<span style='font-weight: bold;'>Общий смысл песни:</span><br><br>{text}")
        self.label.adjustSize()

    def run_process(self, text: str) -> None:
        url: str = f"{self.host}/{self.end_point}"
        r = requests.post(
            url,
            # params={"model_name": self.model_name_combo.currentText()},
            data=json.dumps({
                "text": text,
                "meta": {'track_id': self.mf.audio_player.playable_track_id},
                "lang": self.language_combobox.currentText()
            }),
            timeout=300,
        )
        if r.status_code == 200:
            data = r.json()
            print_d(data)
            self.set_text('.<br>'.join(data['result']))

    def clear(self) -> None:
        self.set_text("")


