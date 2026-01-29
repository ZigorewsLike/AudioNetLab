import gc
import os
from typing import Optional

from PyQt6 import QtCore
from PyQt6.QtCore import Qt, QThread, pyqtSlot, QSize, QRect
from PyQt6.QtGui import (QPainter, QPixmap, QIcon, QMoveEvent,
                         QShowEvent, QAction, QDragEnterEvent, QDragLeaveEvent,
                         QDropEvent, QPaintEvent, QBrush, QColor)
from PyQt6.QtWidgets import (QMainWindow, QFileDialog, QMessageBox, QMenu,
                             QWidget, QApplication, QSizeGrip, QTabWidget)

from src.ai_module.genre_classification import GenreClassifierModule
from src.ai_module.transcription import AudioTranscriptionModule
from src.core.audio import AudioPlayer
from src.core.file_system import FileMetaController
from src.core.log_system import print_d
from src.core.log_system.profiling import ProfileDrawWidget
from src.core.point_system import Point
from src.core.qt_widgets import (PreLoaderWidget, HomePageWidget, DragFileWidget,
                                 MainVerticalTabWidget, TitleBar, SideGrip)
from src.core.settings import SettingsDataObject
from src.core.settings.qt_widgets import SettingsFrame
from src.core.workers import OpenFileWorker
from src.enums import StateMode, PlayerState, MainTabWidgetIcons, DragFileState
from src.function_lib.math_lib import fixed_hash
from src.global_constants import (APP_TITLE, VERSION, CONFIG_FILENAME, GENRE_MODEL_PATH, AI_ENABLED,
                                  RESOURCE_ICON_DIR,
                                  PATH_TO_LAST_REGISTRY, CUSTOM_TITLE_BAR)
