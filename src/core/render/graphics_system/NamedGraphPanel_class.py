from typing import List, Optional

import numpy as np
from PyQt6 import QtCore
from PyQt6.QtCore import pyqtSlot, QEvent, QRect, Qt, QPoint
from PyQt6.QtGui import QPaintEvent, QPainter, QBrush, QColor, QMouseEvent, QFontMetrics, QResizeEvent, QFont, QRegion, \
    QPen
from PyQt6.QtWidgets import QWidget, QToolTip, QLabel

from .GraphPanelBase_class import GraphPanelBase


class NamedGraphPanel(QWidget):
    """GraphPanelBase with a caption above it. Currently unused."""

    def __init__(self, mf, *args, **kwargs):
        super(NamedGraphPanel, self).__init__(*args, **kwargs)
        self.header_padding: int = 30

        self.graph = GraphPanelBase(mf, self)
        self.graph.profile_class_name = "NamedGraphPanel"

        self.label = QLabel("Text", self)
        self.label.setFont(QFont("Arial", 14))

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self.recalc_sizes()

    def set_header(self, text: str) -> None:
        self.label.setText(text)
        self.label.adjustSize()
        self.recalc_sizes()

    def recalc_sizes(self) -> None:
        self.graph.move(0, self.header_padding)
        self.graph.resize(self.width(), self.height() - self.header_padding)
        self.label.move(int(self.width() / 2 - self.label.width() / 2), self.label.y())

