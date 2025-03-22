from typing import Dict, Union, TYPE_CHECKING, Optional, List

import numpy as np
from PyQt6 import QtCore
from PyQt6.QtCore import pyqtSlot, QEvent, QPointF, Qt, QPoint, QThread, QSize, QRect
from PyQt6.QtGui import (QPaintEvent, QPainter, QBrush, QColor, QMouseEvent, QFontMetrics, QLinearGradient, QPen, QFont,
                         QResizeEvent, QIcon)
from PyQt6.QtWidgets import QWidget, QToolTip, QLabel, QPushButton, QFileDialog, QSlider, QFrame

from src.global_constants import EQ_SLIDER_COUNT, RESOURCE_ICON_DIR
from src.core.log_system import print_d, print_e, print_i
from src.enums import EQType
from .ScrollButtonWidget_class import ScrollButtonWidget

if TYPE_CHECKING:
    from src.forms import MainForm


class EQWidget(QWidget):
    autoEQSwitched = QtCore.pyqtSignal(bool)
    activeSwitched = QtCore.pyqtSignal(bool)
    slidersValueChange = QtCore.pyqtSignal(list)

    def __init__(self, eq_type: EQType, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.slider_count: int = EQ_SLIDER_COUNT
        self.slider_padding: int = 26
        self.button_padding: int = 20
        self.slider_container: List[QSlider] = []
        self.label_container: List[QLabel] = []
        self.slider_gains: List[int] = [0 for _ in range(self.slider_count)]
        self.eq_type: EQType = eq_type
        self.accuracy: int = 1000
        self.interpolation_step: int = 10

        self.active_fx: bool = True
        self.auto_eq: bool = False

        self.slider_frame = QFrame(self)
        self.slider_frame.move(self.button_padding, 0)

        frequencies = [22_000 // 2 ** x for x in range(self.slider_count // 2)]
        frequencies += [16_000 // 2 ** x for x in range(self.slider_count // 2)]
        frequencies.sort()
        self.bands = list(zip(frequencies[:-1], frequencies[1:]))

        for slider_index in range(self.slider_count):
            # Sliders
            vert_slider = QSlider(self.slider_frame)
            vert_slider.setObjectName("verticalSlider")
            vert_slider.setGeometry(QRect(self.slider_padding + self.slider_padding * slider_index,
                                          20, 22, 130))
            vert_slider.setRange(0, self.accuracy * 2)
            vert_slider.setValue(self.accuracy)
            vert_slider.setOrientation(Qt.Orientation.Vertical)
            vert_slider.valueChanged.connect(self.on_slider_value_changed)
            self.slider_container.append(vert_slider)
            # Labels
            freq = frequencies[slider_index]
            freq_text = f"{freq}"
            if freq > 1000:
                freq = round(freq / 1000, 1)
                freq_text = f"{freq}k"
            label = QLabel(freq_text, self.slider_frame)
            label.setGeometry(int(self.slider_padding * slider_index + self.slider_padding / 2),
                              5 if slider_index % 2 == 0 else vert_slider.height() + vert_slider.y() + 5,
                              self.slider_padding + vert_slider.width(), 10)
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.label_container.append(label)
        self.slider_frame.adjustSize()

        self.reset_button = QPushButton("", self)
        self.reset_button.setIcon(QIcon(f"{RESOURCE_ICON_DIR}restart_alt_eq.png"))
        self.reset_button.setIconSize(QSize(26, 26))
        self.reset_button.resize(28, 28)
        self.reset_button.move(5, 5)
        self.reset_button.clicked.connect(self.reset_eq)

        if eq_type is EQType.ACTIVE:
            self.active_button = QPushButton("", self)
            self.active_button.setIcon(QIcon(f"{RESOURCE_ICON_DIR}graphic_eq_enabled.png"))
            self.active_button.setIconSize(QSize(26, 26))
            self.active_button.resize(28, 28)
            self.active_button.move(5, self.reset_button.y() + self.reset_button.height() + 10)
            self.active_button.clicked.connect(self.switch_active_eq)

            self.auto_eq_button = QPushButton("", self)
            self.auto_eq_button.setIcon(QIcon(f"{RESOURCE_ICON_DIR}aq.png"))
            self.auto_eq_button.setIconSize(QSize(26, 26))
            self.auto_eq_button.resize(28, 28)
            self.auto_eq_button.move(5, self.active_button.y() + self.active_button.height() + 10)
            self.auto_eq_button.clicked.connect(self.switch_auto_eq)

            self.interpolation_button = ScrollButtonWidget("", self)
            self.interpolation_button.resize(28, 28)
            self.interpolation_button.set_range(2, 20)
            self.interpolation_button.set_value(10)
            self.interpolation_button.move(5, self.auto_eq_button.y() + self.auto_eq_button.height() + 10)
            self.interpolation_button.valueChanged.connect(self.set_interpolation)

    @pyqtSlot(int)
    def on_slider_value_changed(self, value: int) -> None:
        self.slider_gains = [slider.value() / self.accuracy for slider in self.slider_container]
        self.slidersValueChange.emit(self.slider_gains)

    def set_enabled_eq(self, enabled: Optional[bool] = None) -> None:
        if enabled is None:
            enabled = not self.slider_frame.isEnabled()
        self.slider_frame.setEnabled(enabled)

    @pyqtSlot()
    def switch_active_eq(self) -> None:
        self.active_fx = not self.active_fx
        if self.active_fx:
            self.active_button.setIcon(QIcon(f"{RESOURCE_ICON_DIR}graphic_eq_enabled.png"))
        else:
            self.active_button.setIcon(QIcon(f"{RESOURCE_ICON_DIR}graphic_eq_disable.png"))
        self.activeSwitched.emit(self.active_fx)

    @pyqtSlot()
    def switch_auto_eq(self) -> None:
        self.auto_eq = not self.auto_eq
        if self.auto_eq:
            self.auto_eq_button.setIcon(QIcon(f"{RESOURCE_ICON_DIR}aq_on.png"))
        else:
            self.auto_eq_button.setIcon(QIcon(f"{RESOURCE_ICON_DIR}aq.png"))
        self.set_enabled_eq(not self.auto_eq)
        self.reset_button.setEnabled(not self.auto_eq)
        self.autoEQSwitched.emit(self.auto_eq)

    @pyqtSlot()
    def reset_eq(self) -> None:
        if self.auto_eq:
            return
        for slider in self.slider_container:
            slider.setValue(self.accuracy)

    @pyqtSlot(int)
    def set_interpolation(self, value: int) -> None:
        self.interpolation_step = value

    def set_sliders(self, gains: Union[List[int], np.ndarray], interpolation: bool = False) -> None:
        for index, gain in enumerate(gains):
            slider = self.slider_container[index]
            if interpolation:
                if abs(gain - slider.value()) < self.interpolation_step:
                    slider.setValue(gain)
                else:
                    slider.setValue(round(slider.value() + (gain - slider.value()) / self.interpolation_step))
            else:
                slider.setValue(gain)

    def paintEvent(self, event: QPaintEvent) -> None:
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setPen(QPen(QColor("#4C4C4C"), 1.0, Qt.PenStyle.SolidLine))
        painter.drawLine(self.slider_padding + self.button_padding, 85, self.width() - self.slider_padding, 85)
        painter.setPen(QPen(QColor("#4C4C4C"), 1.0, Qt.PenStyle.DashLine))
        painter.drawLine(self.slider_padding + self.button_padding, 53, self.width() - self.slider_padding, 53)
        painter.drawLine(self.slider_padding + self.button_padding, 108, self.width() - self.slider_padding, 108)
        # painter.drawRect(0, 0, self.width() - 1, self.height() - 1)

