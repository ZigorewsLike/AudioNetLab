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
    QFormLayout, QTabWidget

from src.core.log_system import print_d
from .SummariserModule_class import SummariserModule
from .LyricsPropertyCommon_class import LyricsPropertyCommon
from ...global_styles import AppColorSchemes

if TYPE_CHECKING:
    from src.forms import MainForm


class TranscriptionPropertyModule(QWidget):
    """Right side panel of the lyrics tab with the Common and Summarization pages."""

    def __init__(self, mf, lyric_module, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.mf: MainForm = mf

        self.common_lyrics_property = LyricsPropertyCommon(self.mf, lyric_module)
        self.summariser: SummariserModule = SummariserModule(self.mf, lyric_module)

        self.tab_widget = QTabWidget(self)
        self.tab_widget.setStyleSheet(f"""
            QWidget{{
                background-color: {AppColorSchemes.FILE_LIST_BACKGROUND};
                color: black;
            }}
            QTabWidget{{
                background-color: {AppColorSchemes.FILE_LIST_BACKGROUND};
                padding: 0px;
            }}
            QTabBar::tab {{
                color: black;
                background-color: #e0e0e0;
                border: 1px solid #939393;
                border-bottom-color: {AppColorSchemes.FILE_LIST_BACKGROUND};
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                min-width: 50px;
                min-height: 20px;
                padding: 0px 2px;
                margin-left: 1px;
            }}

            QTabBar::tab:selected {{
                color: black;
                background-color: {AppColorSchemes.FILE_LIST_BACKGROUND};
                border-bottom-color: {AppColorSchemes.FILE_LIST_BACKGROUND};
                font-weight: bold;
            }}

            QTabBar::tab:disabled {{
                color: gray;
            }}
        """)
        self.tab_widget.addTab(self.common_lyrics_property, "Common")
        self.tab_widget.addTab(self.summariser, "Summarization")

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self.tab_widget.resize(self.width(), self.height())


