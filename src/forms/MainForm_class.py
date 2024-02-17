import configparser
import gc
import math
import os
import shutil
import pickle
import tracemalloc
from datetime import datetime
from typing import Optional

import mutagen
import numpy as np
from PyQt6 import QtCore, QtSvg, QtWidgets
from PyQt6.QtCore import Qt, QRectF, QPoint, QTimer, QThread, pyqtSlot, QSize, QRect
from PyQt6.QtGui import (QPainter, QPen, QFont, QPixmap, QIcon, QBrush, QWheelEvent, QKeySequence, QMoveEvent,
                         QMouseEvent, QKeyEvent, QColor, QShowEvent, QCursor, QAction, QDragEnterEvent, QDragLeaveEvent,
                         QDropEvent, QPaintEvent)
from PyQt6.QtWidgets import (QPushButton, QMainWindow, QSlider, QLabel, QFileDialog, QMessageBox, QVBoxLayout, QMenu,
                             QFrame, QSpinBox, QProgressBar, QWidget, QApplication, QListWidgetItem, QSizeGrip,
                             QListWidget)

from src.core.audio.Player_class import MetaListItem
from src.global_constants import (APP_NAME, APP_TITLE, VERSION, CONFIG_FILENAME, GENRE_MODEL_PATH, AI_ENABLED,
                                  LAST_FILE_FILENAME, APP_ROAMING_DIR, LAST_FILE_LIMIT, RESOURCE_ICON_DIR,
                                  PATH_TO_LAST_PREVIEW, CUSTOM_TITLE_BAR)
from src.core.log_system import print_e, print_d
from src.core.log_system.profiling import ProfileDrawWidget
from src.core.point_system import Point
from src.core.settings import SettingsDataObject
from src.core.audio import AudioPlayer
from src.core.file_system import LastFileContainer, LastFileProp
from src.core.qt_widgets import (BaseTabWidget, PreLoaderWidget, VerticalTabWidget, HomePageWidget, DragFileWidget,
                                 MainVerticalTabWidget, TitleBar, SideGrip)
from src.enums import StateMode, PlayerState, DragFileState
from src.enums import StateMode, PlayerState, MainTabWidgetIcons
from src.core.workers import OpenFileWorker
from src.function_lib.math_lib import fixed_hash

from src.ai_module.genre_classification.qt_widgets import GenreClassifierModule
from src.core.render.graphics_system import LibrosaGraphsModule


