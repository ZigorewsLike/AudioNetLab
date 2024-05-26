from typing import TYPE_CHECKING, List

from PyQt6 import QtCore
from PyQt6.QtCore import QLine, QPointF, Qt, QPoint, QRectF, pyqtSlot, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QPaintEvent, QPainter, QBrush, QColor, QPen, QPolygon, QMouseEvent, QTextOption, QWheelEvent, \
    QResizeEvent
from PyQt6.QtWidgets import QWidget, QSlider

from src.function_lib.math_lib import median
from src.global_constants import DEBUG
from .GraphPanelBase_class import GraphPanelBase
from src.core.log_system import print_d


class GraphPanelAudio(GraphPanelBase):
    changeCursorPosition = QtCore.pyqtSignal(float)

    def __init__(self, main_form, *args, **kwargs):
        super().__init__(main_form, *args, **kwargs)
        self.cursor_position: float = 0.0
        self.changeCursorPosition.connect(self.cursor_position_changed)
        self.setMouseTracking(True)
        self.debug: bool = False
        self.slider_visible: bool = False
        self.mouse_clicked: bool = False
        self.mouse_position: QPoint = QPoint()
        self.old_shift: List[float] = [self.shift_left, self.shift_right]

        self.step_slider = QSlider(self)
        self.step_slider.setRange(1, 20)
        self.step_slider.setValue(self.step_multiplier)
        self.step_slider.valueChanged.connect(self.step_multiplier_changed)

        self.slider_show_anim = QPropertyAnimation(self.step_slider, b"pos")
        self.slider_show_anim.setDuration(200)

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self.step_slider.resize(15, self.height() - 20)
        if self.slider_visible:
            self.step_slider.move(self.width() - 20, 10)
        else:
            self.step_slider.move(self.width() + 5, 10)

    def paintEvent(self, event: QPaintEvent) -> None:
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
        super().mouseMoveEvent(event)
        if not self.slider_visible:
            self.slider_visible = True
            self.slider_show_anim.setEndValue(QPoint(self.width() - 20, 10))
            self.slider_show_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
            self.slider_show_anim.start()
        if self.mouse_clicked:
            delta_pos = self.mouse_position - event.pos()
            shift_delta = delta_pos.x() / self.scale_factor / self.width()
            if 0 <= self.old_shift[0] + shift_delta <= 1.0 and 0 <= self.old_shift[1] + shift_delta <= 1.0:
                self.set_shift(median(0, self.old_shift[0] + shift_delta, 1),
                               median(0, self.old_shift[1] + shift_delta, 1))

    def leaveEvent(self, event) -> None:
        super().leaveEvent(event)
        if self.slider_visible:
            self.slider_visible = False
            self.slider_show_anim.setEndValue(QPoint(self.width() + 5, 10))
            self.slider_show_anim.setEasingCurve(QEasingCurve.Type.InCubic)
            self.slider_show_anim.start()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        self.mouse_position = event.pos()
        self.mouse_clicked = True
        self.old_shift = [self.shift_left, self.shift_right]

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self.mouse_clicked = False

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        self.change_scale_graph()

    def wheelEvent(self, event: QWheelEvent) -> None:
        self.scale_factor = max(1, self.scale_factor + event.angleDelta().y() / 5)
        self.change_scale_graph()

    @pyqtSlot(int)
    def step_multiplier_changed(self, val: int) -> None:
        self.step_multiplier = val
        self.calculate_render_lines()
        self.update()

    def change_scale_graph(self) -> None:
        region_size: float = 1 / self.scale_factor
        n_l = self.cursor_position - region_size / 2
        n_r = self.cursor_position + region_size / 2
        new_shift_l = n_l - min(.0, n_l) - max(.0, n_r - 1.0)
        new_shift_r = n_r - min(.0, n_l) - max(.0, n_r - 1.0)
        if (new_shift_l, new_shift_r) != (self.shift_left, self.shift_right):
            self.set_shift(new_shift_l, new_shift_r)

        self.update()

    @pyqtSlot(float)
    def cursor_position_changed(self, position: float) -> None:
        self.cursor_position = position
        self.update()

