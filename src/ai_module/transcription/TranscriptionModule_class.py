import json
import re
from datetime import datetime
import mimetypes
from typing import TYPE_CHECKING, List, Union, Optional

import requests
from PyQt6.QtCore import Qt, pyqtSlot
from PyQt6.QtGui import QResizeEvent, QFont, QMouseEvent, QShowEvent
from PyQt6.QtWidgets import QWidget, QPushButton, QFrame, QScrollArea, QVBoxLayout, QLabel, QMenu, QComboBox, QCheckBox, \
    QFormLayout

from src.global_styles import DEFAULT_SCROLLBAR_STYLE

if TYPE_CHECKING:
    from src.forms import MainForm
    from .AudioLyricsModule_class import AudioLyricsModule


class TranscriptionModule(QWidget):
    """Experimental speech to text panel, requires an external HTTP service."""

    def __init__(self, mf, lyric_module, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.mf: MainForm = mf
        self.lyric_module: AudioLyricsModule = lyric_module
        # TODO: Вынести в настройки
        self.host = 'http://127.0.0.1:13000'
        self.end_point = 'audio/transcription/process'
        self.setMaximumWidth(300)

        self.form_layout = QFormLayout(self)

        self.run_process_button = QPushButton("Run process")
        self.run_process_button.clicked.connect(self.run_process)

        self.model_name_combo = QComboBox()
        self.model_name_combo.addItems([
            "tiny",
            "base.en",
            "base",
            "small.en",
            "small",
            "medium.en",
            "medium",
            "large-v1",
            "large-v2",
            "large-v3",
            "large",
            "large-v3-turbo",
            "turbo"
        ])
        self.model_name_combo.setCurrentText("large-v3-turbo")

        self.form_layout.addRow("Model name", self.model_name_combo)
        self.form_layout.addRow("", self.run_process_button)

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)

    @pyqtSlot()
    def run_process(self) -> None:
        url: str = f"{self.host}/{self.end_point}"
        opened_file = self.mf.audio_player.playable_file_file
        if opened_file is None:
            return

        mime_type, encoding = mimetypes.guess_type(opened_file)
        with open(opened_file, "rb") as f:
            r = requests.post(
                url,
                params={"model_name": self.model_name_combo.currentText()},
                files={"file": (opened_file, f, mime_type)},
                timeout=300,
            )
        # print_d(r.status_code, r.json())
        if r.status_code == 200:
            data = r.json()
            data['lyric_source'] = 'ai'
            self.lyric_module.set_transcription_data(data)
            track_id = self.mf.audio_player.playable_track_id
            if track_id is not None:
                self.mf.file_meta_controller.save_track_transcription(track_id, data)


