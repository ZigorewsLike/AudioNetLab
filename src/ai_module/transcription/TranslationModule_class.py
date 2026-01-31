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
    from .AudioLyricsModule_class import AudioLyricsModule


class TranslationModule(QWidget):
    def __init__(self, mf, lyric_module, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.mf: MainForm = mf
        self.lyric_module: AudioLyricsModule = lyric_module
        # TODO: Вынести в настройки
        self.host = 'http://127.0.0.1:13000'
        self.end_point = 'text/translate/process'

        self.language_combobox = QComboBox()
        self.language_combobox.addItem("Русский")
        self.language_combobox.addItem("English")

        self.translate_button = QPushButton("Translate", self)
        self.translate_button.clicked.connect(self.translate_lyrics)

        self.form_layout = QFormLayout(self)
        self.form_layout.addRow("Язык перевода: ", self.language_combobox)
        self.form_layout.addWidget(self.translate_button)

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)

    @pyqtSlot()
    def translate_lyrics(self):
        texts = self.lyric_module.get_segments()
        self.run_process('\n'.join([x.get('text') for x in texts]))

    def run_process(self, text: str) -> None:
        url: str = f"{self.host}/{self.end_point}"
        r = requests.post(
            url,
            data=json.dumps({
                "text": text,
                "meta": {'track_id': self.mf.audio_player.playable_track_id},
                "lang": self.language_combobox.currentText()
            }),
            timeout=300,
        )
        if r.status_code == 200:
            data = r.json()
            tr_text = data['result']
            segments = self.lyric_module.get_segments()
            for segment_index, text_line in enumerate(tr_text):
                segments[segment_index]['text'] = text_line
            self.lyric_module.update_transcription_list()


