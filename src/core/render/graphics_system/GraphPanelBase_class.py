import time
from typing import TYPE_CHECKING, Tuple, Optional

import numpy as np
from PyQt6.QtCore import Qt, QRectF
from PyQt6.QtGui import (QPaintEvent, QPainter, QBrush, QColor, QPen, QShowEvent, QResizeEvent,
                         QPolygonF, QPainterPath)
from PyQt6.QtOpenGLWidgets import QOpenGLWidget

from src.function_lib.qt_utils import array2d_to_qpolygonf
from src.global_constants import PROFILE

if TYPE_CHECKING:
    from src.forms.MainForm_class import MainForm


class GraphPanelBase(QOpenGLWidget):
    """OpenGL panel that draws a 1D signal as a polyline.

    The source array is kept as is, only the visible window (shift_left, shift_right)
    is decimated down to the pixel width and cached as a QPolygonF, so panning and
    zooming do not rebuild the whole curve.
    """

    def __init__(self, main_form, *args, **kwargs):
        """Create the panel with its default drawing settings.

        :param main_form: Main form reference, used for profiling and update blocking.
        :returns: None.
        """
        super(GraphPanelBase, self).__init__(*args, **kwargs)
        self.mf: MainForm = main_form
        self.colors = [QColor("#5CD392"), QColor("#D0D3C7"), QColor("#D0D3C7")]
        self.lines: Tuple[np.ndarray, np.ndarray] = (np.array([]), np.array([]))  # (x indexes, y values)
        self.max_u_count: float = 0.0
        self.setMouseTracking(True)
        self.data_type: Optional[np.dtype] = None
        self.shift_left: float = 0  # Visible window bounds as a fraction of the data
        self.shift_right: float = 1
        self.scale_factor: float = 1.
        self.new_width: float = self.width()
        self.render_lines: Optional[QPolygonF] = None
        self.graph_visible: bool = True
        self.brush_graph: bool = False
        self.step_multiplier: int = 2  # Points drawn per pixel
        self.max_peak_value: float = 1.0
        self.draw_peak_text: bool = False
        self.profile_class_name: str = ""
        self.background_color: str = "#4B4B4B"
        self.background_corner: int = 0
        self.background_corner_color: str = ""

    def showEvent(self, event: QShowEvent) -> None:
        """Store the current width used by the shift math.

        :param event: Qt show event.
        :returns: None.
        """
        self.new_width = self.width()

    def resizeEvent(self, event: QResizeEvent) -> None:
        """Rebuild the polyline for the new size.

        :param event: Qt resize event.
        :returns: None.
        """
        super(GraphPanelBase, self).resizeEvent(event)
        self.set_shift(self.shift_left, self.shift_right)
        self.update()

    def set_data(self, data_array: np.ndarray, data_type: np.dtype = np.uint8, calc_line: bool = True):
        """Load the signal to draw, normalising it to the range 0..1.

        :param data_array: Source values.
        :param data_type: Original data type of the samples.
        :param calc_line: Build the polyline right away.
        :returns: None.
        """
        data_max = data_array.max()
        if data_max > 1.0:  # Already normalised data is kept as is
            data_min = data_array.min()
            self.max_peak_value = data_max
            data_array = (data_array - data_min) / (data_max - data_min)
        else:
            self.max_peak_value = 1.0
        self.data_type = data_type
        data_array = data_array.flatten()
        self.lines: Tuple[np.ndarray, np.ndarray] = (np.arange(0, data_array.size, 1, dtype=int), data_array)
        if calc_line:
            self.calculate_render_lines()
        self.update()

    def calculate_render_lines(self, forcedly: bool = False):
        """Rebuild the cached polyline out of the visible part of the signal.

        :param forcedly: Build even when the widget is hidden or updates are blocked.
        :returns: None.
        """
        if (not self.mf.block_update and self.isVisible()) or forcedly:
            start_time: float = time.time()
            wave_slice = self.lines[0]
            wave_slice: np.ndarray = wave_slice[wave_slice >= int(self.shift_left * self.lines[1].size)]
            wave_slice: np.ndarray = wave_slice[wave_slice <= int(self.shift_right * self.lines[1].size)]
            if wave_slice.size == 0:
                return
            # Off screen anchors close the polygon below the visible area
            x_np_line: np.ndarray = np.array([-10])
            y_np_line: np.ndarray = np.array([self.height() + 50])
            # Take at most step_multiplier points per pixel
            x_slice = wave_slice[::max(1, int(wave_slice.size / self.width() / self.step_multiplier / self.scale_factor))]
            y_slice = self.lines[1][x_slice]

            x_slice_clac = (x_slice / (self.lines[1].size - 1) - self.shift_left) * self.new_width
            y_slice_clac = self.height() - y_slice * self.height()

            x_np_line = np.append(x_np_line, np.append(x_slice_clac, [self.width() + 10]))
            y_np_line = np.append(y_np_line, np.append(y_slice_clac, [self.height() + 50]))

            self.render_lines = array2d_to_qpolygonf(x_np_line, y_np_line)
            if PROFILE:
                module_name: str = self.__class__.__name__ if not self.profile_class_name else self.profile_class_name
                self.mf.profiling.add_math_time(module_name + "_lines", time.time() - start_time)

    def set_shift(self, shift_left: float, shift_right: float):
        """Set the visible window of the signal and rebuild the polyline.

        :param shift_left: Left bound as a fraction of the data, 0..1.
        :param shift_right: Right bound as a fraction of the data, 0..1.
        :returns: None.
        """
        self.shift_left = shift_left
        self.shift_right = shift_right
        shift: float = (1 - self.shift_right) + self.shift_left
        # Virtual width of the full signal at the current zoom
        self.new_width = self.width()
        if shift != 1:
            self.new_width *= abs(1 / (1 - shift))
        self.calculate_render_lines()
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:
        """Draw the background and the cached polyline.

        :param event: Qt paint event.
        :returns: None.
        """
        start_time: float = time.time()
        if not self.mf.block_update and self.graph_visible and self.isVisible():
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)

            painter.fillRect(0, 0, self.width(), self.height(), QBrush(QColor(self.background_color)))

            if self.background_corner_color and self.background_corner != 0:
                path = QPainterPath()
                path.addRoundedRect(QRectF(0, 0, self.width() - 1, self.height() - 1),
                                    self.background_corner, self.background_corner)
                painter.fillPath(path, QBrush(QColor(self.background_corner_color)))

            painter.setPen(QPen(self.colors[0], 1.0, Qt.PenStyle.SolidLine))
            if self.brush_graph:
                painter.setBrush(QBrush(self.colors[0], Qt.BrushStyle.SolidPattern))
            else:
                painter.setBrush(QBrush(Qt.GlobalColor.transparent, Qt.BrushStyle.SolidPattern))
            if self.lines and self.render_lines:
                if self.brush_graph:
                    painter.drawPolygon(self.render_lines)
                else:
                    painter.drawPolyline(self.render_lines)

            if self.draw_peak_text:
                painter.setPen(QPen(Qt.GlobalColor.white, 1.0, Qt.PenStyle.SolidLine))
                painter.drawText(10, 10, f"{self.max_peak_value}")
        if PROFILE:
            self.mf.profiling.add_draw_time(self.__class__.__name__ if not self.profile_class_name else self.profile_class_name,
                                            time.time() - start_time)