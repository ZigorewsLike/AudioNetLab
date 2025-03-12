import math
import os
import time
from typing import Dict, Union, TYPE_CHECKING, Optional, List

import librosa
import soundfile as sf
import numpy as np

from PyQt6 import QtCore
from PyQt6.QtCore import pyqtSlot, QEvent, QPointF, Qt, QPoint, QThread
from PyQt6.QtGui import QPaintEvent, QPainter, QBrush, QColor, QMouseEvent, QFontMetrics, QLinearGradient, QPen, QFont, \
    QResizeEvent
from PyQt6.QtWidgets import QWidget, QToolTip, QLabel, QPushButton, QFileDialog, QFrame, QScrollArea, QCheckBox

from src.global_constants import DEBUG, PROFILE
from src.core.log_system import print_d, print_e, print_i
from .NamedGraphPanel_class import NamedGraphPanel

if TYPE_CHECKING:
    from src.forms import MainForm


class LibrosaGraphsModule(QWidget):

    def __init__(self, main_form, *args, **kwargs):
        super().__init__(main_form, *args, **kwargs)
        self.setParent(main_form)
        self.setMouseTracking(True)

        self.mf: MainForm = main_form
        self.cursor_position: float = 0.0

        self.graphs_frame = QFrame()
        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidget(self.graphs_frame)
        self.scroll_area.move(0, 0)
        self.scroll_area.resize(self.width(), self.height())
        # self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.auto_update_graphs_checkbox = QCheckBox("Auto update graphs", self.graphs_frame)
        self.auto_update_graphs_checkbox.move(100, 0)

        self.save_waveform = QPushButton("Save waveform to file", self.graphs_frame)
        self.save_waveform.move(250, 0)
        self.save_waveform.clicked.connect(self.save_waveform_to_file)

        self.fourier_graph = NamedGraphPanel(self.mf, self.graphs_frame)
        self.fourier_graph.set_header("Short-time Fourier transform (STFT)")
        self.fourier_graph.set_header("Short-time Fourier transform (STFT)")
        self.fourier_graph.resize(self.width() - 10, 300)
        self.fourier_graph.move(10, 40)
        self.fourier_graph.graph.step_multiplier = 10
        self.fourier_graph.graph.brush_graph = True
        self.fourier_graph.graph.draw_peak_text = True
        self.fourier_graph.graph.profile_class_name = "NamedGraphPanel (STFT)"

        self.update_all_button = QPushButton("Update all", self.graphs_frame)
        self.update_all_button.clicked.connect(self.update_graphs)

        self.graphs_frame.resize(600, 600)

    @pyqtSlot(float)
    def set_cursor_position(self, position: int) -> None:
        self.cursor_position = position
        if self.auto_update_graphs_checkbox.isChecked():
            self.update_graphs()

    @pyqtSlot()
    def update_graphs(self) -> None:
        start_time: float = time.time()
        if self.mf.audio_player.waveform is not None and self.mf.audio_player.waveform.size > 0:
            hop_length: int = 512
            slice_left: int = int(self.mf.audio_player.waveform.shape[0] * self.cursor_position / hop_length) * hop_length
            waveform: np.ndarray = self.mf.audio_player.waveform[slice_left:slice_left + hop_length]
            waveform = waveform[:, 0].astype(np.float16) / np.iinfo(np.int16).max
            stff = np.abs(librosa.stft(waveform, n_fft=2048, hop_length=hop_length))
            slice_stff = stff[:, 0]
            self.fourier_graph.graph.set_data(slice_stff, np.float64)
        if PROFILE:
            module_name: str = self.__class__.__name__
            self.mf.profiling.add_math_time(module_name + "_upd_graphs", time.time() - start_time)

    @pyqtSlot()
    def save_waveform_to_file(self) -> None:
        if self.mf.audio_player.waveform is not None and self.mf.audio_player.waveform.size > 0:
            sf.write("data/local/audio.wav", self.mf.audio_player.waveform, self.mf.audio_player.sample_rate)

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self.scroll_area.resize(self.width(), self.height())
        self.graphs_frame.resize(self.width() - 25, self.graphs_frame.height())
        self.fourier_graph.resize(self.width() - 35, 300)

    def paintEvent(self, event: QPaintEvent) -> None:
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setPen(QPen(Qt.GlobalColor.green, 2.0, Qt.PenStyle.SolidLine))
        painter.fillRect(0, 0, self.width(), self.height(), QColor("#1E1F28"))

    def mousePressEvent(self, event: QMouseEvent) -> None:
        pass

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        pass

