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
from src.core.qt_widgets import BaseTabWidget

if TYPE_CHECKING:
    from src.forms import MainForm


class EQWidget(QWidget):
    slidersValueChange = QtCore.pyqtSignal(list)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.slider_count: int = 20
        self.slider_padding: int = 26
        self.slider_container: List[QSlider] = []
        self.label_container: List[QLabel] = []
        self.slider_gains: List[int] = [0 for _ in range(self.slider_count)]

        frequencies = [22_000 // 2 ** x for x in range(self.slider_count // 2)]
        frequencies += [16_000 // 2 ** x for x in range(self.slider_count // 2)]
        frequencies.sort()
        self.bands = list(zip(frequencies[:-1], frequencies[1:]))
        for slider_index in range(self.slider_count):
            # Sliders
            vert_slider = QSlider(self)
            vert_slider.setObjectName("verticalSlider")
            vert_slider.setGeometry(QRect(self.slider_padding + self.slider_padding * slider_index, 20, 22, 130))
            vert_slider.setValue(100)
            vert_slider.setRange(0, 200)
            vert_slider.setOrientation(Qt.Orientation.Vertical)
            vert_slider.valueChanged.connect(self.on_slider_value_changed)
            self.slider_container.append(vert_slider)
            # Labels
            freq = frequencies[slider_index]
            freq_text = f"{freq}"
            if freq > 1000:
                freq = round(freq / 1000, 1)
                freq_text = f"{freq}k"
            label = QLabel(freq_text, self)
            label.setGeometry(int(self.slider_padding * slider_index + self.slider_padding / 2),
                              5 if slider_index % 2 == 0 else vert_slider.height() + vert_slider.y() + 5,
                              self.slider_padding + vert_slider.width(),
                              10)
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.label_container.append(label)

    @pyqtSlot(int)
    def on_slider_value_changed(self, value: int) -> None:
        self.slider_gains = [slider.value() / 100 for slider in self.slider_container]
        self.slidersValueChange.emit(self.slider_gains)


class SettingsEQWidget(QWidget):
    def __init__(self, mf, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.eq: EQWidget = EQWidget(self)

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self.eq.resize(self.size())





