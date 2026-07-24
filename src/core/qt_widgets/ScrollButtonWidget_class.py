import math
from typing import Tuple

from PyQt6 import QtCore
from PyQt6.QtCore import pyqtSlot, QEvent
from PyQt6.QtGui import QPaintEvent, QPainter, QBrush, QColor, QMouseEvent, QFontMetrics, QWheelEvent
from PyQt6.QtWidgets import QWidget, QToolTip, QLabel, QPushButton

from src.core.log_system import print_d
from src.function_lib.math_lib import median


class ScrollButtonWidget(QPushButton):
    """Button holding a number that is changed with the mouse wheel.

    :signals: valueChanged (int)
    """
    valueChanged = QtCore.pyqtSignal(int)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._range: Tuple[int, int] = (0, 100)
        self._value: int = 50
        self.set_range(0, 100)

    def set_range(self, left: int, right: int) -> None:
        self._range = (min(left, right), max(left, right))
        self.set_value(self._value)

    def set_value(self, value: int) -> None:
        self._value = median(self._range[0], value, self._range[1])
        self.setText(f"{self._value}")
        self.valueChanged.emit(self._value)

    def wheelEvent(self, event: QWheelEvent) -> None:
        value = round(self._value - event.angleDelta().y() / 50)
        self.set_value(value)





