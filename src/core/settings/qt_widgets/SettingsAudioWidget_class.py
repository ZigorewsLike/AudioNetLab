import os
import pickle
from typing import Dict, Union, TYPE_CHECKING, Optional, List

from PyQt6 import QtCore
from PyQt6.QtCore import pyqtSlot, QEvent, QPointF, Qt, QPoint, QThread, QSize, QRect
from PyQt6.QtGui import (QPaintEvent, QPainter, QBrush, QColor, QMouseEvent, QFontMetrics, QLinearGradient, QPen, QFont,
                         QResizeEvent, QShowEvent)
from PyQt6.QtWidgets import QWidget, QToolTip, QLabel, QPushButton, QFileDialog, QSlider, QComboBox, QFormLayout, \
    QCheckBox, QHBoxLayout

if TYPE_CHECKING:
    from src.forms import MainForm


class SettingsAudioWidget(QWidget):
    onPresetChanged = QtCore.pyqtSignal(dict)

    def __init__(self, mf, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.mf: MainForm = mf

        self.form_layout = QFormLayout(self)

        self.audio_out_device_combo = QComboBox()

        self.chunk_size_slider = QSlider(Qt.Orientation.Horizontal)
        self.chunk_size_slider.setTickPosition(QSlider.TickPosition.TicksBothSides)
        self.chunk_size_slider.setTickInterval(100)
        self.chunk_size_slider.setRange(2**8, 2**12)
        self.chunk_size_slider.valueChanged.connect(self.chunk_size_changed)
        self.chunk_size_label = QLabel("", self)

        chunk_layout = QHBoxLayout()
        chunk_layout.addWidget(self.chunk_size_slider, 10)
        chunk_layout.addWidget(self.chunk_size_label, 1)

        self.log_volume_checkbox = QCheckBox("Логарифмический регулятор громкости")
        self.log_volume_checkbox.stateChanged.connect(self.set_log_volume)

        self.form_layout.addRow("Устройство", self.audio_out_device_combo)
        self.form_layout.addRow("Параметры", QWidget())
        self.form_layout.addRow("Размер кеша", chunk_layout)
        self.form_layout.addRow("", self.log_volume_checkbox)

    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        self.load_data()

    def load_data(self) -> None:
        self.chunk_size_slider.setValue(self.mf.audio_player.audio_streamer.get_chunk_size())
        self.log_volume_checkbox.setChecked(self.mf.audio_player.audio_streamer.log_volume)

    @pyqtSlot(int)
    def set_log_volume(self, _: int) -> None:
        self.mf.audio_player.set_log_volume(self.log_volume_checkbox.isChecked())

    @pyqtSlot(int)
    def chunk_size_changed(self, value: int) -> None:
        chunk_size = value
        self.chunk_size_label.setText(f"{chunk_size}")
        self.chunk_size_label.adjustSize()

        self.mf.audio_player.audio_streamer.set_chunk_size(chunk_size)








