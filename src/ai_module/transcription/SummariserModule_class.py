import json
import re
from datetime import datetime
import mimetypes
from bisect import bisect_right
from typing import TYPE_CHECKING, List, Union, Optional

import requests
from PyQt6.QtCore import Qt, pyqtSlot, QEvent
from PyQt6.QtGui import QResizeEvent, QFont, QMouseEvent, QShowEvent
from PyQt6.QtWidgets import QWidget, QPushButton, QFrame, QScrollArea, QVBoxLayout, QLabel, QMenu, QComboBox, QCheckBox, \
    QFormLayout

from src.core.log_system import print_d
from src.global_styles import DEFAULT_SCROLLBAR_STYLE

if TYPE_CHECKING:
    from src.forms import MainForm
    from .AudioLyricsModule_class import AudioLyricsModule


class SummariserModule(QWidget):
    """Experimental lyrics summarization panel, requires an external HTTP service."""

    def __init__(self, mf, lyric_module, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.mf: MainForm = mf
        self.lyric_module: AudioLyricsModule = lyric_module
        # TODO: move to the settings
        self.host = 'http://127.0.0.1:13000'
        self.end_point = 'text/summary/process'

        # The item texts are sent to the service as is, they must not be translated
        self.language_combobox = QComboBox()
        self.language_combobox.addItem("Русский")
        self.language_combobox.addItem("English")

        self.summarize_button = QPushButton("", self)
        self.summarize_button.clicked.connect(self.summarize_lyrics)

        self.summary_text: str = ""
        self.label = QLabel("", self)
        self.label.setWordWrap(True)
        self.label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
            | Qt.TextInteractionFlag.TextSelectableByKeyboard
        )

        self.language_label = QLabel("")
        self.form_layout = QFormLayout(self)
        self.form_layout.addRow(self.language_label, self.language_combobox)
        self.form_layout.addWidget(self.summarize_button)
        self.form_layout.addRow(self.label)

        self.retranslate_ui()

    def changeEvent(self, event: QEvent) -> None:
        """Reapply the texts when the application language changes.

        :param event: Qt event.
        :returns: None.
        """
        if event.type() == QEvent.Type.LanguageChange:
            self.retranslate_ui()
        super().changeEvent(event)

    def retranslate_ui(self) -> None:
        """Apply the current translation to the texts of this panel.

        :returns: None.
        """
        self.summarize_button.setText(self.tr("Summarize"))
        self.language_label.setText(self.tr("Summary language"))
        self.set_text(self.summary_text)  # The header of the summary is translated too

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        # self.label.move(10, self.language_combobox.height() + 20)
        # self.label.setFixedWidth(self.width() - 20)

    def set_text(self, text: str) -> None:
        """Show the summary under a translated header.

        :param text: Summary text, may be empty.
        :returns: None.
        """
        self.summary_text = text
        self.label.setText(f"<span style='font-weight: bold;'>{self.tr('What the song is about:')}</span>"
                           f"<br><br>{text}")
        self.label.adjustSize()

    @pyqtSlot()
    def summarize_lyrics(self):
        texts = [x.get("text") for x in self.lyric_module.transcription_data.get('segments', [])]
        self.run_process('\n'.join(texts))

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


