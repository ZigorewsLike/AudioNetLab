import math

from PyQt6 import QtCore
from PyQt6.QtCore import pyqtSlot, QEvent
from PyQt6.QtGui import QPaintEvent, QPainter, QBrush, QColor, QMouseEvent, QFontMetrics
from PyQt6.QtWidgets import QWidget, QToolTip, QLabel

from src.core.log_system import print_d
from src.function_lib.math_lib import median


class SimpleSlider(QWidget):
    valueChanged = QtCore.pyqtSignal(int)
    sliderMoved = QtCore.pyqtSignal(int)
    onMouseRelease = QtCore.pyqtSignal()
    onMousePress = QtCore.pyqtSignal()

    def __init__(self, *args, **kwargs):
        super(SimpleSlider, self).__init__(*args, **kwargs)
        self.minimum: int = 0
        self.maximum: int = 100
        self.value: int = 100
        self._slider_height: int = 6
        self.top_bottom_margin: int = 10
        self.left_right_margin: int = 0

        self.is_hover: bool = False
        self.rect_always_show: bool = True
        self.is_clicked: bool = False

        # region Настройка стилей
        self.background_color: QColor = QColor("#424242")
        self.simple_color: QColor = QColor("#DADADA")
        self.hover_color: QColor = QColor("#3980FF")
        self.flag_color: QColor = QColor("#86CFFF")
        self.front_color: QColor = self.simple_color
        self.tooltip_sub_text: str = ""
        self.tooltip_visible: bool = False

        local_text_container: QLabel = QLabel()
        local_text_container.setFont(QToolTip.font())
        self.tooltip_font_metrics: QFontMetrics = local_text_container.fontMetrics()
        # endregion

        self.resize(self.parent().width(), self._slider_height + self.top_bottom_margin * 2)
        self.setMouseTracking(True)
        self.valueChanged.connect(self._slider_val_change)

    def __del__(self):
        pass

    @property
    def slider_height(self) -> int:
        return self._slider_height

    @slider_height.setter
    def slider_height(self, val: int) -> None:
        self._slider_height = val
        self.resize(self.parent().width(), self._slider_height + self.top_bottom_margin * 2)

    def set_global_margin(self, global_margin: int) -> None:
        self.top_bottom_margin = global_margin
        self.resize(self.parent().width(), self._slider_height + self.top_bottom_margin * 2)
        self.update()

    def set_value(self, value, signal: bool = True):
        if signal:
            self.valueChanged.emit(value)
        else:
            self._slider_val_change(value)

    def set_range(self, min_value: int, max_value: int) -> None:
        self.minimum = min_value
        self.maximum = max_value

    # region Методы QWidget
    def paintEvent(self, event: QPaintEvent) -> None:
        super().paintEvent(event)
        painter = QPainter(self)
        painter.fillRect(self.left_right_margin, self.top_bottom_margin, self.width() - self.left_right_margin * 2,
                         self.height() - self.top_bottom_margin * 2, QBrush(self.background_color))
        calc_width: float = (self.width() - self.left_right_margin * 2) * (self.value / (self.maximum - self.minimum))
        painter.fillRect(self.left_right_margin, self.top_bottom_margin,
                         int(calc_width), int(self.height() - self.top_bottom_margin * 2), QBrush(self.front_color))
        if self.rect_always_show or self.is_hover:
            painter.fillRect(int(calc_width - 2 + self.left_right_margin), int(self.top_bottom_margin // 2),
                             5, int(self.height() - self.top_bottom_margin), QBrush(self.flag_color))

    def mousePressEvent(self, event: QMouseEvent) -> None:
        self.is_clicked = True
        mouse_val: int = median(0, event.pos().x() - self.top_bottom_margin, self.width() - self.top_bottom_margin * 2)
        mouse_val /= self.width() - self.top_bottom_margin * 2  # Normalisation
        self.valueChanged.emit(round((self.maximum - self.minimum) * mouse_val + self.minimum))
        self.sliderMoved.emit(self.value)
        self.onMousePress.emit()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self.is_clicked = False
        self.onMouseRelease.emit()
        self.sliderMoved.emit(self.value)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        self.front_color = self.hover_color
        self.is_hover = True
        if self.is_clicked:
            mouse_val: int = median(0, event.pos().x() - self.top_bottom_margin, self.width() - self.top_bottom_margin * 2)
            mouse_val /= self.width() - self.top_bottom_margin * 2  # Normalisation
            self.valueChanged.emit(int((self.maximum - self.minimum) * mouse_val + self.minimum))
            self.sliderMoved.emit(self.value)
        self.update()

    def leaveEvent(self, event: QEvent) -> None:
        self.front_color = self.simple_color
        self.is_hover = False
        self.update()
    # endregion

    @pyqtSlot(int)
    def _slider_val_change(self, val: int) -> None:
        self.value = median(self.minimum, val, self.maximum)

        # region ToolTip
        if self.tooltip_visible:
            tooltip_text: str = f"{self.tooltip_sub_text + ' ' if self.tooltip_sub_text != '' else ''}{self.value}%"
            pos = self.parent().mapToGlobal(self.pos())
            text_width: int = self.tooltip_font_metrics.boundingRect(tooltip_text).width()
            calc_width: float = (self.width() - self.top_bottom_margin * 2) * (self.value / (self.maximum - self.minimum))
            pos.setX(int(pos.x() + calc_width - text_width // 2))
            pos.setY(int(pos.y() - (42 - self.top_bottom_margin)))
            QToolTip.showText(pos, tooltip_text)
        # endregion

        self.update()




