from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt, pyqtSlot
from PyQt6.QtGui import QResizeEvent
from PyQt6.QtWidgets import QWidget, QTabWidget, QFrame, QScrollArea, QFormLayout, QLabel, QCheckBox, QPushButton

from src.global_styles import AppColorSchemes, DEFAULT_SCROLLBAR_STYLE
from src.core.qt_widgets import CollapsibleSection
from .TranscriptionModule_class import TranscriptionModule

if TYPE_CHECKING:
    from src.forms import MainForm
    from .AudioLyricsModule_class import AudioLyricsModule


class LyricsPropertyCommon(QWidget):
    def __init__(self, mf, lyric_module, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.mf: MainForm = mf
        self.lyric_module: AudioLyricsModule = lyric_module

        self.show_timestamp_checkbox = QCheckBox("Show timestamp")
        self.show_timestamp_checkbox.stateChanged.connect(lambda:  self.set_timestamp_visible())

        self.get_from_file_button = QPushButton("Extract lyrics")
        self.get_from_file_button.clicked.connect(self.lyric_module.set_lyrics_from_file)
        self.get_from_file_button.setMaximumWidth(100)

        self.common_frame = QFrame()
        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidget(self.common_frame)
        self.scroll_area.setStyleSheet(DEFAULT_SCROLLBAR_STYLE)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.form_layout = QFormLayout(self)

        self.transcription = TranscriptionModule(mf, self.lyric_module, self.common_frame)
        self.form_layout.addRow(QLabel("<b>Common settings</b>"))
        self.form_layout.addRow(self.show_timestamp_checkbox)
        self.form_layout.addRow("Extract lyrics from file tags", self.get_from_file_button)
        self.form_layout.addRow(QLabel("<b>Auto audio transcription</b>"))
        self.form_layout.addRow(self.transcription)
        # self.transcription_section: CollapsibleSection = CollapsibleSection("Auto Audio Transcription", 20, self.common_frame)
        # self.transcription_section.set_content(self.transcription)

    def set_timestamp_visible(self):
        self.lyric_module.show_timestamp = self.show_timestamp_checkbox.isChecked()
        self.lyric_module.update_transcription_list()

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self.scroll_area.resize(self.width(), self.height())
        self.common_frame.resize(self.width(), 300)


