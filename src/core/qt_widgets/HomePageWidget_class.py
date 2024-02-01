from typing import List, Optional, Union, TYPE_CHECKING

from PyQt6 import QtCore
from PyQt6.QtCore import pyqtSlot, QEvent, QRect, Qt, QPoint
from PyQt6.QtGui import QPaintEvent, QPainter, QBrush, QColor, QMouseEvent, QFontMetrics, QResizeEvent, QFont, QRegion, \
    QPen
from PyQt6.QtWidgets import QWidget, QToolTip, QLabel, QPushButton

from src.core.log_system import print_d
from src.core.file_system.qt_widgets import LastFileList
from src.enums import StateMode

if TYPE_CHECKING:
    from src.forms import MainForm


class HomePageWidget(QWidget):
    def __init__(self, mf, *args, **kwargs):
        super(HomePageWidget, self).__init__(*args, **kwargs)
        self.resize(300, 300)
        self.setAutoFillBackground(True)

        self.mf: Union[MainForm, QWidget] = mf

        self.button_player = QPushButton("Go to player", self)
        self.button_player.clicked.connect(self.open_player)

        self.button_open = QPushButton("Open file", self)
        self.button_open.clicked.connect(self.call_open_dialog)
        self.button_open.move(100, 0)

        self.top_panel_height: int = 60

        self.last_file = LastFileList(self.width(), self.mf, self)
        self.last_file.move(0, self.top_panel_height)

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self.last_file.resize(self.width(), self.height() - self.top_panel_height)

    @pyqtSlot()
    def call_open_dialog(self) -> None:
        self.mf.open_file_dialog()

    @pyqtSlot()
    def open_player(self) -> None:
        self.mf.set_state_mode(StateMode.PLAYER)

    def update(self) -> None:
        super().update()

    def paintEvent(self, event: QPaintEvent) -> None:
        super(HomePageWidget, self).paintEvent(event)
        if self.isVisible():
            painter = QPainter(self)
            # painter.setPen(QPen(QColor("#4C4C4C"), 1.0, Qt.PenStyle.SolidLine))
