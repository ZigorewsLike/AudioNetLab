from typing import List

from PyQt6 import QtCore
from PyQt6.QtCore import Qt, QPoint, pyqtSlot, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QPaintEvent, QPainter, QColor, QPen, QMouseEvent, QWheelEvent, QResizeEvent
from PyQt6.QtWidgets import QSlider

from src.function_lib.math_lib import median
from src.global_constants import DEBUG
from .GraphPanelBase_class import GraphPanelBase
from src.core.log_system import print_d


class GraphPanelAudio(GraphPanelBase):
    """Waveform panel of the player: playback cursor, drag to pan and wheel to zoom.

    While a track plays the visible window follows the cursor, so at a zoom above 1
    the waveform scrolls under a centred cursor.

    :signals: changeCursorPosition (float) - relative playback position in the range 0..1
    """
    changeCursorPosition = QtCore.pyqtSignal(float)

    def __init__(self, main_form, *args, **kwargs):
        """Create the panel and the detail level slider.

        :param main_form: Main form reference.
        :returns: None.
        """
        super().__init__(main_form, *args, **kwargs)
        self.cursor_position: float = 0.0
        self.changeCursorPosition.connect(self.cursor_position_changed)
        self.setMouseTracking(True)
        self.debug: bool = False
        self.slider_visible: bool = False
        self.reset_graph_scale: bool = True
        self.mouse_clicked: bool = False
        self.mouse_position: QPoint = QPoint()
        self.old_shift: List[float] = [self.shift_left, self.shift_right]
        self.step_multiplier: int = 20

        self.step_slider = QSlider(self)
        self.step_slider.setRange(1, 20)
        self.step_slider.setValue(self.step_multiplier)
        self.step_slider.valueChanged.connect(self.step_multiplier_changed)

        self.slider_show_anim = QPropertyAnimation(self.step_slider, b"pos")
        self.slider_show_anim.setDuration(200)

    def resizeEvent(self, event: QResizeEvent) -> None:
        """Keep the detail slider parked at the right edge.

        :param event: Qt resize event.
        :returns: None.
        """
        super().resizeEvent(event)
        self.step_slider.resize(15, self.height() - 20)
        if self.slider_visible:
            self.step_slider.move(self.width() - 20, 10)
        else:
            self.step_slider.move(self.width() + 5, 10)  # Parked outside the visible area

    def paintEvent(self, event: QPaintEvent) -> None:
        """Draw the waveform, the playback cursor and the debug overlay.

        :param event: Qt paint event.
        :returns: None.
        """
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setPen(QPen(Qt.GlobalColor.green, 2.0, Qt.PenStyle.SolidLine))
        cursor_x = int((self.cursor_position - self.shift_left) * self.scale_factor * self.width())
        painter.drawLine(cursor_x, 0, cursor_x, self.height())
        if DEBUG and self.debug:
            painter.setPen(QPen(QColor("#FA887F"), 2.0, Qt.PenStyle.SolidLine))
            painter.drawText(5, 40, f'scale:{self.scale_factor}')
            painter.drawText(5, 55, f'shift:{self.shift_left} : {self.shift_right}')

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        """Slide the detail slider in and pan the waveform while a button is held.

        :param event: Qt mouse event.
        :returns: None.
        """
        super().mouseMoveEvent(event)
        if not self.slider_visible:
            self.slider_visible = True
            self.slider_show_anim.setEndValue(QPoint(self.width() - 20, 10))
            self.slider_show_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
            self.slider_show_anim.start()
        if self.mouse_clicked:
            delta_pos = self.mouse_position - event.pos()
            shift_delta = delta_pos.x() / self.scale_factor / self.width()
            # Pan only while both bounds stay inside the signal
            if 0 <= self.old_shift[0] + shift_delta <= 1.0 and 0 <= self.old_shift[1] + shift_delta <= 1.0:
                self.set_shift(median(0, self.old_shift[0] + shift_delta, 1),
                               median(0, self.old_shift[1] + shift_delta, 1))

    def leaveEvent(self, event) -> None:
        """Slide the detail slider back out.

        :param event: Qt event.
        :returns: None.
        """
        super().leaveEvent(event)
        if self.slider_visible:
            self.slider_visible = False
            self.slider_show_anim.setEndValue(QPoint(self.width() + 5, 10))
            self.slider_show_anim.setEasingCurve(QEasingCurve.Type.InCubic)
            self.slider_show_anim.start()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Remember the grab point to pan from.

        :param event: Qt mouse event.
        :returns: None.
        """
        self.mouse_position = event.pos()
        self.mouse_clicked = True
        self.old_shift = [self.shift_left, self.shift_right]

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        """Stop panning.

        :param event: Qt mouse event.
        :returns: None.
        """
        self.mouse_clicked = False

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        """Recentre the visible window on the playback cursor.

        :param event: Qt mouse event.
        :returns: None.
        """
        self.change_scale_graph()

    def wheelEvent(self, event: QWheelEvent) -> None:
        """Zoom the waveform, never below the full view.

        :param event: Qt wheel event.
        :returns: None.
        """
        self.scale_factor = max(1, self.scale_factor + event.angleDelta().y() / 5)
        self.reset_graph_scale = self.scale_factor == 1.0
        self.change_scale_graph()

    @pyqtSlot(int)
    def step_multiplier_changed(self, val: int) -> None:
        """Change the number of points drawn per pixel.

        :param val: Points per pixel, larger means more detail and slower drawing.
        :returns: None.
        """
        self.step_multiplier = val
        self.calculate_render_lines()
        self.update()
        print_d(val)

    def change_scale_graph(self) -> None:
        """Centre the visible window on the cursor for the current zoom.

        :returns: None.
        """
        if self.scale_factor != 1.0 or self.reset_graph_scale:
            region_size: float = 1 / self.scale_factor
            n_l = self.cursor_position - region_size / 2
            n_r = self.cursor_position + region_size / 2
            # Push the window back inside the signal near the start and the end
            new_shift_l = n_l - min(.0, n_l) - max(.0, n_r - 1.0)
            new_shift_r = n_r - min(.0, n_l) - max(.0, n_r - 1.0)
            if (new_shift_l, new_shift_r) != (self.shift_left, self.shift_right):
                self.set_shift(new_shift_l, new_shift_r)
            self.reset_graph_scale = False
            self.update()

    @pyqtSlot(float)
    def cursor_position_changed(self, position: float) -> None:
        """Move the playback cursor.

        :param position: Relative playback position in the range 0..1.
        :returns: None.
        """
        self.cursor_position = position
        self.update()