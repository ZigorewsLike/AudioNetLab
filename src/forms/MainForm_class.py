import configparser
import math
import os
import shutil
import pickle
import tracemalloc

from PyQt6 import QtCore, QtSvg, QtWidgets
from PyQt6.QtCore import Qt, QRectF, QPoint, QTimer, QThread, pyqtSlot, QSize, QRect
from PyQt6.QtGui import (QPainter, QPen, QFont, QPixmap, QIcon, QBrush, QWheelEvent, QKeySequence, QMoveEvent,
                         QMouseEvent, QKeyEvent, QColor, QShowEvent, QCursor)
from PyQt6.QtWidgets import (QPushButton, QMainWindow, QSlider, QLabel, QFileDialog, QMessageBox, QVBoxLayout, QMenu,
                             QFrame, QSpinBox, QProgressBar, QWidget, QApplication)

from src.global_constants import (APP_NAME, APP_TITLE, VERSION, CONFIG_FILENAME)
from src.core.point_system import Point
from src.core.settings import SettingsDataObject


class MainForm(QMainWindow):
    resized = QtCore.pyqtSignal()
    resource_dir = "resource"
    resource_icon_dir = f"{resource_dir}/2x/"
    data_dir = "data/"
    local_dir = f"{data_dir}local/"

    def __init__(self, params):
        super().__init__()
        self.params: dict = params
        self.params['main_form_ref'] = self

        self.screen_width = params.get("size_width")
        self.screen_height = params.get("size_height")

        self.settings = SettingsDataObject()
        self.settings.load_from_ini(CONFIG_FILENAME)

        self.installEventFilter(self)
        self.init_ui()

        self.resized.connect(self.recalculate_size)

    def init_ui(self):
        if self.settings.system_settings.form_position == Point(-1, -1):
            self.settings.system_settings.form_position.x = self.screen_width / 2 - self.settings.system_settings.form_width / 2
            self.settings.system_settings.form_position.y = self.screen_height / 2 - self.settings.system_settings.form_height / 2
        common_width: int = 0
        common_height: int = 0
        for screen in QApplication.screens():
            common_width += screen.size().width()
            common_height += screen.size().height()
        if self.settings.system_settings.form_position.x >= common_width:
            self.settings.system_settings.form_position.x = common_width - self.settings.system_settings.form_width
        if self.settings.system_settings.form_position.y >= common_height:
            self.settings.system_settings.form_position.y = common_height - self.settings.system_settings.form_height
        self.setGeometry(self.settings.system_settings.form_position.ix, self.settings.system_settings.form_position.iy,
                         int(self.settings.system_settings.form_width), int(self.settings.system_settings.form_height))
        self.setWindowTitle(f'{APP_TITLE} v{VERSION}')
        self.setMouseTracking(True)
        self.setMinimumSize(850, 720)
        self.setWindowIcon(QIcon('Icon.ico'))

    def moveEvent(self, event: QMoveEvent) -> None:
        self.settings.system_settings.form_position.x = event.pos().x()
        self.settings.system_settings.form_position.y = event.pos().y()

    def resizeEvent(self, event):
        self.resized.emit()
        return super(MainForm, self).resizeEvent(event)

    @pyqtSlot()
    def recalculate_size(self) -> None:
        """
        Перерасчёт размеров, позиции виджетов, объектов

        :return: None
        """
        self.settings.system_settings.form_width = self.width()
        self.settings.system_settings.form_height = self.height()

    def load_ann_models(self) -> None:
        pass

    def save_config_app(self) -> None:
        self.settings.save_to_ini(CONFIG_FILENAME)

    def closeEvent(self, event):
        self.save_config_app()
