import math

from PyQt6 import QtCore
from PyQt6.QtCore import pyqtSlot, QEvent, QRectF, Qt
from PyQt6.QtGui import QPaintEvent, QPainter, QBrush, QColor, QMouseEvent, QFontMetrics, QPixmap, QFont
from PyQt6.QtWidgets import QWidget, QToolTip, QLabel

from src.core.log_system import print_d
from src.global_constants import RESOURCE_ICON_DIR


class DragFileWidget(QWidget):

    def __init__(self, *args, **kwargs):
        super(DragFileWidget, self).__init__(*args, **kwargs)
        self.pixmap = QPixmap(RESOURCE_ICON_DIR + "upload_2_FILL0_wght400_GRAD0_opsz24_white.png")

    def paintEvent(self, event: QPaintEvent) -> None:
        super().paintEvent(event)
        painter = QPainter(self)
        painter.fillRect(0, 0, self.width(), self.height(), QBrush(QColor(0, 0, 0, 150)))
        logo_shift: int = 25

        painter.drawPixmap(int(self.width() / 2 - self.pixmap.width() / 2),
                           int(self.height() / 2 - self.pixmap.height() / 2) - logo_shift, self.pixmap)
        rect: QRectF = QRectF(0, self.height() / 2 + self.pixmap.height() / 2 - logo_shift, self.width(), 50)
        font = QFont('Arial', 12)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "Открыть файл в приложении ...")





