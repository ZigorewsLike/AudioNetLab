import math
import os
import time
from typing import Dict, Union, TYPE_CHECKING, Optional, List


from PyQt6 import QtCore
from PyQt6.QtCore import pyqtSlot, QEvent, QPointF, Qt, QPoint, QThread, QSize, QRect
from PyQt6.QtGui import (QPaintEvent, QPainter, QBrush, QColor, QMouseEvent, QFontMetrics, QLinearGradient, QPen, QFont,
                         QResizeEvent)
from PyQt6.QtWidgets import QWidget, QToolTip, QLabel, QPushButton, QFileDialog, QSlider

from src.global_constants import ONNX_INFERENCE, PROFILE, ONNX_SESS_PROVIDER
from src.core.log_system import print_d, print_e, print_i
from src.core.qt_widgets import BaseTabWidget, EQWidget
from src.enums import EQType

if TYPE_CHECKING:
    from src.forms import MainForm


class SettingsEQWidget(QWidget):
    def __init__(self, mf, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.eq: EQWidget = EQWidget(EQType.PRESET, self)

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self.eq.resize(self.size())