class MainForm(QMainWindow):
    resized = QtCore.pyqtSignal()
    windowStateChanged = QtCore.pyqtSignal()
    resource_dir = "resource"
    resource_icon_dir = f"{resource_dir}/2x/"
    data_dir = "data/"
    local_dir = f"{data_dir}local/"

    def __init__(self, params):
        super().__init__()
        self.params: dict = params
        self.params['main_form_ref'] = self
        if CUSTOM_TITLE_BAR:
            self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint)
        self.title_bar = TitleBar(self)
        self.title_bar.setVisible(CUSTOM_TITLE_BAR)
        self.block_update: bool = False
        self.windowStateChanged.connect(self.window_state_changed)

        self.setAcceptDrops(True)
        self.create_menu_bars()
        self.profiling = ProfileDrawWidget()

        self.central_widget = QWidget(self)
        if CUSTOM_TITLE_BAR:
            self.central_widget.move(0, self.title_bar.height())
        else:
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

        self.player_frame = QWidget()

        self.meta_list = QListWidget(self.player_frame)
        self.meta_list.move(self.width(), 0)
        self.meta_list.resize(300, 300)
        self.meta_list.setContentsMargins(5, 5, 5, 5)
        # self.meta_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)

        self.tab_widget = VerticalTabWidget(self.player_frame)
        self.tab_widget.tab_switched.connect(self.tab_switched)
        self.audio_player = AudioPlayer(self, self.player_frame)

        self.home_page = HomePageWidget(self)
        self.home_page.last_file.update_file_list()

        # region Overlap widgets
        self.drag_widget = DragFileWidget(self)
        self.drag_widget.setVisible(False)

        self.preloader = PreLoaderWidget(self)
        self.preloader.setVisible(False)
        # endregion

        self.set_state_mode(self.state)

        # region AI MODULES
        self.genre_widget = GenreClassifierModule(model_path=GENRE_MODEL_PATH, main_form=self)
        if AI_ENABLED:
            self.genre_widget.load_model()
        self.audio_player.positionChanged.connect(self.genre_widget.set_cursor_position)

        # librosa graphs
        self.librosa_module = LibrosaGraphsModule(self)
        self.audio_player.positionChanged.connect(self.librosa_module.set_cursor_position)

        self.tab_widget.add_tab(self.genre_widget, "Жанр")
        self.tab_widget.add_tab(self.librosa_module, "Librosa")
        # endregion

        # region apply settings
        self.audio_player.volume_slider.set_value(self.settings.player_settings.volume)
        self.audio_player.audio_output.setVolume(self.settings.player_settings.volume / 100)
        # endregion

        self.work_thread = QThread(self)
        self.worker = OpenFileWorker()
        self.worker.mf = self
        self.worker.finished.connect(self.open_finished)
        self.worker.preloader_signal.connect(self.preloader.set_help_text)

        self.main_tab_widget = MainVerticalTabWidget(self.central_widget)
        self.main_tab_widget.add_tab(self.home_page, MainTabWidgetIcons.HOME_PAGE)
        self.main_tab_widget.add_sub_tub(0, MainTabWidgetIcons.OPEN_FILE)
        self.main_tab_widget.add_tab(self.player_frame, MainTabWidgetIcons.PLAYER)
        self.main_tab_widget.add_sub_tub(1, MainTabWidgetIcons.GENRE_CLASSIFICATION)
        self.main_tab_widget.add_sub_tub(1, MainTabWidgetIcons.LIBROSA_PANEL)
        self.main_tab_widget.add_tab(QWidget(), MainTabWidgetIcons.SETTINGS)
        self.main_tab_widget.add_sub_tub(2, MainTabWidgetIcons.OPEN_FILE)
        self.main_tab_widget.add_sub_tub(2, MainTabWidgetIcons.OPEN_FILE)
        self.main_tab_widget.add_sub_tub(2, MainTabWidgetIcons.OPEN_FILE)
        self.main_tab_widget.add_sub_tub(2, MainTabWidgetIcons.OPEN_FILE)
        self.main_tab_widget.tab_switched.connect(lambda: self.recalculate_size())

        self.main_tab_widget.get_sub_tab_button(0, 0).tab_clicked.connect(lambda: self.open_file_dialog())
        self.main_tab_widget.get_sub_tab_button(1, 0).tab_clicked.connect(lambda: self.tab_widget.active_tab(0))
        self.main_tab_widget.get_sub_tab_button(1, 1).tab_clicked.connect(lambda: self.tab_widget.active_tab(1))

        self.meta_list.raise_()

        # region SizeGrips
        self.grip_size = 4
        self.side_grips = [
            SideGrip(self, Qt.Edge.LeftEdge),
            SideGrip(self, Qt.Edge.TopEdge),
            SideGrip(self, Qt.Edge.RightEdge),
            SideGrip(self, Qt.Edge.BottomEdge),
        ]
        self.corner_grips = [QSizeGrip(self) for i in range(4)]
        # endregion

        self.recalculate_size()

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
        self.setMinimumSize(800, 720)
        self.setWindowIcon(QIcon('Icon.ico'))

    def update_grips(self):
        self.setContentsMargins(*[self.grip_size] * 4)

        out_rect = self.rect()
        in_rect = out_rect.adjusted(self.grip_size, self.grip_size, -self.grip_size, -self.grip_size)

        self.corner_grips[0].setGeometry(QRect(out_rect.topLeft(), in_rect.topLeft()))
        self.corner_grips[1].setGeometry(QRect(out_rect.topRight(), in_rect.topRight()).normalized())
        self.corner_grips[2].setGeometry(QRect(in_rect.bottomRight(), out_rect.bottomRight()))
        self.corner_grips[3].setGeometry(QRect(out_rect.bottomLeft(), in_rect.bottomLeft()).normalized())

        self.side_grips[0].setGeometry(0, in_rect.top(), self.grip_size, in_rect.height())
        self.side_grips[1].setGeometry(in_rect.left(), 0, in_rect.width(), self.grip_size)
        self.side_grips[2].setGeometry(in_rect.left() + in_rect.width(),
                                       in_rect.top(), self.grip_size, in_rect.height())
        self.side_grips[3].setGeometry(self.grip_size, in_rect.top() + in_rect.height(),
                                       in_rect.width(), self.grip_size)

    def create_menu_bars(self) -> None:
        if CUSTOM_TITLE_BAR:
            menu_bar = self.title_bar.menu_bar
        else:
            menu_bar = self.menuBar()
        file_menu = QMenu("&File", self)
        edit_menu = QMenu("&Edit", self)
        tools_menu = QMenu("&Tools", self)

        # region FileMenu
        open_file_action = QAction("Open file", self)
        open_file_action.triggered.connect(lambda: self.open_file_dialog())
        icon = QPixmap(RESOURCE_ICON_DIR + "audio_file_FILL0_wght400_GRAD0_opsz24.png")
        open_file_action.setIcon(QIcon(icon))

        player_action = QAction("Open player", self)
        player_action.triggered.connect(lambda: self.set_state_mode(StateMode.PLAYER))
        # icon = QPixmap(RESOURCE_ICON_DIR + "audio_file_FILL0_wght400_GRAD0_opsz24.png")
        # player_action.setIcon(QIcon(icon))

        home_page_action = QAction("Home page", self)
        home_page_action.triggered.connect(lambda: self.set_state_mode(StateMode.HOME_PAGE))
        icon = QPixmap(RESOURCE_ICON_DIR + "home_FILL0_wght400_GRAD0_opsz24.png")
        home_page_action.setIcon(QIcon(icon))

        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(lambda: self.close())

        file_menu.addAction(open_file_action)
        file_menu.addAction(player_action)
        file_menu.addAction(home_page_action)
        file_menu.addSeparator()
        file_menu.addAction(exit_action)
        # endregion

        # region EditMenu
        edit_menu.addAction(QAction("Aboba", self))
        # endregion

        # region ToolsMenu
        profiling_action = QAction("Profiling", self)
        profiling_action.triggered.connect(lambda: self.profiling.show())

        tools_menu.addAction(profiling_action)
        # endregion

        menu_bar.addMenu(file_menu)
        menu_bar.addMenu(edit_menu)
        menu_bar.addMenu(tools_menu)

    def showEvent(self, event: QShowEvent) -> None:
        pass

    def moveEvent(self, event: QMoveEvent) -> None:
        if self.windowState() is not Qt.WindowState.WindowMaximized:
            self.settings.system_settings.form_position.x = event.pos().x()
            self.settings.system_settings.form_position.y = event.pos().y()

    def resizeEvent(self, event):
        self.resized.emit()
        super(MainForm, self).resizeEvent(event)
        self.update_grips()

    @pyqtSlot()
    def window_state_changed(self) -> None:
        grips_enable: bool = True
        if self.windowState() is Qt.WindowState.WindowMaximized:
            grips_enable = False
        elif self.windowState() is Qt.WindowState.WindowNoState:
            grips_enable = True

        for side_grip in self.side_grips:
            side_grip.setEnabled(grips_enable)
            side_grip.setVisible(grips_enable)
        for corner_grip in self.corner_grips:
            corner_grip.setEnabled(grips_enable)
            corner_grip.setVisible(grips_enable)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if self.state is not StateMode.OPENING and not self.preloader.isVisible() and event.mimeData().hasUrls:
            event.setDropAction(Qt.DropAction.CopyAction)
            for path in event.mimeData().urls():
                if path.isLocalFile():
                    file_path = path.path()[1:]
                else:
                    file_path = str(path)
                _, file_extension = os.path.splitext(file_path)
                if file_extension.lower() in ['.mp3', '.wave', '.wav', '.flac']:
                    self.drag_widget.set_state(DragFileState.CORRECT)
                    event.accept()
                else:
                    self.drag_widget.set_state(DragFileState.INCORRECT)
                    event.accept()
                self.drag_widget.setVisible(True)
                break
        else:
            event.ignore()
            self.drag_widget.setVisible(False)

    def dropEvent(self, event: QDropEvent) -> None:
        if event.mimeData().hasUrls and self.drag_widget.state is DragFileState.CORRECT:
            event.setDropAction(Qt.DropAction.CopyAction)
            event.accept()
            for path in event.mimeData().urls():
                self.drag_widget.setVisible(False)
                if path.isLocalFile():
                    self.open_file(path.path()[1:])
                else:
                    self.open_file(str(path))
                break
        else:
            event.ignore()
            self.drag_widget.setVisible(False)

    def dragLeaveEvent(self, event: QDragLeaveEvent) -> None:
        self.drag_widget.setVisible(False)

    @pyqtSlot()
    def recalculate_size(self) -> None:
        """
        Перерасчёт размеров, позиции виджетов, объектов

        :return: None
        """

        if CUSTOM_TITLE_BAR:
            title_bar_size = QSize(0, self.title_bar.height())
            self.central_widget.resize(self.size() - title_bar_size)
            self.title_bar.resize(self.width(), self.title_bar.height())

        if self.windowState() is not Qt.WindowState.WindowMaximized:
            self.settings.system_settings.form_width = self.width()
            self.settings.system_settings.form_height = self.height()

        self.main_tab_widget.resize(self.central_widget.size())
        self.audio_player.resize(self.player_frame.width(), self.audio_player.height())
        self.audio_player.move(0, self.central_widget.height() - self.audio_player.height())
        self.tab_widget.resize(self.player_frame.width(),
                               self.player_frame.height())
        self.tab_widget.move(0, 0)
        self.tab_widget.resize_tab_content()

        if self.audio_player.meta_visible:
            self.meta_list.move(self.width() - self.meta_list.width(),
                                self.central_widget.height() - self.meta_list.height() - 52)
        else:
            self.meta_list.move(self.width(),
                                self.central_widget.height() - self.meta_list.height() - 52)

        self.preloader.resize(self.size())
        self.drag_widget.resize(self.size())

        # self.home_page.resize(self.central_widget.size())

    def set_state_mode(self, state: StateMode) -> None:
        player_enabled = state is StateMode.PLAYER
        # self.home_page.setVisible(not player_enabled)
        # self.audio_player.setVisible(player_enabled)
        if state is StateMode.PLAYER:
            self.main_tab_widget.active_tab(1)
        elif state is StateMode.HOME_PAGE:
            self.main_tab_widget.active_tab(0)
        self.state = state

    @pyqtSlot(int)
    def tab_switched(self, index: int) -> None:
        # self.tab_widget.resize(self.width(), self.height() - self.audio_player.height())
        # self.tab_widget.move(0, self.audio_player.height())
        self.tab_widget.resize_tab_content()

    def load_ann_models(self) -> None:
        pass

    def reset_open_workers(self) -> None:
        self.worker = OpenFileWorker()
        self.worker.mf = self
        self.worker.finished.connect(self.open_finished)
        self.worker.preloader_signal.connect(self.preloader.set_help_text)

        self.work_thread.exit(0)
        self.work_thread.wait()

    def open_file_dialog(self) -> None:
        dialog_filter = f"Все музыкальные форматы (*.mp3 *.flac *.wave);;" \
                        f"MP3 (*.mp3);;FLAC (*.flac);;WAVE (*.wave *.wav);;" \
                        f"Все файлы (*.*)"
        filename = QFileDialog.getOpenFileName(self, "Открыть файл",
                                               self.settings.system_settings.last_folder,
                                               dialog_filter)[0]
        if filename:
            self.settings.system_settings.last_folder = os.path.dirname(filename)
            self.open_file(filename)

    def open_file(self, file_path) -> None:
        if not os.path.exists(file_path):
            error_msg = QMessageBox()
            error_msg.setText("Файл не найден. Возможно он удалён")
            error_msg.setIcon(QMessageBox.Icon.Critical)
            error_msg.setWindowTitle("Ошибка открытия файла")
            error_msg.move(self.frameGeometry().center() - QtCore.QRect(QtCore.QPoint(), error_msg.sizeHint()).center())
            error_msg.setStandardButtons(QMessageBox.StandardButton.Ok)
            error_msg.exec()
            return
        self.preloader.setVisible(True)
        self.preloader.set_help_text("Открытие файла")
        if not self.audio_player.prepare_to_open_file(file_path):
            error_msg = QMessageBox()
            error_msg.setText("Не возможно открыть файл!")
            error_msg.setIcon(QMessageBox.Icon.Critical)
            error_msg.setWindowTitle("Ошибка открытия файла")
            error_msg.move(self.frameGeometry().center() - QtCore.QRect(QtCore.QPoint(), error_msg.sizeHint()).center())
            error_msg.setStandardButtons(QMessageBox.StandardButton.Ok)
            error_msg.exec()
            self.preloader.setVisible(False)
            return
        self.state = StateMode.OPENING

        self.worker.file_path = file_path
        self.worker.moveToThread(self.work_thread)
        self.work_thread.started.connect(self.worker.run)
        print_d("RUN Thread")
        self.work_thread.wait()
        self.work_thread.start()

    def open_finished(self, path: Optional[str]) -> None:
        self.reset_open_workers()
        self.drag_widget.setVisible(False)
        if not path:
            error_msg = QMessageBox()
            error_msg.setText("Не возможно открыть файл!")
            error_msg.setIcon(QMessageBox.Icon.Critical)
            error_msg.setWindowTitle("Ошибка открытия файла")
            error_msg.move(self.frameGeometry().center() - QtCore.QRect(QtCore.QPoint(), error_msg.sizeHint()).center())
            error_msg.setStandardButtons(QMessageBox.StandardButton.Ok)
            error_msg.exec()
            self.preloader.setVisible(False)
            return
        self.last_files.add(LastFileProp(path, datetime.now()))
        self.home_page.last_file.update_file_list()

        # region preview
        if self.audio_player.track_meta_image_bytes is not None:
            path_hash = fixed_hash(path)
            with open(f"{PATH_TO_LAST_PREVIEW}/{path_hash}.byte", "wb") as binary_file:
                binary_file.write(self.audio_player.track_meta_image_bytes)
        # endregion

        self.audio_player.player_state = PlayerState.WAIT
        self.settings.system_settings.open_filename = path
        self.save_config_app()
        gc.collect()
        self.preloader.setVisible(False)
        self.set_state_mode(StateMode.PLAYER)
        self.audio_player.audio_graph.calculate_render_lines()

    def save_config_app(self) -> None:
        self.settings.player_settings.volume = self.audio_player.volume_slider.value
        self.settings.save_to_ini(CONFIG_FILENAME)

    def closeEvent(self, event):
        if self.profiling.isVisible():
            self.profiling.close()
        self.save_config_app()

    def paintEvent(self, event: QPaintEvent) -> None:
        super(MainForm, self).paintEvent(event)
        if self.isVisible():
            painter = QPainter(self)
            # painter.fillRect(0, 0, self.width(), self.height(), QBrush(QColor("#B3B3B3")))
