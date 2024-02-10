from typing import List, Optional

from PyQt6 import QtCore
from PyQt6.QtCore import pyqtSlot, QEvent, QRect, Qt, QPoint, QSize
from PyQt6.QtGui import QPaintEvent, QPainter, QBrush, QColor, QMouseEvent, QFontMetrics, QResizeEvent, QFont, QRegion, \
    QPixmap
from PyQt6.QtWidgets import QWidget, QToolTip, QLabel

from src.core.log_system import print_d
from src.function_lib.math_lib import median
from .BaseTabWidget_class import BaseTabWidget, TabItem
from src.global_constants import RESOURCE_ICON_DIR
from src.enums import MainTabWidgetIcons


class MainVerticalTabButton(QWidget):
    tab_clicked = QtCore.pyqtSignal(int)

    def __init__(self, tab_type: MainTabWidgetIcons, index: int, *args, **kwargs):
        super(MainVerticalTabButton, self).__init__(*args, **kwargs)
        self.setMouseTracking(True)

        self.font_text = QFont('Arial', 8)
        self.tab_type: MainTabWidgetIcons = tab_type
        self.margin: int = 10
        self.index: int = index
        self.is_active: bool = False

        if tab_type is MainTabWidgetIcons.HOME_PAGE:
            self.pixmap = QPixmap(RESOURCE_ICON_DIR + "home_page_tab_icon_black.png")
        elif tab_type is MainTabWidgetIcons.PLAYER:
            self.pixmap = QPixmap(RESOURCE_ICON_DIR + "player_tab_icon_black.png")
        elif tab_type is MainTabWidgetIcons.SETTINGS:
            self.pixmap = QPixmap(RESOURCE_ICON_DIR + "settings_tab_icon_black.png")
        else:
            self.pixmap = QPixmap()

        self.resize(40, 40)

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        if self.is_active:
            painter.fillRect(0, 0, self.width(), self.height(), QBrush(QColor("#B5B5B5")))
        else:
            painter.fillRect(0, 0, self.width(), self.height(), QBrush(QColor("#CCCCCC")))

        border_size: QSize = QSize(40, 40) - self.pixmap.size()
        painter.drawPixmap(round(border_size.width() / 2), round(border_size.height() / 2), self.pixmap)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        self.tab_clicked.emit(self.index)


class MainVerticalTabWidget(BaseTabWidget):
    def __init__(self, *args, **kwargs):
        super(MainVerticalTabWidget, self).__init__(*args, **kwargs)
        self.resize(300, 300)

        # region Маска событий мыши. Не реагировать родителю на мышь
        reg = QRegion(self.frameGeometry())
        reg -= QRegion(self.geometry())
        reg += self.childrenRegion()
        self.setMask(reg)
        # endregion

        self.tab_width: int = 0
        self._buttons_container: List[MainVerticalTabButton] = []
        self.margin = 0

    def add_tab(self, widget: QWidget, tab_type: MainTabWidgetIcons, resize: bool = True) -> None:
        super().add_tab(widget, tab_type.name, resize)

        tab_button = MainVerticalTabButton(tab_type, self.tab_count-1, self)
        tab_button.tab_clicked.connect(self.active_tab)

        if self._buttons_container:
            tab_button.move(0, self._buttons_container[-1].height() + self._buttons_container[-1].y() + 5)
        else:
            tab_button.move(0, 20)

        self._buttons_container.append(tab_button)
        if len(self._tab_container) == 1:
            tab_button.is_active = True
        for button in self._buttons_container:
            button.raise_()
        self.update()

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
        super(MainVerticalTabWidget, self).paintEvent(event)
        if self.isVisible():
            painter = QPainter(self)
            # painter.fillRect(self.tab_width, 0, self.width(), self.height(), QBrush(QColor("#73707B")))





