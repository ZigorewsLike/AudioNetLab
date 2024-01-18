import configparser
import math
import os
import shutil
import pickle
import tracemalloc
from datetime import datetime

from PyQt6 import QtCore, QtSvg, QtWidgets
from PyQt6.QtCore import Qt, QRectF, QPoint, QTimer, QThread, pyqtSlot, QSize, QRect
from PyQt6.QtGui import (QPainter, QPen, QFont, QPixmap, QIcon, QBrush, QWheelEvent, QKeySequence, QMoveEvent,
                         QMouseEvent, QKeyEvent, QColor, QShowEvent, QCursor, QAction)
from PyQt6.QtWidgets import (QPushButton, QMainWindow, QSlider, QLabel, QFileDialog, QMessageBox, QVBoxLayout, QMenu,
                             QFrame, QSpinBox, QProgressBar, QWidget, QApplication)

from src.global_constants import (APP_NAME, APP_TITLE, VERSION, CONFIG_FILENAME, GENRE_MODEL_PATH, AI_ENABLED,
                                  LAST_FILE_FILENAME, APP_ROAMING_DIR, LAST_FILE_LIMIT)
from src.core.log_system import print_e, print_d
from src.core.point_system import Point
from src.core.settings import SettingsDataObject
from src.core.audio import AudioPlayer
from src.core.file_system import LastFileContainer, LastFileProp
from src.core.qt_widgets import BaseTabWidget, PreLoaderWidget, VerticalTabWidget, HomePageWidget
from src.enums import StateMode

from src.ai_module.genre_classification.qt_widgets import GenreClassifierModule


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

        self.create_menu_bars()

        self.central_widget = QWidget(self)
        self.central_widget.setStyleSheet("""

        """)
        self.setCentralWidget(self.central_widget)

        self.state = StateMode.LOADING

        self.screen_width = params.get("size_width")
        self.screen_height = params.get("size_height")

        self.settings = SettingsDataObject()
        self.settings.load_from_ini(CONFIG_FILENAME)

        self.installEventFilter(self)
        self.init_ui()
        self.resized.connect(self.recalculate_size)

        self.first_run: bool = False

        try:
            if not os.path.exists(LAST_FILE_FILENAME):
                if os.path.exists(os.path.join(APP_ROAMING_DIR, LAST_FILE_FILENAME)):
                    shutil.copy(os.path.join(APP_ROAMING_DIR, LAST_FILE_FILENAME), LAST_FILE_FILENAME)
                else:
                    raise FileNotFoundError
            with open(LAST_FILE_FILENAME, "rb") as f:
                self.last_files: LastFileContainer = pickle.load(f)
        except Exception as e:
            self.last_files: LastFileContainer = LastFileContainer()
            self.first_run = True
            print_e(e)

        self.tab_widget = VerticalTabWidget(self.central_widget)
        self.tab_widget.tab_switched.connect(self.tab_switched)
        self.audio_player = AudioPlayer(self, self.central_widget)

        self.home_page = HomePageWidget(self, self.central_widget)

        self.preloader = PreLoaderWidget(self)
        self.preloader.setVisible(False)

        self.set_state_mode(self.state)

        # region AI MODULES
        self.genre_widget = GenreClassifierModule(model_path=GENRE_MODEL_PATH, main_form=self)
        if AI_ENABLED:
            self.genre_widget.load_model()
        self.audio_player.positionChanged.connect(self.genre_widget.set_cursor_position)

        self.tab_widget.add_tab(self.genre_widget, "Жанр")
        self.tab_widget.add_tab(QPushButton("Debug"), "Empty")
        # endregion

        # region apply settings
        self.audio_player.volume_slider.set_value(self.settings.player_settings.volume)
        self.audio_player.audio_output.setVolume(self.settings.player_settings.volume / 100)
        # if self.settings.system_settings.open_filename and os.path.exists(self.settings.system_settings.open_filename):
        #     self.audio_player.open_file(self.settings.system_settings.open_filename)
        # endregion

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
        self.setMinimumSize(850, 300)
        self.setWindowIcon(QIcon('Icon.ico'))

    def create_menu_bars(self) -> None:
        menu_bar = self.menuBar()
        file_menu = QMenu("&File", self)
        edit_menu = QMenu("&Edit", self)

        home_page_action = QAction("Home page", self)
        home_page_action.triggered.connect(lambda: self.set_state_mode(StateMode.HOME_PAGE))

        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(lambda: self.close())

        file_menu.addAction(home_page_action)
        file_menu.addSeparator()
        file_menu.addAction(exit_action)

        menu_bar.addMenu(file_menu)
        menu_bar.addMenu(edit_menu)

    def showEvent(self, event: QShowEvent) -> None:
        pass

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

        self.audio_player.resize(self.width(), self.audio_player.height())
        self.tab_widget.resize(self.width(), self.height() - self.audio_player.height())
        self.tab_widget.move(0, self.audio_player.height())
        self.tab_widget.resize_tab_content()

        self.preloader.resize(self.width(), self.height())

        self.home_page.resize(self.size())

    def set_state_mode(self, state: StateMode) -> None:
        player_enabled = state is StateMode.PLAYER
        self.home_page.setVisible(not player_enabled)
        self.audio_player.setVisible(player_enabled)

        self.state = state

    @pyqtSlot(int)
    def tab_switched(self, index: int) -> None:
        self.tab_widget.resize(self.width(), self.height() - self.audio_player.height())
        self.tab_widget.move(0, self.audio_player.height())
        self.tab_widget.resize_tab_content()

    def load_ann_models(self) -> None:
        pass

    def open_file(self, file_path) -> None:
        if not os.path.exists(file_path):
            return
        self.audio_player.open_file(file_path)
        self.set_state_mode(StateMode.PLAYER)

    def save_config_app(self) -> None:
        self.settings.player_settings.volume = self.audio_player.volume_slider.value
        self.settings.save_to_ini(CONFIG_FILENAME)

    def closeEvent(self, event):
        self.save_config_app()
