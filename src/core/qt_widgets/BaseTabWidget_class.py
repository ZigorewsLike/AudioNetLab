from typing import List

from PyQt6 import QtCore
from PyQt6.QtCore import Qt, QPoint
from PyQt6.QtGui import QPaintEvent, QPainter, QColor, QResizeEvent, QPen
from PyQt6.QtWidgets import QWidget


class TabItem:
    """
    Класс вкладки
    """
    def __init__(self, widget: QWidget, tab_name: str):
        self.widget: QWidget = widget
        self.tab_name: str = tab_name


class BaseTabWidget(QWidget):
    """
    Класс базового виджета переключения вкладок
    """
    tab_switched = QtCore.pyqtSignal(int, bool)

    def __init__(self, *args, **kwargs):
        super(BaseTabWidget, self).__init__(*args, **kwargs)
        self.resize(300, 300)

        self.margin: int = 0
        self.is_active: bool = True
        self.content_width: int = 300
        self._fixed_position: QPoint = QPoint(0, 0)

        self.tab_count: int = 0
        self.tab_current_index: int = 0
        self.tab_width: int = 0
        self._tab_container: List[TabItem] = []

    def set_fixed_position(self, fixed_pos: QPoint) -> None:
        self._fixed_position = fixed_pos
        self.move(self._fixed_position.x() - self.width(), self._fixed_position.y())

    def add_tab(self, widget: QWidget, tab_name: str, resize: bool = True) -> None:
        self._tab_container.append(TabItem(widget, tab_name))
        self.tab_count += 1
        widget.setParent(self)
        widget.move(self.margin + self.tab_width, self.margin)
        if resize:
            widget.resize(self.width() - self.tab_width - self.margin * 2, self.height() - self.margin * 2)
        if len(self._tab_container) > 1:
            widget.hide()
        else:
            self.active_tab(0)
        self.update()

    def active_tab(self, index: int) -> None:
        self._tab_container[self.tab_current_index].widget.hide()
        self.tab_current_index = index
        self._tab_container[self.tab_current_index].widget.show()

        self.resize_tab_content()
        self.tab_switched.emit(index, True)
        self.update()

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self.resize_tab_content()

    def resize_tab_content(self) -> None:
        if self.is_active and self._tab_container:
            self.content_width = self.width() - self.tab_width
            widget = self._tab_container[self.tab_current_index].widget
            widget.resize(self.content_width - self.margin * 2, self.height() - self.margin * 2)

    def update(self) -> None:
        super().update()
        if self._tab_container:
            self._tab_container[self.tab_current_index].widget.update()