from src.global_styles import AppColorSchemes


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
        self.file_meta_controller = FileMetaController()

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

        # self.meta_list.setContentsMargins(5, 5, 5, 5)
        # self.meta_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)

        self.tab_widget = QTabWidget(self.central_widget)
        self.tab_widget.currentChanged.connect(self.on_tab_changed)
        self.tab_widget.setStyleSheet(f"""
        QWidget{{
            background-color: {AppColorSchemes.FILE_LIST_BACKGROUND};
            color: black;
        }}
        QTabWidget{{
            background-color: {AppColorSchemes.FILE_LIST_BACKGROUND};
            padding: 0px;
        }}
        QTabBar::tab {{
            color: black;
            background-color: #e0e0e0;
            border: 1px solid #939393;
            border-bottom-color: {AppColorSchemes.FILE_LIST_BACKGROUND};
            border-top-left-radius: 4px;
            border-top-right-radius: 4px;
            min-width: 100px;
            min-height: 25px;
            padding: 0px 10px;
            margin-left: 2px;
        }}
        
        QTabBar::tab:selected {{
            color: black;
            background-color: {AppColorSchemes.FILE_LIST_BACKGROUND};
            border-bottom-color: {AppColorSchemes.FILE_LIST_BACKGROUND};
            font-weight: bold;
        }}
        """)
        "AFAFAF"
        # self.tab_widget.tab_switched.connect(self.tab_switched)
        self.audio_player = AudioPlayer(self, self.central_widget)
        # self.audio_player.show()

        self.home_page = HomePageWidget(self, self.central_widget)
        self.home_page.last_file.update_file_list()
        self.tab_widget.addTab(self.home_page, 'Home')

        # region Overlap widgets
        self.drag_widget = DragFileWidget(self)
        self.drag_widget.setVisible(False)

        self.preloader = PreLoaderWidget(self)
        self.preloader.setVisible(False)
        if CUSTOM_TITLE_BAR:
            self.preloader.move(0, self.title_bar.height())
        # endregion

        # region AI MODULES
        self.genre_widget = GenreClassifierModule(model_path=GENRE_MODEL_PATH, main_form=self)
        self.tab_widget.addTab(self.genre_widget, 'EQ AI')
        if AI_ENABLED:
            self.genre_widget.load_model()
        self.audio_player.positionChanged.connect(self.genre_widget.set_cursor_position)

        self.transcription_module = AudioTranscriptionModule(self)
        self.tab_widget.addTab(self.transcription_module, 'Transcription')
        self.audio_player.audio_streamer.progress.connect(self.transcription_module.on_position_changed)
        # endregion

        # region apply settings
        self.audio_player.volume_slider.set_value(self.settings.player_settings.volume)
        self.audio_player.audio_streamer.set_volume(self.settings.player_settings.volume / self.audio_player.volume_slider.maximum)
        # endregion

        self.work_thread = QThread(self)
        self.worker = OpenFileWorker()
        self.worker.mf = self
        self.worker.finished.connect(self.open_finished)
        self.worker.preloader_signal.connect(self.preloader.set_help_text)

        # self.settings_widget = QWidget()
        self.settings_widget = SettingsFrame(mf=self)
        self.tab_widget.addTab(self.settings_widget, 'Settings')

        self.genre_widget.eq.slidersValueChange.connect(self.audio_player.set_eq_gains)
        self.genre_widget.eq.activeSwitched.connect(self.audio_player.audio_streamer.set_eq_active)
        self.audio_player.audio_streamer.bands = self.genre_widget.eq.bands
        self.genre_widget.genre_eq = self.settings_widget.eq_settings.load_preset_from_file()
        self.settings_widget.eq_settings.onPresetChanged.connect(self.genre_widget.on_preset_changed)

        # self.main_tab_widget = MainVerticalTabWidget(self.central_widget)

        self.audio_player.meta_list.raise_()

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
        open_file_action.triggered.connect(lambda: self.add_file_dialog())
        icon = QPixmap(RESOURCE_ICON_DIR + "audio_file_FILL0_wght400_GRAD0_opsz24.png")
        open_file_action.setIcon(QIcon(icon))

        player_action = QAction("Open player", self)
        # icon = QPixmap(RESOURCE_ICON_DIR + "audio_file_FILL0_wght400_GRAD0_opsz24.png")
        # player_action.setIcon(QIcon(icon))

        home_page_action = QAction("Home page", self)
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
        edit_menu.addAction(QAction("", self))
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
        if not self.preloader.isVisible() and event.mimeData().hasUrls:
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
                    self.add_file(path.path()[1:])
                else:
                    self.add_file(str(path))
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
        preloader_size: QSize = self.size()
        # if self.audio_player.isVisible():
        #     preloader_size = preloader_size - QSize(0, self.audio_player.height())

        if CUSTOM_TITLE_BAR:
            title_bar_size = QSize(0, self.title_bar.height())
            self.central_widget.resize(self.size() - title_bar_size)
            self.title_bar.resize(self.width(), self.title_bar.height())
            self.preloader.resize(preloader_size - title_bar_size)
        else:
            self.preloader.resize(preloader_size)

        if self.windowState() is not Qt.WindowState.WindowMaximized:
            self.settings.system_settings.form_width = self.width()
            self.settings.system_settings.form_height = self.height()

        # self.main_tab_widget.resize(self.central_widget.size())
        self.audio_player.resize(self.central_widget.width(), self.audio_player.height())
        self.audio_player.move(0, self.central_widget.height() - self.audio_player.height())
        self.tab_widget.resize(self.central_widget.width(),
                               self.central_widget.height() - self.audio_player.height())
        # self.settings_widget.resize(self.central_widget.size())

        self.drag_widget.resize(self.size())

    def show_preloader(self) -> None:
        self.preloader.setVisible(True)
        self.recalculate_size()

    def show_error_message_log(self, title: str, text: str) -> None:
        error_msg = QMessageBox()
        error_msg.setText(text)
        error_msg.setIcon(QMessageBox.Icon.Critical)
        error_msg.setWindowTitle(title)
        error_msg.move(self.frameGeometry().center() - QtCore.QRect(QtCore.QPoint(), error_msg.sizeHint()).center())
        error_msg.setStandardButtons(QMessageBox.StandardButton.Ok)
        error_msg.exec()

    def load_ann_models(self) -> None:
        pass

    def reset_open_workers(self) -> None:
        self.worker = OpenFileWorker()
        self.worker.mf = self
        self.worker.finished.connect(self.open_finished)
        self.worker.preloader_signal.connect(self.preloader.set_help_text)

        self.work_thread.exit(0)
        self.work_thread.wait()

    def add_file_dialog(self) -> None:
        dialog_filter = f"Все музыкальные форматы (*.mp3 *.flac *.wave);;" \
                        f"MP3 (*.mp3);;FLAC (*.flac);;WAVE (*.wave *.wav);;" \
                        f"Все файлы (*.*)"
        filename = QFileDialog.getOpenFileName(self, "Открыть файл",
                                               self.settings.system_settings.last_folder,
                                               dialog_filter)[0]
        if filename:
            self.settings.system_settings.last_folder = os.path.dirname(filename)
            self.add_file(filename)

    def add_file(self, file_path: str) -> None:
        if not os.path.exists(file_path):
            self.show_error_message_log("Ошибка открытия файла", "Файл не найден. Возможно он удалён")
            return
        filename, file_extension = os.path.splitext(os.path.basename(file_path))
        meta = self.file_meta_controller.read_track_file(file_path)
        track_name = meta.get('title')
        title = track_name[0] if track_name is not None else filename
        track_id: int = self.home_page.last_file.add(title, file_path)
        if track_id is None:
            return
        self.file_meta_controller.save_meta_in_registry(track_id)
        self.home_page.last_file.update_file_list()

    def open_file(self, file_path, track_id: int = 6) -> None:
        if not os.path.exists(file_path):
            self.show_error_message_log("Ошибка открытия файла", "Файл не найден. Возможно он удалён")
            return
        self.show_preloader()
        self.preloader.set_help_text("Открытие файла")

        meta = self.file_meta_controller.get_track_meta(track_id)
        if not self.audio_player.prepare_to_open_file(file_path, meta):
            self.show_error_message_log("Ошибка открытия файла", "Не возможно открыть файл!")
            self.preloader.setVisible(False)
            return
        cover = self.file_meta_controller.get_preview_cover(track_id, file_path=file_path)
        if cover is None:
            icon_index: int = fixed_hash(str(track_id)) % 6
            self.audio_player.set_default_track_cover(icon_index=icon_index)
        else:
            self.audio_player.set_track_cover(cover)
        self.audio_player.player_state_changed = PlayerState.OPENING
        self.audio_player.playable_track_id = track_id
        self.audio_player.playable_file_file = file_path
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
            self.show_error_message_log("Ошибка открытия файла", "Не возможно открыть файл!")
            self.preloader.setVisible(False)
            return
        # filename, file_extension = os.path.splitext(path)
        # track_name = self.file_meta_controller.track_meta.get('title')
        # title = track_name[0] if track_name is not None else filename
        # track_id: int = self.home_page.last_file.add(title, path)
        self.home_page.last_file.update_file_list()
        # self.file_meta_controller.save_meta_in_registry(track_id)

        self.audio_player.play_music()
        self.settings.system_settings.open_filename = path
        self.save_config_app()
        gc.collect()
        self.preloader.setVisible(False)
        self.audio_player.audio_graph.calculate_render_lines(forcedly=True)
        self.genre_widget.reset_result()

        self.transcription_module.clear()
        transcription = self.file_meta_controller.get_track_transcription(self.audio_player.playable_track_id)
        if transcription is not None:
            self.transcription_module.set_transcription_data(transcription)
        else:
            transcription = self.transcription_module.get_lyrics_from_file()
            if transcription.get('segments', []):
                self.transcription_module.set_transcription_data(transcription)


    def get_current_lyrics(self) -> Optional[str]:
        track_id = self.audio_player.playable_track_id
        return self.file_meta_controller.get_lyrics(track_id)

    def save_config_app(self) -> None:
        self.settings.player_settings.volume = self.audio_player.volume_slider.value
        self.settings.save_to_ini(CONFIG_FILENAME)

    def closeEvent(self, event):
        if self.profiling.isVisible():
            self.profiling.close()
        self.save_config_app()

    def on_tab_changed(self, index: int):
        pass

    def paintEvent(self, event: QPaintEvent) -> None:
        super(MainForm, self).paintEvent(event)
        if self.isVisible():
            painter = QPainter(self)
            painter.fillRect(0, 0, self.width(), self.height(), QBrush(QColor("#B3B3B3")))
