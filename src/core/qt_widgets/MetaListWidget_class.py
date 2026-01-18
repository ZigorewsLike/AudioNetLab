from typing import List

from PyQt6.QtCore import QSize, QRectF
from PyQt6.QtGui import QPaintEvent, QPainter, QColor, QShowEvent, QResizeEvent, \
    QPainterPath
from PyQt6.QtWidgets import QWidget, QLabel, QScrollArea, QFrame

from src.core.log_system import print_d, print_e


class MetaListItem(QWidget):
    def __init__(self, key: str, values: List[str], *args, **kwargs):
        super().__init__(*args, **kwargs)
        tag_str_value: str = ""
        try:
            for tag_value in values:
                if isinstance(tag_value, list):
                    tag_str_value += ', '.join(tag_value)
                else:
                    tag_str_value += str(tag_value)
        except Exception as e:
            print_e(e)
            tag_str_value = 'UNKNOWN'
        self.label_header = QLabel(self)
        self.label_header.setText(f'<span style=" font-size:8pt; font-weight: bold; color:#5CD392;">{key}</span>')
        self.label_header.adjustSize()

        self.label_body = QLabel(self)
        self.label_body.setText(f' : {tag_str_value}')
        self.label_body.move(self.label_header.width() + self.label_header.x(), 0)

    def set_padding(self, padding: int = 0) -> None:
        self.label_header.move(padding, 0)
        self.label_body.move(self.label_header.width() + self.label_header.x(), 0)
        self.setFixedWidth(self.label_header.width() + self.label_header.x() + self.label_body.width())

    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        self.label_header.adjustSize()
        self.setFixedWidth(self.label_header.width() + self.label_header.x() + self.label_body.width())


class MetaListWidget(QWidget):
    def __init__(self, *args, **kwargs):
        super(MetaListWidget, self).__init__(*args, **kwargs)
        self.resize(300, 300)
        self._item_container: List[MetaListItem] = []
        self.item_height: int = 14
        self.footer_height: int = 43
        self.margin: int = 10
        self.item_max_width: int = self.width()
        self.item_max_width_header: int = 0

        self.setStyleSheet("""
        QFrame{
            background-color: transparent;
        }
        """)

        self.item_frame = QFrame()

        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidget(self.item_frame)
        self.scroll_area.move(self.margin, self.margin)
        self.scroll_area.resize(self.width() - (self.margin * 2), self.height())
        # self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self.scroll_area.resize(self.size() - QSize(self.margin * 2, self.margin * 2))

    def paintEvent(self, event: QPaintEvent) -> None:
        super().paintEvent(event)
        painter = QPainter(self)

        path = QPainterPath()
        path.addRoundedRect(QRectF(0, 0, self.width(), self.height()), 5, 5)
        painter.fillPath(path, QColor("#333333"))

    def clear(self) -> None:
        for item in self._item_container:
            item.deleteLater()
        self._item_container.clear()
        self.item_max_width: int = self.scroll_area.width()
        self.item_max_width_header: int = 0

    def add(self, item: MetaListItem) -> None:
        item.setParent(self.item_frame)
        item.setFixedHeight(self.item_height)
        item.adjustSize()
        widget_height = (len(self._item_container)) * self.item_height
        item.move(0, widget_height)
        item.show()

        self.item_max_width_header: int = max(item.label_header.width(), self.item_max_width_header)

        # self.item_max_width = max(item.width(), self.item_max_width)
        # print_d(self.item_max_width, item.width())
        self._item_container.append(item)
        # self.item_frame.resize(self.item_max_width, widget_height + self.item_height)

    def recalculate_size(self) -> None:
        for item in self._item_container:
            print_d(self.item_max_width_header, item.label_header.width())
            item.set_padding(self.item_max_width_header - item.label_header.width())
            item.adjustSize()
            widget_height = (len(self._item_container)) * self.item_height

            self.item_max_width = max(item.width(), self.item_max_width)
            print_d(self.item_max_width, item.width())
            self.item_frame.resize(self.item_max_width, widget_height + self.item_height)





