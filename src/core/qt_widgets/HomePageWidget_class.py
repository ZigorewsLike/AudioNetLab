from typing import Union, TYPE_CHECKING

from PyQt6 import QtCore
from PyQt6.QtCore import pyqtSlot, QEvent
from PyQt6.QtGui import (QPaintEvent, QPainter, QColor, QMouseEvent, QResizeEvent, QFont, QPixmap)
from PyQt6.QtWidgets import QWidget, QLabel, QFrame

from src.core.file_system.qt_widgets import LastFileList
from src.global_constants import RESOURCE_ICON_DIR
from src.global_styles import AppColorSchemes

if TYPE_CHECKING:
    from src.forms import MainForm


class HomePageButtonWidget(QWidget):
    """Wide "Open file" button at the top of the home page.

    :signals: clicked ()
    """
    clicked = QtCore.pyqtSignal()

    def __init__(self, *args, **kwargs):
        super(HomePageButtonWidget, self).__init__(*args, **kwargs)
        self.resize(300, 300)
        self.setStyleSheet("""
        QFrame#MainFrame{
            background-color: """ + AppColorSchemes.FILE_LIST_ITEM_BODY + """;
        }
        QFrame#InfoFrame{
            background-color: transparent;
        }
        QFrame#MainFrame:hover{
            background-color: """ + AppColorSchemes.BUTTON_HOVER + """;
        }
        QLabel{
            background-color: transparent;
            color: black;
        }
        """)

        self.frame_button = QFrame(self)
        self.frame_button.setObjectName("MainFrame")

        self.frame_info = QFrame(self)
        self.frame_info.setObjectName("InfoFrame")
        self.frame_info.setMouseTracking(False)
        self.frame_info.resize(128, 40)
        self.logo = QLabel(self.frame_info)
        self.logo.setPixmap(QPixmap(f"{RESOURCE_ICON_DIR}open_file_icon_white.png"))
        self.logo.resize(40, 40)

        self.header_text = QLabel("", self.frame_info)
        font = QFont("Arima")
        font.setPointSize(13)
        font.setBold(True)
        self.header_text.setFont(font)
        self.header_text.move(self.logo.width() + 10, 4)

        self.footer_text = QLabel(".MP3, .FLAC, .WAVE", self.frame_info)
        font = QFont("Arima")
        font.setPointSize(6)
        self.footer_text.setFont(font)
        self.footer_text.move(self.logo.width() + 10, 27)
        self.footer_text.adjustSize()

        self.retranslate_ui()

    def changeEvent(self, event: QEvent) -> None:
        """Reapply the texts when the application language changes.

        :param event: Qt event.
        :returns: None.
        """
        if event.type() == QEvent.Type.LanguageChange:
            self.retranslate_ui()
        super().changeEvent(event)

    def retranslate_ui(self) -> None:
        """Apply the current translation to the button caption.

        :returns: None.
        """
        self.header_text.setText(self.tr("Open file"))
        self.header_text.adjustSize()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self.clicked.emit()

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self.frame_button.resize(self.size())
        self.frame_info.move(int(self.width() / 2 - self.frame_info.width() / 2), 10)


class HomePageWidget(QWidget):
    """Home tab: the open file button and the list of recently opened tracks."""

    def __init__(self, mf, *args, **kwargs):
        super(HomePageWidget, self).__init__(*args, **kwargs)
        self.resize(300, 300)
        self.setAutoFillBackground(True)

        self.top_panel_height: int = 80
        self.left_padding = 10
        self.right_padding = 0

        self.mf: Union[MainForm, QWidget] = mf

        self.button_open = HomePageButtonWidget(self)
        self.button_open.clicked.connect(self.call_open_dialog)
        self.button_open.move(self.left_padding, 10)

        self.last_file = LastFileList(self.width() - self.right_padding - self.left_padding, self.mf, self)
        self.last_file.move(self.left_padding, self.top_panel_height)

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self.last_file.resize(self.width() - self.right_padding - self.left_padding,
                              self.height() - self.top_panel_height)
        self.button_open.resize(self.width() - self.left_padding - 30, self.top_panel_height - 20)

    @pyqtSlot()
    def call_open_dialog(self) -> None:
        self.mf.add_file_dialog()

    def update(self) -> None:
        super().update()

    def paintEvent(self, event: QPaintEvent) -> None:
        super(HomePageWidget, self).paintEvent(event)
        if self.isVisible():
            painter = QPainter(self)
            painter.fillRect(0, 0, self.width(), self.height(), QColor(AppColorSchemes.FILE_LIST_BACKGROUND))
