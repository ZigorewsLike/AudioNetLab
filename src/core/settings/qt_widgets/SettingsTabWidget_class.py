import math
import os
import time
from typing import Dict, Union, TYPE_CHECKING, Optional, List


from PyQt6 import QtCore
from PyQt6.QtCore import pyqtSlot, QEvent, QPointF, Qt, QPoint, QThread, QSize
from PyQt6.QtGui import (QPaintEvent, QPainter, QBrush, QColor, QMouseEvent, QFontMetrics, QLinearGradient, QPen, QFont,
                         QResizeEvent)
from PyQt6.QtWidgets import QWidget, QToolTip, QLabel, QPushButton, QFileDialog

from src.global_constants import ONNX_INFERENCE, PROFILE, ONNX_SESS_PROVIDER
from src.global_styles import AppColorSchemes
from src.core.log_system import print_d, print_e, print_i
from src.core.qt_widgets import BaseTabWidget

from .SettingsEQWidget_class import SettingsEQWidget
from .SettingsAudioWidget_class import SettingsAudioWidget

if TYPE_CHECKING:
    from src.forms import MainForm


class SettingsTabWidget(QWidget):
    def __init__(self, mf, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.mf: MainForm = mf
        self.left_tab_padding = 50

        self.setStyleSheet("""
        QWidget{
            background-color: """ + AppColorSchemes.SETTINGS_BACKGROUND + """;
            color: """ + AppColorSchemes.SETTINGS_FONT_COLOR + """;
        }
        """)

        self.audio_settings = SettingsAudioWidget(self.mf)
        self.eq_settings = SettingsEQWidget()

        self.tab_widget = BaseTabWidget(self)
        self.tab_widget.move(self.left_tab_padding, 0)
        self.tab_widget.add_tab(self.audio_settings, "audio")
        self.tab_widget.add_tab(self.eq_settings, "EQ")

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self.tab_widget.resize(self.size() - QSize(self.left_tab_padding, 0))

    def paintEvent(self, event: QPaintEvent) -> None:
        super().paintEvent(event)
        painter = QPainter(self)
        painter.fillRect(0, 0, self.width(), self.height(), QColor(AppColorSchemes.SETTINGS_BACKGROUND))

