from typing import List, Optional, Dict

from PyQt6 import QtCore
from PyQt6.QtCore import QEvent, Qt, QPoint, QSize, QRectF
from PyQt6.QtGui import QPaintEvent, QPainter, QBrush, QColor, QMouseEvent, QResizeEvent, QFont, QRegion, \
    QPixmap, QPainterPath
from PyQt6.QtWidgets import QWidget

from src.enums import MainTabWidgetIcons
from src.global_constants import RESOURCE_ICON_DIR
from .BaseTabWidget_class import BaseTabWidget


class MainVerticalTabButton(QWidget):
    """
    Класс кнопки переключения вкладки
    """
    tab_clicked = QtCore.pyqtSignal(int)

    def __init__(self, tab_type: MainTabWidgetIcons, index: int, icon_size: Optional[QSize], *args, **kwargs):
        super(MainVerticalTabButton, self).__init__(*args, **kwargs)
        self.setMouseTracking(True)

        self.font_text = QFont('Arial', 8)
        self.tab_type: MainTabWidgetIcons = tab_type
        self.margin: int = 10
        self.index: int = index
        self.button_size: QSize = QSize(40, 40)
        self.icon_size: Optional[QSize] = icon_size
        self.border_corner: int = 5
        self.shift_rect: QPoint = QPoint(-6, 0)

        self.sub_buttons: List[MainVerticalTabSubButton] = []

        self.is_active: bool = False
        self.mouse_moved: bool = False

        self.icon_path_dict: Dict[MainTabWidgetIcons, str] = {
            MainTabWidgetIcons.HOME_PAGE: RESOURCE_ICON_DIR + "home_page_tab_icon_black.png",
            MainTabWidgetIcons.PLAYER: RESOURCE_ICON_DIR + "player_tab_icon_black.png",
            MainTabWidgetIcons.SETTINGS: RESOURCE_ICON_DIR + "settings_tab_icon_black.png",
            MainTabWidgetIcons.OPEN_FILE: RESOURCE_ICON_DIR + "open_file_tab_icon_white.png",
            MainTabWidgetIcons.GENRE_CLASSIFICATION: RESOURCE_ICON_DIR + "genre_tab_icon_white.png",
            MainTabWidgetIcons.LIBROSA_PANEL: RESOURCE_ICON_DIR + "librosa_tab_icon_white.png",
            MainTabWidgetIcons.SETTINGS_EQ: RESOURCE_ICON_DIR + "equalizer_presets.png",
            MainTabWidgetIcons.SETTINGS_AUDIO: RESOURCE_ICON_DIR + "media_output.png",
        }

        icon_path: str = self.icon_path_dict.get(self.tab_type, "")
        self.pixmap = QPixmap(icon_path)
        if icon_size is not None:
            self.pixmap = self.pixmap.scaled(self.icon_size, aspectRatioMode=Qt.AspectRatioMode.KeepAspectRatio,
                                             transformMode=Qt.TransformationMode.SmoothTransformation)

        self.resize(self.button_size)

    def set_active(self, active: bool) -> None:
        self.is_active = active

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        path = QPainterPath()
        path.addRoundedRect(QRectF(self.shift_rect.x(), self.shift_rect.y(),
                                   self.width() - self.shift_rect.x(), self.height() - self.shift_rect.y()),
                            self.border_corner, self.border_corner)

        if self.is_active:
            painter.fillPath(path, QBrush(QColor("#704D93")))
        else:
            painter.fillPath(path, QBrush(QColor("#9E8CAF")))

        if self.mouse_moved:
            painter.fillPath(path, QBrush(QColor(0, 0, 0, 40)))

        border_size: QSize = self.button_size - self.pixmap.size()
        painter.drawPixmap(round(border_size.width() / 2), round(border_size.height() / 2), self.pixmap)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        self.tab_clicked.emit(self.index)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        super().mouseMoveEvent(event)
        self.mouse_moved = True
        self.update()

    def leaveEvent(self, event: QEvent) -> None:
        super().leaveEvent(event)
        self.mouse_moved = False
        self.update()


