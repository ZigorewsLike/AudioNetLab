from typing import Callable

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QMouseEvent
from PyQt6.QtWidgets import QLabel, QComboBox, QCheckBox, QSpinBox, QSlider, QLineEdit


class QLabelHelp(QLabel):
    def __init__(self, show_help: Callable, *args, **kwargs):
        super(QLabelHelp, self).__init__(*args, **kwargs)
        self.show_help = show_help
        self.setMouseTracking(True)
        self.hint = ""

    def set_hint(self, text):
        self.hint = text

    def mouseMoveEvent(self, event):
        self.show_help(self.hint)


class QComboBoxHelp(QComboBox):
    def __init__(self, show_help: Callable, *args, **kwargs):
        super(QComboBoxHelp, self).__init__(*args, **kwargs)
        self.show_help = show_help
        self.setMouseTracking(True)
        self.hint = ""

    def set_hint(self, text):
        self.hint = text

    def mouseMoveEvent(self, event):
        self.show_help(self.hint)


class QCheckBoxHelp(QCheckBox):
    def __init__(self, show_help: Callable, *args, **kwargs):
        super(QCheckBoxHelp, self).__init__(*args, **kwargs)
        self.show_help = show_help
        self.setMouseTracking(True)
        self.hint = ""

    def set_hint(self, text):
        self.hint = text

    def mouseMoveEvent(self, event):
        self.show_help(self.hint)


class QSpinBoxHelp(QSpinBox):
    def __init__(self, show_help: Callable, *args, **kwargs):
        super(QSpinBoxHelp, self).__init__(*args, **kwargs)
        self.show_help = show_help
        self.setMouseTracking(True)
        self.hint = ""

    def set_hint(self, text):
        self.hint = text

    def mouseMoveEvent(self, event):
        self.show_help(self.hint)


class QSliderHelp(QSlider):
    def __init__(self, show_help: Callable, *args, **kwargs):
        super(QSliderHelp, self).__init__(*args, **kwargs)
        self.show_help = show_help
        self.setMouseTracking(True)
        self.hint = ""

    def set_hint(self, text):
        self.hint = text

    def mouseMoveEvent(self, event: QMouseEvent):
        self.show_help(self.hint)
        if event.buttons() & Qt.MouseButton.LeftButton:
            super(QSliderHelp, self).mouseMoveEvent(event)


class QLineEditHelp(QLineEdit):
    def __init__(self, show_help: Callable, *args, **kwargs):
        super(QLineEditHelp, self).__init__(*args, **kwargs)
        self.show_help = show_help
        self.setMouseTracking(True)
        self.hint = ""

    def set_hint(self, text):
        self.hint = text

    def mouseMoveEvent(self, event):
        self.show_help(self.hint)
