import os
import subprocess
import sys
from datetime import datetime
from typing import List, Optional, Union, TYPE_CHECKING

from PyQt6 import QtCore
from PyQt6.QtCore import pyqtSlot, QEvent, QRect, Qt, QPoint, QSize
from PyQt6.QtGui import QPaintEvent, QPainter, QBrush, QColor, QMouseEvent, QFontMetrics, QResizeEvent, QFont, QRegion, \
    QPen, QPixmap, QIcon, QShowEvent
from PyQt6.QtWidgets import QWidget, QToolTip, QLabel, QPushButton, QFrame, QScrollArea, QVBoxLayout, QMenu

from src.core.log_system import print_d
from src.core.file_system import LastFileProp
from src.enums import StateMode

if TYPE_CHECKING:
    from src.forms import MainForm


class LastFileList(QWidget):
    resource_icon_dir = "resource/2x/"

    def __init__(self, width, mf, *args, **kwargs):
        super(LastFileList, self).__init__(*args, **kwargs)

        self.widget_width = width
        self.mf: MainForm = mf

        self.setStyleSheet("""
        QLabel{
            color: white;
            background-color: transparent;
        }
        QFrame{
            background-color: transparent;
        }
        QPushButton#openFolder{
            border: 0px solid black;
            background-color: #001D3D;
            margin: 0px;
        }
        QPushButton#openFolder:hover{
            background-color: #003566;
        }

        """)

        self.file_frame = QFrame()
        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidget(self.file_frame)
        self.scroll_area.move(0, 0)
        self.scroll_area.resize(width, 500)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.v_layout = QVBoxLayout(self)
        self.v_layout.setSpacing(0)
        self.v_layout.setContentsMargins(0, 0, 0, 0)

        self.file_frame.setLayout(self.v_layout)

        self.file_frame.resize(width - 15, 145 * 1)

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self.widget_width = self.width()
        self.call_resize()

    def call_resize(self):
        self.scroll_area.resize(self.widget_width, self.height())
        self.file_frame.resize(self.widget_width - 15, 120 * (self.v_layout.count() - 1))

        for item_index in range(self.v_layout.count()):
            item = self.v_layout.itemAt(item_index)
            if item.widget() is not None:
                item.widget().resize(self.width(), item.widget().height())

    def showEvent(self, event) -> None:
        for i in reversed(range(self.v_layout.count())):
            item = self.v_layout.itemAt(i)
            if item.widget() is not None:
                item.widget().deleteLater()
            self.v_layout.removeItem(item)

        if self.mf.last_files.props:
            for _file in reversed(self.mf.last_files.props):
                last_file = LastFileItem(_file, self.mf, self)
                last_file.setFixedHeight(120)
                self.v_layout.addWidget(last_file)
            self.v_layout.addStretch()
            self.file_frame.resize(self.widget_width - 15, 120 * (self.v_layout.count() - 1))

    def delete_elem(self, item: QWidget):
        self.mf.last_files.delete(item.file_prop)  # noqa
        self.v_layout.removeWidget(item)
        self.file_frame.resize(self.widget_width - 15, 120 * (self.v_layout.count() - 1))


class LastFileItem(QWidget):
    resource_icon_dir = "res"

    def __init__(self, file_prop: LastFileProp, main_form, container, *args, **kwargs):
        super(LastFileItem, self).__init__(*args, **kwargs)
        self.resize(self.width(), 120)

        self.color = 'transparent'

        self.file_prop: LastFileProp = file_prop
        self.file_path = file_prop.path
        self.mf = main_form
        self.container: LastFileList = container

        self.label_filename = QLabel(os.path.basename(self.file_path), self)
        self.label_filename.setGeometry(QRect(0, 0, 300, 40))
        font = QFont()
        font.setPointSize(12)
        self.label_filename.setFont(font)

        self.label_date = QLabel("Посл. открытие: " + datetime.strftime(self.file_prop.last_date, '%Y-%m-%d %H:%M:%S'), self)
        self.label_date.setGeometry(QRect(0, 30, 280, 25))
        font = QFont()
        font.setPointSize(10)
        self.label_date.setFont(font)

        self.label_path = QLabel(os.path.abspath(self.file_path).replace('\\', '/'), self)
        font = QFont()
        font.setPointSize(10)
        self.label_path.setFont(font)
        self.label_path.setGeometry(QRect(0, 50, 360, 60))
        # self.label_path.setWordWrap(True)

        self.button_open = QPushButton(self)
        self.button_open.setGeometry(QRect(310, 2, 60, 50))
        self.button_open.setObjectName("openFolder")
        icon = QPixmap(os.path.join(self.resource_icon_dir, 'PlayButton.png'))
        self.button_open.setIcon(QIcon(icon))
        self.button_open.setIconSize(QSize(50, 50))
        self.button_open.clicked.connect(self.click_open_folder)

        self.file_type: str = "folder"

    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        self.recalc_sizes()

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        if self.isVisible():
            self.recalc_sizes()

    def recalc_sizes(self) -> None:
        self.label_path.resize(self.width() - 20, 60)
        self.label_path.adjustSize()
        self.button_open.move(self.width() - self.button_open.width() - 10, self.button_open.y())

    def click_open_folder(self):
        self.mf.open_file(self.file_path)

    def contextMenuEvent(self, event):
        self.color = '#2C2A35'
        self.update()
        contextMenu = QMenu(self)
        open_folder = contextMenu.addAction("Открыть")
        show_folder = contextMenu.addAction("Показать в проводнике")
        delete_elem = contextMenu.addAction("Удалить из списка")
        action = contextMenu.exec(self.mapToGlobal(event.pos()))
        if action == open_folder:
            self.button_open.click()
        elif action == show_folder:
            path = self.file_path
            path = path.replace('/', '\\')
            if sys.platform == "win32":
                subprocess.call(f'explorer /select,"{path}"')
            else:
                subprocess.call(["open", "-R", path])
        elif action == delete_elem:
            self.container.delete_elem(self)
        self.color = 'transparent'
        self.update()

    def paintEvent(self, event):
        super(LastFileItem, self).paintEvent(event)

        painter = QPainter(self)
        painter.fillRect(0, 0, self.width(), 2, QBrush(QColor('#CFCFCF')))
        painter.fillRect(0, 2, self.width(), self.height(), QBrush(QColor(self.color)))