class MainVerticalTabSubButton(MainVerticalTabButton):
    """
    Класс подраздела вкладки
    """
    tab_clicked = QtCore.pyqtSignal(int)

    def __init__(self, tab_type: MainTabWidgetIcons, index: int, icon_size: Optional[QSize], *args, **kwargs):
        super(MainVerticalTabSubButton, self).__init__(tab_type, index, icon_size, *args, **kwargs)
        self.setMouseTracking(True)

        self.tab_type: MainTabWidgetIcons = tab_type
        self.is_active: bool = False
        self.button_size = QSize(36, 36)
        self.border_corner = 0

        self.resize(self.button_size)

    def paintEvent(self, event: QPaintEvent) -> None:
        super().paintEvent(event)
        painter = QPainter(self)
        if self.index != 0:
            painter.fillRect(2, 0, self.width() - 4, 1, QBrush(QColor("#CAC7D0")))
        if self.border_corner == 0:
            painter.fillRect(2, self.height() - 1, self.width() - 4, 1, QBrush(QColor("#CAC7D0")))


class MainVerticalTabWidget(BaseTabWidget):
    """
    Класс многоуровневого TabWidget'a для главного окна
    """
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
        self.button_margin_top = 5

    def add_tab(self, widget: QWidget,
                tab_type: MainTabWidgetIcons,
                resize: bool = True,
                icon_size: Optional[QSize] = None) -> int:
        super().add_tab(widget, tab_type.name, resize)

        new_index: int = self.tab_count-1
        tab_button = MainVerticalTabButton(tab_type, new_index, icon_size, self)
        tab_button.tab_clicked.connect(self.active_tab)

        if self._buttons_container:
            tab_button.move(0, self._buttons_container[-1].height() + self._buttons_container[-1].y() + self.button_margin_top)
        else:
            tab_button.move(0, 20)

        self._buttons_container.append(tab_button)
        if len(self._tab_container) == 1:
            tab_button.is_active = True
        for button in self._buttons_container:
            button.raise_()
            for sub_button in button.sub_buttons:
                sub_button.raise_()
        self.update()
        return new_index

    def add_sub_tub(self, button_index: int, tab_type: MainTabWidgetIcons, icon_size: Optional[QSize] = None) -> None:
        sub_list = self._buttons_container[button_index].sub_buttons
        sub_tab_item = MainVerticalTabSubButton(tab_type, len(sub_list), icon_size, self)
        sub_tab_item.shift_rect = QPoint(-6, -6)
        sub_list.append(sub_tab_item)

        for sub_tab_button in sub_list[:-1]:
            sub_tab_button.border_corner = 0
        sub_list[-1].border_corner = 5

    def resize_tab_content(self) -> None:
        super().resize_tab_content()
        self.recalc_tab_button_pos()

    def recalc_tab_button_pos(self) -> None:
        move_shift: int = 20
        sub_tab_size: int = 36
        for tab_index, tab_button in enumerate(self._buttons_container):
            tab_button: MainVerticalTabButton

            if tab_index > 0:
                y_pos: int = move_shift + tab_button.height() + self.button_margin_top

                if self._buttons_container[tab_index - 1].is_active:
                    y_pos += len(self._buttons_container[tab_index - 1].sub_buttons) * sub_tab_size

                tab_button.move(tab_button.x(), y_pos)
                move_shift = y_pos

            for sub_tab_index, sub_tab_button in enumerate(tab_button.sub_buttons):
                sub_tab_button: MainVerticalTabSubButton
                if tab_button.is_active:
                    sub_tab_button.move(0, tab_button.y() + tab_button.height() + sub_tab_size * sub_tab_index)
                sub_tab_button.setVisible(tab_button.is_active)

    def get_sub_tab_button(self, tab_index: int, sub_button_index: int) -> MainVerticalTabSubButton:
        return self._buttons_container[tab_index].sub_buttons[sub_button_index]

    def active_tab(self, index: int) -> None:
        old_current_index = self.tab_current_index
        super().active_tab(index)
        if self._buttons_container:
            self._buttons_container[old_current_index].is_active = False
            self._buttons_container[self.tab_current_index].is_active = True
        self.recalc_tab_button_pos()
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





