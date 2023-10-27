from typing import TYPE_CHECKING, List, Tuple, Optional

import numpy as np

from PyQt6.QtCore import QLine, QPointF, Qt
from PyQt6.QtGui import QPaintEvent, QPainter, QBrush, QColor, QPen, QMouseEvent, QShowEvent, QResizeEvent
from PyQt6.QtOpenGLWidgets import QOpenGLWidget
from PyQt6.QtWidgets import QWidget

from src.core.log_system import print_d

if TYPE_CHECKING:
    from src.forms.MainForm_class import MainForm


class GraphPanelBase(QOpenGLWidget):
    def __init__(self, main_form, *args, **kwargs):
        super(GraphPanelBase, self).__init__(*args, **kwargs)
        self.mf: MainForm = main_form
        self.colors = [QColor("#5CD392"), QColor("#D0D3C7"), QColor("#D0D3C7")]
        self.lines: Tuple[np.ndarray, np.ndarray] = (np.array([]), np.array([]))
        self.max_u_count: float = 0.0
        self.setMouseTracking(True)
        self.data_type: Optional[np.dtype] = None
        self.shift_left: float = 0
        self.shift_right: float = 1
        self.scale_factor: float = 1.
        self.new_width: float = self.width()
        self.render_lines: List[QPointF] = []
        self.graph_visible: bool = True

    def showEvent(self, event: QShowEvent) -> None:
        self.new_width = self.width()

    def resizeEvent(self, event: QResizeEvent) -> None:
        super(GraphPanelBase, self).resizeEvent(event)
        self.set_shift(self.shift_left, self.shift_right)
        self.update()

    def set_data(self, data_array: np.ndarray, data_type: np.dtype = np.uint8, calc_line: bool = True):
        self.data_type = data_type
        data_array = data_array.flatten()
        self.lines: Tuple[np.ndarray, np.ndarray] = (np.arange(0, data_array.size, 1, dtype=int), data_array)
        if calc_line:
            self.calculate_render_lines()
        self.update()

    def calculate_render_lines(self):
        color_slice = self.lines[0]
        color_slice: np.ndarray = color_slice[color_slice >= int(self.shift_left * self.lines[1].size)]
        color_slice: np.ndarray = color_slice[color_slice <= int(self.shift_right * self.lines[1].size)]
        self.render_lines = [QPointF(0, self.height() / 2)]
        self.render_lines += [QPointF(((i / (self.lines[1].size - 1) - self.shift_left) * self.new_width),
                                      self.height() - self.lines[1][i] * self.height())
                              for i in color_slice[::max(1, int(color_slice.size / self.width() / 3 / self.scale_factor))]]
        self.render_lines += [QPointF(self.width(), self.height()/2)]

    def set_shift(self, shift_left: float, shift_right: float):
        self.shift_left = shift_left
        self.shift_right = shift_right
        shift: float = (1 - self.shift_right) + self.shift_left
        self.new_width = self.width()
        if shift != 1:
            self.new_width *= abs(1 / (1 - shift))
        self.calculate_render_lines()
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:
        if self.graph_visible and self.isVisible():
            painter = QPainter(self)
            painter.fillRect(0, 0, self.width(), self.height(), QBrush(QColor("#4B4B4B")))

            painter.setPen(QPen(self.colors[0], 1.0, Qt.PenStyle.SolidLine))
            painter.setBrush(QBrush(Qt.GlobalColor.transparent, Qt.BrushStyle.SolidPattern))
            if self.lines and self.render_lines:
                painter.drawPolygon(self.render_lines)
