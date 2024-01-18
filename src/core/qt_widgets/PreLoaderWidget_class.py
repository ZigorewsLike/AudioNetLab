import random
from math import cos, sin, pi

from PyQt6.QtCore import Qt, QMetaObject, QCoreApplication, QRect, QUrl, QSize, QPoint, QRectF, QTimer
from PyQt6.QtGui import QPixmap, QIcon, QPainter, QFont, QPaintEvent, QBrush, QColor, QPen, QMouseEvent, \
    QLinearGradient, QCursor, QHideEvent
# from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWidgets import QPushButton, QSlider, QLabel, QVBoxLayout, QWidget, QHBoxLayout, QFrame, QMessageBox


class PreLoaderWidget(QWidget):
    def __init__(self, *args, **kwargs):
        super(PreLoaderWidget, self).__init__(*args, **kwargs)
        self.resize(300, 300)
        self.angle: float = .0
        self.rect_count: int = 10
        self.rect_height: int = 40
        self.rect_width = 15
        self.rect_shift: int = 1
        self.color: str = "#60FF88"
        self.angular_velocity: float = .1
        self.help_text: str = ""
        self.background_color: QColor = QColor(5, 5, 5, 150)

        self.timer = QTimer()
        self.timer.timeout.connect(self.rotate_preloader)

    def showEvent(self, event):
        if self.timer.isActive():
            self.timer.stop()
        self.timer.start(10)

    def hideEvent(self, event: QHideEvent) -> None:
        super().hideEvent(event)
        if self.timer.isActive():
            self.timer.stop()

    def rotate_preloader(self):
        if self.isVisible():
            self.angle += self.angular_velocity
            if self.angle >= pi*2:
                self.angle -= pi*2
            self.update()

    def set_help_text(self, text: str):
        self.help_text = text
        self.update()

    def paintEvent(self, event: QPaintEvent):
        painter = QPainter(self)
        painter.fillRect(0, 0, self.width(), self.height(), QBrush(self.background_color))
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(QColor(0, 0, 0, 0), 0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap,
                            Qt.PenJoinStyle.RoundJoin))

        rect_width: int = self.rect_shift + self.rect_width
        for i in range(0, self.rect_count):
            painter.setBrush(QBrush(QColor(self.color), Qt.BrushStyle.SolidPattern))
            painter.fillRect(int(rect_width * i - (self.rect_count*rect_width/2) + self.width()/2 - rect_width/2),
                             int(self.height()/2),
                             self.rect_width,
                             -int(max(0.0, cos(self.angle + i/pi * 1.2)) * self.rect_height),
                             QBrush(QColor(self.color), Qt.BrushStyle.SolidPattern))
        painter.setPen(QPen(Qt.GlobalColor.white, 10, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap,
                            Qt.PenJoinStyle.RoundJoin))
        rect: QRectF = QRectF(0, self.height()/2, self.width(), 50)
        font = QFont('Arial', 12)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, self.help_text)

