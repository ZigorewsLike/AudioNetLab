from typing import TYPE_CHECKING, List

from PyQt6 import QtCore
from PyQt6.QtCore import QLine, QPointF, Qt, QPoint, QRectF, pyqtSlot
from PyQt6.QtGui import QPaintEvent, QPainter, QBrush, QColor, QPen, QPolygon, QMouseEvent, QTextOption, QWheelEvent
from PyQt6.QtWidgets import QWidget

from src.global_constants import DEBUG
from .GraphPanelBase_class import GraphPanelBase
from src.core.log_system import print_d


class GraphPanelAudio(GraphPanelBase):
    changeCursorPosition = QtCore.pyqtSignal(float)

    def __init__(self, main_form, *args, **kwargs):
        super().__init__(main_form, *args, **kwargs)
        self.setParent(main_form)
        self.cursor_position: float = 0.0
        self.changeCursorPosition.connect(self.cursor_position_changed)
        self.setMouseTracking(True)

    def paintEvent(self, event: QPaintEvent) -> None:
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setPen(QPen(Qt.GlobalColor.green, 2.0, Qt.PenStyle.SolidLine))
        cursor_x = int((self.cursor_position - self.shift_left) * self.scale_factor * self.width())
        painter.drawLine(cursor_x, 0, cursor_x, self.height())
        if DEBUG:
            painter.setPen(QPen(QColor("#FA887F"), 2.0, Qt.PenStyle.SolidLine))
            painter.drawText(5, 40, f'scale:{self.scale_factor}')
            painter.drawText(5, 55, f'shift:{self.shift_left} : {self.shift_right}')

    def mousePressEvent(self, event: QMouseEvent) -> None:
        pass
        # self.set_shift(event.pos().x() / self.width(), 1.0)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        self.change_scale_graph()

    def wheelEvent(self, event: QWheelEvent) -> None:
        self.scale_factor = max(1, self.scale_factor + event.angleDelta().y() / 50)
        self.change_scale_graph()

    def change_scale_graph(self) -> None:
        region_size: float = 1 / self.scale_factor
        n_l = self.cursor_position - region_size / 2
        n_r = self.cursor_position + region_size / 2
        new_shift_l = n_l - min(.0, n_l) - max(.0, n_r - 1.0)
        new_shift_r = n_r - min(.0, n_l) - max(.0, n_r - 1.0)
        if (new_shift_l, new_shift_r) != (self.shift_left, self.shift_right):
            self.set_shift(new_shift_l, new_shift_r)

        # self.set_shift(max(0., self.cursor_position - region_size / 2), min(1., self.cursor_position + region_size / 2))
        self.update()

    @pyqtSlot(float)
    def cursor_position_changed(self, position: float) -> None:
        self.cursor_position = position
        self.update()

