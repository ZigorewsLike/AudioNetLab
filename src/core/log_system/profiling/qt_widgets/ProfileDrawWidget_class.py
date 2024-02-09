import math
import time
from typing import List, Optional

import numpy as np
from PyQt6 import QtCore
from PyQt6.QtCore import pyqtSlot, QEvent, Qt, QTimer, QPoint, QRect
from PyQt6.QtGui import QPaintEvent, QPainter, QBrush, QColor, QMouseEvent, QFontMetrics
from PyQt6.QtOpenGLWidgets import QOpenGLWidget
from PyQt6.QtWidgets import QWidget, QToolTip, QLabel, QPushButton, QCheckBox, QSpinBox

from src.core.log_system import print_d
from src.enums import ProfileDataType
from src.function_lib.qt_utils import array2d_to_qpolygonf
from ..ProfileDrawData_class import ProfileDrawData


class ProfileDrawWidget(QOpenGLWidget):
    valueChanged = QtCore.pyqtSignal(int)

    def __init__(self, *args, **kwargs):
        super(ProfileDrawWidget, self).__init__(*args, **kwargs)
        self.resize(600, 500)

        self.debug_graph: bool = True

        self.profile_data: ProfileDrawData = ProfileDrawData()

        self.checkbox_fps = QCheckBox("FPS mode", self)
        self.checkbox_fps.move(10, 0)
        self.checkbox_fps.stateChanged.connect(self.fps_mode_changed)

        self.spinbox_data_limiter = QSpinBox(self)
        self.spinbox_data_limiter.setMaximum(1000)
        self.spinbox_data_limiter.setMinimum(1)
        self.spinbox_data_limiter.setValue(self.profile_data.data_limiter)
        self.spinbox_data_limiter.move(self.checkbox_fps.x() + self.checkbox_fps.width() + 10, 0)
        self.spinbox_data_limiter.valueChanged.connect(self.data_limiter_changed)

        self.checkbox_ignore_zero = QCheckBox("Ignore 0", self)
        self.checkbox_ignore_zero.move(self.spinbox_data_limiter.x() + self.spinbox_data_limiter.width() + 10, 0)
        self.checkbox_ignore_zero.setChecked(True)

        self.timer = QTimer()
        self.timer.timeout.connect(self.end_timer)
        # self.timer.start(50)

    @pyqtSlot(int)
    def data_limiter_changed(self, value: int) -> None:
        self.profile_data.data_limiter = value

    @pyqtSlot(int)
    def fps_mode_changed(self, _: int) -> None:
        self.profile_data.fps_mode = self.checkbox_fps.isChecked()

    def add_draw_time(self, module: str, ms: float) -> None:
        self.profile_data.add_time(module, ms * 1000, ProfileDataType.DRAW_CALL, self.checkbox_ignore_zero.isChecked())
        self.update()

    def add_math_time(self, module: str, ms: float) -> None:
        self.profile_data.add_time(module, ms * 1000, ProfileDataType.MATH_CALL, self.checkbox_ignore_zero.isChecked())
        self.update()

    @pyqtSlot()
    def end_timer(self) -> None:
        self.update()

    @staticmethod
    def draw_debug_graph(painter: QPainter,
                         draw_call_time_array: np.ndarray,
                         x_pos: int,
                         y_pos: int,
                         width: int,
                         height: int,
                         max_data_size: Optional[int] = None) -> None:
        data_size = draw_call_time_array.size
        if data_size == 0:
            return
        if max_data_size is None:
            max_data_size = width / data_size
        step = width / max_data_size
        y_array = draw_call_time_array.copy()
        y_array_min = y_array.min()
        y_array_max = y_array.max()
        multiply_coefficient = height
        if y_array_max - y_array_min == 0:
            multiply_coefficient = 0

        x_array = np.arange(0, draw_call_time_array.size)

        point_x: np.ndarray = np.round(x_array * step + x_pos)
        point_y: np.ndarray = np.round(height - ((y_array - y_array_min) / (y_array_max - y_array_min)) * multiply_coefficient) + y_pos

        polygon = array2d_to_qpolygonf(point_x, point_y).toPolygon()
        painter.drawPolyline(polygon)

    def paintEvent(self, event: QPaintEvent) -> None:
        super().paintEvent(event)
        start_time = time.time()
        painter = QPainter(self)
        text_mode: str = "fps" if self.profile_data.fps_mode else "ms"
        x_padding = 10
        y_padding = 80
        draw_width = int(self.width() / 2 - x_padding * 2)
        common_ms: float = 0.0
        for profile_type in [ProfileDataType.DRAW_CALL, ProfileDataType.MATH_CALL]:
            x_pos = x_padding if profile_type is ProfileDataType.DRAW_CALL else x_padding + self.width() // 2
            painter.drawText(x_pos, 60, f" == {profile_type.name} ==")

            for index, module in enumerate(self.profile_data.get_modules(profile_type)):
                mean = self.profile_data.get_mean_time(module, profile_type)
                if self.profile_data.fps_mode:
                    common_ms += 1000 / mean
                else:
                    common_ms += mean
                prof_text = (f"{module}: {mean} {text_mode}  "
                             f"({self.profile_data.get_max_time(module, profile_type)}:"
                             f"{self.profile_data.get_min_time(module, profile_type)})")
                painter.drawText(x_pos, (index * 100) + y_padding, prof_text)

                if self.debug_graph:
                    graph_rect = QRect(x_pos, (index * 100) + y_padding + 5, draw_width, 70)
                    data_list = self.profile_data.get_time_list(module, profile_type)
                    self.draw_debug_graph(painter, data_list,
                                          graph_rect.x(), graph_rect.y(), graph_rect.width(), graph_rect.height(),
                                          self.profile_data.data_limiter)
                    painter.drawRect(graph_rect)

        profile_ms = round((time.time() - start_time) * 1000, 4)
        common_ms = round(common_ms, 4)
        if self.profile_data.fps_mode:
            common_text = (f"Profiler: {round(1000 / profile_ms, 2) if profile_ms != 0 else 'inf'} {text_mode}"
                           f" | Common: {round(1000 / common_ms, 2) if common_ms != 0 else 'inf'} {text_mode}")
            painter.drawText(0, 40, common_text)
        else:
            common_text = f"Profiler: {profile_ms} {text_mode} | Common: {common_ms} {text_mode}"
            painter.drawText(0, 40, common_text)


