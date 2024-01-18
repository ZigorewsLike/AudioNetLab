from typing import List, Optional

from PyQt6 import QtCore
from PyQt6.QtCore import pyqtSlot, QEvent, QRect, Qt, QPoint
from PyQt6.QtGui import QPaintEvent, QPainter, QBrush, QColor, QMouseEvent, QFontMetrics, QResizeEvent, QFont, QRegion
from PyQt6.QtWidgets import QWidget, QToolTip, QLabel

from src.core.log_system import print_d
from src.function_lib.math_lib import median
from .BaseTabWidget_class import BaseTabWidget, TabItem


class VerticalTabButton(QWidget):
    tab_clicked = QtCore.pyqtSignal(int)

    def __init__(self, text: str, index: int, *args, **kwargs):
        super(VerticalTabButton, self).__init__(*args, **kwargs)
        self.setMouseTracking(True)

        self.font_text = QFont('Arial', 8)
        self.text: str = text
        self.margin: int = 10
        self.index: int = index
        self.is_active: bool = False

        self.text_rect: QRect = QFontMetrics(self.font_text).boundingRect(text)
        self.resize(self.text_rect.height() + self.margin * 2, self.text_rect.width() + self.margin * 2)

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        if self.is_active:
            painter.fillRect(0, 0, self.width(), self.height(), QBrush(QColor("#605F68")))
        else:
            painter.fillRect(0, 0, self.width(), self.height(), QBrush(QColor("#3B3842")))
        painter.rotate(-90)
        painter.setFont(self.font_text)
        painter.drawText(-self.text_rect.width() - self.margin, self.text_rect.height() + self.margin - 2, self.text)
        # painter.rotate(90)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        self.tab_clicked.emit(self.index)


class VerticalTabWidget(BaseTabWidget):
    def __init__(self, *args, **kwargs):
        super(VerticalTabWidget, self).__init__(*args, **kwargs)
        self.resize(300, 300)

        # region Маска событий мыши. Не реагировать родителю на мышь
        reg = QRegion(self.frameGeometry())
        reg -= QRegion(self.geometry())
        reg += self.childrenRegion()
        self.setMask(reg)
        # endregion

        self.tab_width: int = 35
        self._buttons_container: List[VerticalTabButton] = []

    def add_tab(self, widget: QWidget, tab_name: str, resize: bool = True, fixed_width: int = 300) -> None:
        super().add_tab(widget, tab_name, resize, fixed_width)

        tab_button = VerticalTabButton(tab_name, self.tab_count-1, self)
        tab_button.tab_clicked.connect(self.active_tab)

        if self._buttons_container:
            tab_button.move(0, self._buttons_container[-1].height() + self._buttons_container[-1].y() + 5)
        else:
            tab_button.move(0, 5)

        self._buttons_container.append(tab_button)
        if len(self._tab_container) == 1:
            tab_button.is_active = True
        self.update()

    @pyqtSlot(int)
    def active_tab(self, index: int) -> None:
        old_current_index = self.tab_current_index
        super().active_tab(index)
        if self._buttons_container:
            self._buttons_container[old_current_index].is_active = False
            self._buttons_container[self.tab_current_index].is_active = True
        self.update()

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self.resize_tab_content()
        reg = QRegion(self.frameGeometry())
        reg -= QRegion(self.geometry())
        reg += self.childrenRegion()
        self.setMask(reg)

    def paintEvent(self, event: QPaintEvent) -> None:
        super(VerticalTabWidget, self).paintEvent(event)
        if self.isVisible():
            painter = QPainter(self)
            # painter.fillRect(self.tab_width, 0, self.width(), self.height(), QBrush(QColor("#73707B")))





