import math

from PyQt6 import QtCore
from PyQt6.QtCore import pyqtSlot, QEvent, QRectF, Qt, QPropertyAnimation
from PyQt6.QtGui import QPaintEvent, QPainter, QBrush, QColor, QMouseEvent, QFontMetrics, QPixmap, QFont, QPen, \
    QPainterPath, QShowEvent
from PyQt6.QtWidgets import QWidget, QToolTip, QLabel

from src.core.log_system import print_d
from src.enums import DragFileState
from src.global_constants import RESOURCE_ICON_DIR
from src.global_styles import AppColorSchemes


class DragFileWidget(QWidget):

    def __init__(self, *args, **kwargs):
        super(DragFileWidget, self).__init__(*args, **kwargs)
        self.state: DragFileState = DragFileState.NONE
        self.pixmap = QPixmap()
        self.paint_text: str = ""
        self.paint_subtext: str = ""

    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)

    def set_state(self, state: DragFileState) -> None:
        if state is DragFileState.CORRECT:
            self.pixmap = QPixmap(RESOURCE_ICON_DIR + "drag_file_icon_white.png")
            self.paint_text = "Открыть файл в приложении ..."
            self.paint_subtext: str = ""
        elif state is DragFileState.INCORRECT:
            self.pixmap = QPixmap(RESOURCE_ICON_DIR + "drag_file_error_icon_white.png")
            self.paint_text = "Неверный формат"
            self.paint_subtext: str = "Корректные расширения: .mp3, .flac, .wave"
        else:
            self.pixmap = QPixmap()
            self.paint_text = ""
            self.paint_subtext: str = ""
        self.state = state

    def paintEvent(self, event: QPaintEvent) -> None:
        super().paintEvent(event)
        painter = QPainter(self)
        painter.fillRect(0, 0, self.width(), self.height(), QBrush(QColor(0, 0, 0, 150)))
        painter.setPen(QPen(QColor(AppColorSchemes.SCROLLBAR_BACKGROUND), 4.0, Qt.PenStyle.SolidLine))

        logo_shift: int = 25
        painter.drawPixmap(int(self.width() / 2 - self.pixmap.width() / 2),
                           int(self.height() / 2 - self.pixmap.height() / 2) - logo_shift, self.pixmap)
        rect: QRectF = QRectF(0, self.height() / 2 + self.pixmap.height() / 2 - logo_shift, self.width(), 50)
        font = QFont('Arial', 16)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, self.paint_text)

        rect: QRectF = QRectF(0, self.height() / 2 + self.pixmap.height() / 2 - logo_shift + 25, self.width(), 50)
        font = QFont('Arial', 10)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, self.paint_subtext)

        rect_width = 400
        rect_height = 300
        draw_rect = QRectF(int(self.width() / 2 - rect_width / 2), int(self.height() / 2 - rect_height / 2),
                           rect_width, rect_height)
        path = QPainterPath()
        path.addRoundedRect(draw_rect, 5, 5)
        painter.drawPath(path)





