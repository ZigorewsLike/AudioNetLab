from typing import Optional

from PyQt6 import QtWidgets, QtCore
from PyQt6.QtCore import Qt, QPoint, pyqtSlot


class SideGrip(QtWidgets.QWidget):
    """Invisible strip along a window edge that resizes the frameless window by dragging.

    :signals: resizeSignal (QPoint) - mouse delta since the grab
    """
    resizeSignal = QtCore.pyqtSignal(QPoint)

    def __init__(self, parent, edge):
        QtWidgets.QWidget.__init__(self, parent)
        if edge == Qt.Edge.LeftEdge:
            self.setCursor(Qt.CursorShape.SizeHorCursor)
            self.resizeSignal.connect(self.resize_left)
        elif edge == Qt.Edge.TopEdge:
            self.setCursor(Qt.CursorShape.SizeVerCursor)
            self.resizeSignal.connect(self.resize_top)
        elif edge == Qt.Edge.RightEdge:
            self.setCursor(Qt.CursorShape.SizeHorCursor)
            self.resizeSignal.connect(self.resize_right)
        else:
            self.setCursor(Qt.CursorShape.SizeVerCursor)
            self.resizeSignal.connect(self.resize_bottom)

        self.mouse_pos: Optional[QPoint] = None

    @pyqtSlot(QPoint)
    def resize_left(self, delta):
        window = self.window()
        width = max(window.minimumWidth(), window.width() - delta.x())
        geo = window.geometry()
        geo.setLeft(geo.right() - width)
        window.setGeometry(geo)

    @pyqtSlot(QPoint)
    def resize_top(self, delta):
        window = self.window()
        height = max(window.minimumHeight(), window.height() - delta.y())
        geo = window.geometry()
        geo.setTop(geo.bottom() - height)
        window.setGeometry(geo)

    @pyqtSlot(QPoint)
    def resize_right(self, delta):
        window = self.window()
        width = max(window.minimumWidth(), window.width() + delta.x())
        window.resize(width, window.height())

    @pyqtSlot(QPoint)
    def resize_bottom(self, delta):
        window = self.window()
        height = max(window.minimumHeight(), window.height() + delta.y())
        window.resize(window.width(), height)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.mouse_pos = event.pos()

    def mouseMoveEvent(self, event):
        if self.mouse_pos is not None:
            delta = event.pos() - self.mouse_pos
            self.resizeSignal.emit(delta)

    def mouseReleaseEvent(self, event):
        self.mouse_pos = None
