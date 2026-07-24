from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt, pyqtSlot, QEvent
from PyQt6.QtGui import QResizeEvent
from PyQt6.QtWidgets import QWidget, QFrame, QScrollArea, QFormLayout, QLabel, QCheckBox, QPushButton

from src.global_styles import AppColorSchemes, DEFAULT_SCROLLBAR_STYLE
from src.core.qt_widgets import CollapsibleSection
from .TranscriptionModule_class import TranscriptionModule
from .TranslationModule_class import TranslationModule
from ...core.log_system import print_d

if TYPE_CHECKING:
    from src.forms import MainForm
    from .AudioLyricsModule_class import AudioLyricsModule


class LyricsPropertyCommon(QWidget):
    """"Common" page of the lyrics panel: display options, tag extraction, transcription and translation."""

    def __init__(self, mf, lyric_module, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.mf: MainForm = mf
        self.lyric_module: AudioLyricsModule = lyric_module

        self.show_timestamp_checkbox = QCheckBox("")
        self.show_timestamp_checkbox.stateChanged.connect(lambda:  self.set_timestamp_visible())

        self.get_from_file_button = QPushButton("")
        self.get_from_file_button.clicked.connect(self.lyric_module.set_lyrics_from_file)
        self.get_from_file_button.setMaximumWidth(100)

        self.common_frame = QFrame()
        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidget(self.common_frame)
        self.scroll_area.setStyleSheet(DEFAULT_SCROLLBAR_STYLE)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.form_layout = QFormLayout(self)

        self.transcription = TranscriptionModule(mf, self.lyric_module, self.common_frame)
        self.translation = TranslationModule(mf, self.lyric_module, self.common_frame)

        self.common_header = QLabel("")
        self.extract_label = QLabel("")
        self.transcription_header = QLabel("")
        self.translation_header = QLabel("")

        self.form_layout.addRow(self.common_header)
        self.form_layout.addRow(self.show_timestamp_checkbox)
        self.form_layout.addRow(self.extract_label, self.get_from_file_button)
        self.form_layout.addRow(self.transcription_header)
        self.form_layout.addRow(self.transcription)
        self.form_layout.addRow(self.translation_header)
        self.form_layout.addRow(self.translation)

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
        """Apply the current translation to the texts of this page.

        :returns: None.
        """
        self.show_timestamp_checkbox.setText(self.tr("Show timestamp"))
        self.get_from_file_button.setText(self.tr("Extract"))
        self.common_header.setText(f"<b>{self.tr('Common settings')}</b>")
        self.extract_label.setText(self.tr("Extract lyrics from file tags"))
        self.transcription_header.setText(f"<b>{self.tr('Auto audio transcription')}</b>")
        self.translation_header.setText(f"<b>{self.tr('Translate lyrics')}</b>")

    def set_timestamp_visible(self):
        self.lyric_module.show_timestamp = self.show_timestamp_checkbox.isChecked()
        self.lyric_module.update_transcription_list()

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self.scroll_area.resize(self.width(), self.height())
        self.common_frame.resize(self.width(), 300)


