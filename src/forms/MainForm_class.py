import gc
import os
from typing import List, Optional, Sequence

from PyQt6 import QtCore
from PyQt6.QtCore import Qt, QThread, pyqtSlot, QSize, QRect, QEvent, QUrl
from PyQt6.QtGui import (QPainter, QPixmap, QIcon, QMoveEvent,
                         QShowEvent, QAction, QDragEnterEvent, QDragLeaveEvent,
                         QDropEvent, QPaintEvent, QBrush, QColor)
from PyQt6.QtWidgets import (QMainWindow, QFileDialog, QMessageBox, QMenu,
                             QWidget, QApplication, QSizeGrip, QTabWidget)

from src.ai_module.genre_classification import GenreClassifierModule
from src.ai_module.transcription import AudioLyricsModule
from src.core.audio import AudioPlayer, PlaybackController
from src.core.audio.qt_widgets import QueuePanel
from src.api.db import library_repo
from src.api.db.db_handler import create_session
from src.api.db.models import Track
from src.core.file_system import FileMetaController
from src.core.library import library_service
from src.core.library.qt_widgets import ScanProgressWidget, LibraryTabWidget
from src.core.library.scanner import ScanStats
from src.core.log_system import print_d
from src.core.log_system.profiling import ProfileDrawWidget
from src.core.point_system import Point
from src.core.qt_widgets import (PreLoaderWidget, DragFileWidget,
                                 TitleBar, SideGrip, ChatWidget)
from src.core.settings import SettingsDataObject
from src.core.settings.qt_widgets import SettingsFrame
from src.core.workers import OpenFileWorker, LibraryScanWorker
from src.enums import StateMode, PlayerState, DragFileState
from src.function_lib.math_lib import fixed_hash
from src.global_constants import (APP_TITLE, VERSION, CONFIG_FILENAME, GENRE_MODEL_PATH, AI_ENABLED,
                                  RESOURCE_ICON_DIR, CUSTOM_TITLE_BAR, DEBUG, EXPERIMENTAL_MODULES,
                                  SUPPORTED_AUDIO_EXTENSIONS)
from src.global_styles import AppColorSchemes


class MainForm(QMainWindow):
    """Application main window.

    Owns the tab bar (Library, EQ AI, Lyrics, Chat, Settings), the player panel pinned
    to the bottom, the settings object and the file opening worker. It also wires the
    modules together: the classifier drives the equalizer and the equalizer drives
    the audio streamer.

    :signals: resized (), windowStateChanged ()
    """
    resized = QtCore.pyqtSignal()
    windowStateChanged = QtCore.pyqtSignal()
    resource_dir = "resource"
    resource_icon_dir = f"{resource_dir}/2x/"
    data_dir = "data/"
    local_dir = f"{data_dir}local/"

    def __init__(self, params):
        """Build the window, the tabs and the connections between the modules.

        :param params: Startup parameters, expects size_width and size_height of the screen.
        :returns: None.
        """
        super().__init__()
        self.params: dict = params
        self.params['main_form_ref'] = self
        if CUSTOM_TITLE_BAR:
            self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint)
        self.title_bar = TitleBar(self)
        self.title_bar.setVisible(CUSTOM_TITLE_BAR)
        self.block_update: bool = False  # Suspends the heavy repaints while the window is dragged
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

        QTabBar::tab:disabled {{
            color: gray;
        }}
        """)
        self.ai_modules_tab_indexes = []  # Tabs that stay disabled until a track is open
        self.audio_player = AudioPlayer(self, self.central_widget)

        # Single source of truth for the queue and what is playing. The streamer reports
        # the end of a track and its state; the controller advances the queue and tells
        # the views which track is current.
        self.playback = PlaybackController(self)
        self.audio_player.audio_streamer.trackEnded.connect(self.playback.on_track_ended)
        self.audio_player.audio_streamer.playbackStateChanged.connect(self.playback.on_streamer_state)
        self.playback.currentTrackChanged.connect(self.on_current_track_changed)

        # The library is the single home of everything imported: the album grid and the
        # track list, with the open and add entry points that used to sit on the home page
        # Activating a tile opens the album detail page; playing is started from there
        self.library_widget = LibraryTabWidget(self, self.central_widget)
        self.last_file = self.library_widget.tracks_list  # The relocated recent-track list
        self.playback.currentTrackChanged.connect(self.last_file.set_playing_track)
        self.last_file.update_file_list()
        self.library_tab_index = self.tab_widget.addTab(self.library_widget, self.tr("Library"))

        # The queue panel overlays the right side, toggled from the player panel
        self.queue_panel = QueuePanel(self, self.central_widget)

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
        self.genre_tab_index = self.tab_widget.addTab(self.genre_widget, self.tr("EQ AI"))
        if AI_ENABLED:
            self.genre_widget.load_model()
        self.audio_player.positionChanged.connect(self.genre_widget.set_cursor_position)
        self.ai_modules_tab_indexes.append(self.genre_tab_index)

        self.transcription_module = AudioLyricsModule(self)
        self.lyrics_tab_index = self.tab_widget.addTab(self.transcription_module, self.tr("Lyrics"))
        self.audio_player.audio_streamer.progress.connect(self.transcription_module.on_position_changed)
        self.ai_modules_tab_indexes.append(self.lyrics_tab_index)

        for index in self.ai_modules_tab_indexes:
            self.tab_widget.setTabEnabled(index, False or DEBUG)

        self.chat: Optional[ChatWidget] = None
        self.chat_tab_index: Optional[int] = None
        if EXPERIMENTAL_MODULES:
            self.chat = ChatWidget(mf=self)
            self.chat_tab_index = self.tab_widget.addTab(self.chat, self.tr("Chat"))
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

        # region library scan
        # The strip and the worker are wired once. Unlike the open worker the thread is
        # only started and stopped, so started() must not be reconnected on every run.
        self.scan_progress = ScanProgressWidget(self.central_widget)
        self.scan_progress.visibilityChanged.connect(self.recalculate_size)

        self.scan_thread = QThread(self)
        self.scan_worker = LibraryScanWorker()
        self.scan_worker.moveToThread(self.scan_thread)
        self.scan_thread.started.connect(self.scan_worker.run)
        self.scan_worker.progress.connect(self.scan_progress.set_progress)
        self.scan_worker.finished.connect(self.on_scan_finished)
        self.scan_worker.failed.connect(self.on_scan_failed)
        self.scan_progress.cancelRequested.connect(self.scan_worker.cancel)
        # endregion

        self.settings_widget = SettingsFrame(mf=self)
        self.settings_tab_index = self.tab_widget.addTab(self.settings_widget, self.tr("Settings"))

        # EQ sliders feed the streamer gains, saved presets feed the auto EQ of the classifier
        self.genre_widget.eq.slidersValueChange.connect(self.audio_player.set_eq_gains)
        self.genre_widget.eq.activeSwitched.connect(self.audio_player.audio_streamer.set_eq_active)
        self.audio_player.audio_streamer.bands = self.genre_widget.eq.bands
        self.genre_widget.genre_eq = self.settings_widget.eq_settings.load_preset_from_file()
        self.settings_widget.eq_settings.onPresetChanged.connect(self.genre_widget.on_preset_changed)

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
        """Restore the window geometry from the settings, keeping it on a real screen.

        :returns: None.
        """
        if self.settings.system_settings.form_position == Point(-1, -1):
            self.settings.system_settings.form_position.x = self.screen_width / 2 - self.settings.system_settings.form_width / 2
            self.settings.system_settings.form_position.y = self.screen_height / 2 - self.settings.system_settings.form_height / 2
        # Pull the window back when the monitor it was left on is gone
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
        """Place the resize grips along the window edges and corners.

        :returns: None.
        """
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
        """Build the File, Edit and Tools menus.

        :returns: None.
        """
        if CUSTOM_TITLE_BAR:
            menu_bar = self.title_bar.menu_bar
        else:
            menu_bar = self.menuBar()
        self.file_menu = QMenu("", self)
        self.edit_menu = QMenu("", self)
        self.tools_menu = QMenu("", self)

        # region FileMenu
        self.open_file_action = QAction("", self)
        self.open_file_action.triggered.connect(lambda: self.add_file_dialog())
        icon = QPixmap(RESOURCE_ICON_DIR + "audio_file_FILL0_wght400_GRAD0_opsz24.png")
        self.open_file_action.setIcon(QIcon(icon))

        self.add_folder_action = QAction("", self)
        self.add_folder_action.triggered.connect(lambda: self.add_folder_dialog())

        self.player_action = QAction("", self)

        # Opens the library tab, the home page it used to open is gone
        self.library_action = QAction("", self)
        icon = QPixmap(RESOURCE_ICON_DIR + "home_FILL0_wght400_GRAD0_opsz24.png")
        self.library_action.setIcon(QIcon(icon))
        self.library_action.triggered.connect(self.show_library_tab)

        self.exit_action = QAction("", self)
        self.exit_action.triggered.connect(lambda: self.close())

        self.file_menu.addAction(self.open_file_action)
        self.file_menu.addAction(self.add_folder_action)
        self.file_menu.addAction(self.player_action)
        self.file_menu.addAction(self.library_action)
        self.file_menu.addSeparator()
        self.file_menu.addAction(self.exit_action)
        # endregion

        # region EditMenu
        self.edit_menu.addAction(QAction("", self))
        # endregion

        # region ToolsMenu
        self.profiling_action = QAction("", self)
        self.profiling_action.triggered.connect(lambda: self.profiling.show())

        self.tools_menu.addAction(self.profiling_action)
        # endregion

        menu_bar.addMenu(self.file_menu)
        menu_bar.addMenu(self.edit_menu)
        menu_bar.addMenu(self.tools_menu)
        self.retranslate_menu_bars()

    def retranslate_menu_bars(self) -> None:
        """Apply the current translation to the menus and their actions.

        :returns: None.
        """
        self.file_menu.setTitle(self.tr("&File"))
        self.edit_menu.setTitle(self.tr("&Edit"))
        self.tools_menu.setTitle(self.tr("&Tools"))
        self.open_file_action.setText(self.tr("Open file"))
        self.add_folder_action.setText(self.tr("Add folder to the library"))
        self.player_action.setText(self.tr("Open player"))
        self.library_action.setText(self.tr("Library"))
        self.exit_action.setText(self.tr("Exit"))
        self.profiling_action.setText(self.tr("Profiling"))

    def changeEvent(self, event: QEvent) -> None:
        """Reapply the texts when the application language changes.

        :param event: Qt event.
        :returns: None.
        """
        if event.type() == QEvent.Type.LanguageChange:
            self.retranslate_ui()
        super().changeEvent(event)

    def retranslate_ui(self) -> None:
        """Apply the current translation to the menus and the tab captions.

        :returns: None.
        """
        self.retranslate_menu_bars()
        self.tab_widget.setTabText(self.library_tab_index, self.tr("Library"))
        self.tab_widget.setTabText(self.genre_tab_index, self.tr("EQ AI"))
        self.tab_widget.setTabText(self.lyrics_tab_index, self.tr("Lyrics"))
        if self.chat_tab_index is not None:
            self.tab_widget.setTabText(self.chat_tab_index, self.tr("Chat"))
        self.tab_widget.setTabText(self.settings_tab_index, self.tr("Settings"))

    def showEvent(self, event: QShowEvent) -> None:
        """Handle the window becoming visible.

        :param event: Qt show event.
        :returns: None.
        """
        pass

    def moveEvent(self, event: QMoveEvent) -> None:
        """Remember the window position for the next start.

        :param event: Qt move event.
        :returns: None.
        """
        if self.windowState() is not Qt.WindowState.WindowMaximized:
            self.settings.system_settings.form_position.x = event.pos().x()
            self.settings.system_settings.form_position.y = event.pos().y()

    def resizeEvent(self, event):
        """Relayout the widgets and the resize grips.

        :param event: Qt resize event.
        :returns: None.
        """
        self.resized.emit()
        super(MainForm, self).resizeEvent(event)
        self.update_grips()

    @pyqtSlot()
    def window_state_changed(self) -> None:
        """Hide the resize grips while the window is maximized.

        :returns: None.
        """
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

    @staticmethod
    def urls_to_paths(urls: Sequence[QUrl]) -> List[str]:
        """Turn dropped urls into local paths.

        toLocalFile is used rather than trimming the leading slash off path(), because
        that trick mangles a network share and leaves percent escapes in a name with
        spaces or Cyrillic characters.

        :param urls: Urls carried by the drop.
        :returns: List[str] - Local paths, in the order they were dropped.
        """
        paths: List[str] = []
        for url in urls:
            if not url.isLocalFile():
                continue
            local = url.toLocalFile()
            if local:
                paths.append(local)
        return paths

    @staticmethod
    def is_supported_audio(path: str) -> bool:
        """Whether a file is one the player can open.

        :param path: Path to check.
        :returns: bool - True for a supported audio file.
        """
        return os.path.splitext(path)[1].lower() in SUPPORTED_AUDIO_EXTENSIONS

    def dragEnterEvent(self, event: QDragEnterEvent):
        """Show the drop overlay and validate what is being dragged.

        A drop is accepted when it carries at least one folder or one supported audio
        file, so a whole music collection can be dropped on the window at once.

        :param event: Qt drag enter event.
        :returns: None.
        """
        if self.audio_player.position_slider.loading_mode or not event.mimeData().hasUrls():
            event.ignore()
            self.drag_widget.setVisible(False)
            return

        paths = self.urls_to_paths(event.mimeData().urls())
        acceptable = any(os.path.isdir(path) or self.is_supported_audio(path) for path in paths)
        self.drag_widget.set_state(DragFileState.CORRECT if acceptable else DragFileState.INCORRECT)
        self.drag_widget.setVisible(True)
        event.setDropAction(Qt.DropAction.CopyAction)
        event.accept()

    def dropEvent(self, event: QDropEvent) -> None:
        """Add everything that was dropped to the library.

        :param event: Qt drop event.
        :returns: None.
        """
        self.drag_widget.setVisible(False)
        if not event.mimeData().hasUrls() or self.drag_widget.state is not DragFileState.CORRECT:
            event.ignore()
            return
        event.setDropAction(Qt.DropAction.CopyAction)
        event.accept()
        self.add_paths(self.urls_to_paths(event.mimeData().urls()))

    def dragLeaveEvent(self, event: QDragLeaveEvent) -> None:
        """Hide the drop overlay.

        :param event: Qt drag leave event.
        :returns: None.
        """
        self.drag_widget.setVisible(False)

    @pyqtSlot()
    def recalculate_size(self) -> None:
        """Recompute the size and position of the title bar, tabs, player and overlays.

        :returns: None.
        """
        preloader_size: QSize = self.size()

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

        # The player is pinned to the bottom, the scan strip sits above it while a scan
        # runs, and the tabs take whatever is left
        self.audio_player.resize(self.central_widget.width(), self.audio_player.height())
        self.audio_player.move(0, self.central_widget.height() - self.audio_player.height())

        scan_height: int = self.scan_progress.height() if self.scan_progress.isVisible() else 0
        self.scan_progress.resize(self.central_widget.width(), self.scan_progress.height())
        self.scan_progress.move(0, self.central_widget.height()
                                - self.audio_player.height() - scan_height)

        self.tab_widget.resize(self.central_widget.width(),
                               self.central_widget.height() - self.audio_player.height() - scan_height)

        # The queue panel overlays the right of the tab area, above the player
        queue_width = min(340, self.central_widget.width() // 2)
        self.queue_panel.resize(queue_width, self.tab_widget.height())
        self.queue_panel.move(self.central_widget.width() - queue_width, 0)
        self.queue_panel.raise_()

        self.drag_widget.resize(self.size())

    def show_preloader(self) -> None:
        """Show the fullscreen preloader overlay.

        :returns: None.
        """
        self.preloader.setVisible(True)
        self.recalculate_size()

    def show_error_message_log(self, title: str, text: str) -> None:
        """Show a modal error dialog centred on the window.

        :param title: Dialog title.
        :param text: Message text.
        :returns: None.
        """
        error_msg = QMessageBox()
        error_msg.setText(text)
        error_msg.setIcon(QMessageBox.Icon.Critical)
        error_msg.setWindowTitle(title)
        error_msg.move(self.frameGeometry().center() - QtCore.QRect(QtCore.QPoint(), error_msg.sizeHint()).center())
        error_msg.setStandardButtons(QMessageBox.StandardButton.Ok)
        error_msg.exec()

    def load_ann_models(self) -> None:
        """Hook for loading the neural network models after the window is created.

        :returns: None.
        """
        pass

    def reset_open_workers(self) -> None:
        """Recreate the file opening worker and stop its thread.

        :returns: None.
        """
        self.worker = OpenFileWorker()
        self.worker.mf = self
        self.worker.finished.connect(self.open_finished)
        self.worker.preloader_signal.connect(self.preloader.set_help_text)

        self.work_thread.exit(0)
        self.work_thread.wait()

    def add_file_dialog(self) -> None:
        """Ask for audio files and add them to the library.

        :returns: None.
        """
        all_formats = " ".join(f"*{extension}" for extension in SUPPORTED_AUDIO_EXTENSIONS)
        dialog_filter = (f"{self.tr('All audio formats')} ({all_formats});;"
                         f"MP3 (*.mp3);;FLAC (*.flac);;WAVE (*.wave *.wav);;"
                         f"{self.tr('All files')} (*.*)")
        filenames = QFileDialog.getOpenFileNames(self, self.tr("Open file"),
                                                 self.settings.system_settings.last_folder,
                                                 dialog_filter)[0]
        if filenames:
            self.settings.system_settings.last_folder = os.path.dirname(filenames[0])
            self.add_paths(filenames)

    def add_folder_dialog(self) -> None:
        """Ask for a folder and import everything under it.

        :returns: None.
        """
        folder = QFileDialog.getExistingDirectory(self, self.tr("Add folder to the library"),
                                                  self.settings.system_settings.last_folder)
        if folder:
            self.settings.system_settings.last_folder = folder
            self.add_paths([folder])

    def add_paths(self, paths: Sequence[str]) -> None:
        """Add any mix of files and folders to the library.

        Everything, even a single file, goes through the scanner so it gets its album,
        artist and cover the same way a folder import does. Registering a single file on
        its own used to skip that, leaving the track with no album and invisible in the
        album view.

        :param paths: Files and folders to add.
        :returns: None.
        """
        folders = [path for path in paths if os.path.isdir(path)]
        files = [path for path in paths if os.path.isfile(path) and self.is_supported_audio(path)]
        if not folders and not files:
            return
        self.start_library_scan(folders + files)

    def start_library_scan(self, paths: Sequence[str]) -> None:
        """Import paths in the background.

        :param paths: Files and folders to import.
        :returns: None.
        """
        if self.scan_thread.isRunning():
            self.show_error_message_log(self.tr("Library"),
                                        self.tr("A scan is already running, wait for it to finish"))
            return
        self.scan_thread.wait()  # The previous run may still be shutting down
        self.scan_worker.set_paths(paths)
        self.scan_progress.start()
        self.scan_thread.start()

    @pyqtSlot(object)
    def on_scan_finished(self, stats: ScanStats) -> None:
        """Show what the scan did and refresh the views that read the library.

        :param stats: Result reported by the scanner.
        :returns: None.
        """
        self.scan_thread.quit()
        if stats.cancelled:
            summary = self.tr("Scan cancelled, {0} tracks added").format(stats.tracks_added)
        else:
            summary = self.tr("{0} tracks added, {1} updated, {2} albums").format(
                stats.tracks_added, stats.tracks_updated, stats.albums_added)
        self.scan_progress.finish(summary)
        if stats.changed:
            self.library_widget.reload()  # Refreshes both the album grid and the track list

    @pyqtSlot(str)
    def on_scan_failed(self, message: str) -> None:
        """Report a scan that could not run.

        :param message: Error text.
        :returns: None.
        """
        self.scan_thread.quit()
        self.scan_progress.finish(self.tr("Scan failed"))
        self.show_error_message_log(self.tr("Library"), message)

    def delete_tracks_from_library(self, track_ids: Sequence[int]) -> None:
        """Remove tracks from the library and refresh every view that showed them.

        The entry point every view deletes through. The audio files stay on disk.

        :param track_ids: Tracks to remove.
        :returns: None.
        """
        ids = list(track_ids)
        if not ids:
            return
        result = library_service.delete_tracks(ids, self.file_meta_controller)
        self.playback.purge_tracks(result.track_ids)
        self.library_widget.reload()

    def delete_album_from_library(self, album_id: int) -> None:
        """Remove an album and every track on it, after asking.

        :param album_id: Album id.
        :returns: None.
        """
        session = create_session()
        try:
            album = library_repo.get_album(session, album_id)
        finally:
            session.close()
        if album is None:
            return
        if not self.confirm_album_delete(album.title, album.track_count or 0):
            return
        result = library_service.delete_album(album_id, self.file_meta_controller)
        self.playback.purge_tracks(result.track_ids)
        self.library_widget.reload()

    def confirm_album_delete(self, title: str, track_count: int) -> bool:
        """Ask before removing a whole album.

        :param title: Album title, named in the question.
        :param track_count: Number of tracks that go with it.
        :returns: bool - True when the user confirmed.
        """
        question = QMessageBox()
        question.setWindowTitle(self.tr("Remove album"))
        question.setIcon(QMessageBox.Icon.Question)
        question.setText(self.tr('Remove "{0}" from the library?').format(title))
        question.setInformativeText(
            self.tr("%n track(s) will be removed. The files stay on disk.", "", track_count))
        question.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        question.setDefaultButton(QMessageBox.StandardButton.No)
        question.move(self.frameGeometry().center() - QtCore.QRect(QtCore.QPoint(), question.sizeHint()).center())
        return question.exec() == QMessageBox.StandardButton.Yes

    @pyqtSlot(int)
    def play_album(self, album_id: int) -> None:
        """Play an album picked in the library.

        The whole album becomes the play queue, so it plays through and next and
        previous walk it. The controller starts at the first track whose file exists.

        :param album_id: Album id.
        :returns: None.
        """
        session = create_session()
        try:
            track_ids = library_repo.get_album_track_ids(session, album_id)
        finally:
            session.close()
        if not track_ids:
            self.show_error_message_log(self.tr("Library"),
                                        self.tr("No playable file in this album"))
            return
        self.playback.play_context(track_ids, 0)

    def enqueue_album(self, album_id: int) -> None:
        """Add every track of an album to the end of the play queue.

        :param album_id: Album id.
        :returns: None.
        """
        session = create_session()
        try:
            track_ids = library_repo.get_album_track_ids(session, album_id)
        finally:
            session.close()
        self.playback.enqueue(track_ids)

    def open_current_album(self) -> None:
        """Open the album of the playing track in the library tab, from the player cover.

        :returns: None.
        """
        track_id = self.playback.current_track_id
        if track_id < 0:
            return
        session = create_session()
        try:
            album_id, _ = library_repo.get_track_nav_ids(session, track_id)
        finally:
            session.close()
        if album_id is None:
            return
        self.tab_widget.setCurrentIndex(self.library_tab_index)
        self.library_widget.open_album(album_id)

    def open_current_artist(self) -> None:
        """Open the artist of the playing track in the library tab, from the player name.

        :returns: None.
        """
        track_id = self.playback.current_track_id
        if track_id < 0:
            return
        session = create_session()
        try:
            _, artist_id = library_repo.get_track_nav_ids(session, track_id)
        finally:
            session.close()
        if artist_id is None:
            return
        self.tab_widget.setCurrentIndex(self.library_tab_index)
        self.library_widget.open_artist(artist_id)

    @pyqtSlot(int)
    def on_current_track_changed(self, track_id: int) -> None:
        """Stamp the track as opened and move the playing marker.

        Driven by the controller, so a track started from anywhere, including an
        autoplay to the next one, updates the list the same way.

        :param track_id: Id of the track now playing.
        :returns: None.
        """
        self.last_file.update_track_last_opened(track_id)

    def open_file(self, file_path, track_id: int = 6) -> None:
        """Start opening a track: show the meta and cover, then decode in the worker thread.

        :param file_path: Path to the audio file.
        :param track_id: Track id in the database.
        :returns: None.
        """
        if not os.path.exists(file_path):
            self.show_error_message_log(self.tr("File open error"), self.tr("File not found, it may have been deleted"))
            return
        # Ignore a second open while one is still decoding. open_file blocks on
        # work_thread.wait() before it starts, so re-entering while the thread runs
        # would freeze the interface until the first decode finished.
        if self.work_thread.isRunning():
            print_d("Open ignored, a file is still being decoded")
            return
        self.audio_player.start_position_loading()

        # Tracks imported by the scanner have no registry folder, their tags live in the
        # database. Fill the registry for the track actually being opened, which is what
        # the player panel, the cover and the lyrics read from.
        meta = self.file_meta_controller.get_track_meta(track_id)
        if meta is None:
            meta = self.file_meta_controller.read_track_file(file_path)
            if meta is not None:
                self.file_meta_controller.save_meta_in_registry(track_id)

        if not self.audio_player.prepare_to_open_file(file_path, meta):
            self.show_error_message_log(self.tr("File open error"), self.tr("Unable to open the file"))
            self.audio_player.stop_position_loading()
            return
        cover = self.file_meta_controller.get_preview_cover(track_id, file_path=file_path, meta=meta)
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
        try:
            self.work_thread.started.disconnect()  # Drop stale worker connections, decode this file only
        except TypeError:
            pass
        self.work_thread.started.connect(self.worker.run)
        print_d(f"RUN Thread {track_id}")
        self.work_thread.wait()
        self.work_thread.start()

    def open_finished(self, path: Optional[str]) -> None:
        """Finish opening a track: start playback, refresh the graph and the AI tabs.

        :param path: Path of the opened file, empty when decoding failed.
        :returns: None.
        """
        self.reset_open_workers()
        self.drag_widget.setVisible(False)
        if not path:
            self.show_error_message_log(self.tr("File open error"), self.tr("Unable to open the file"))
            self.audio_player.stop_position_loading()
            return
        self.last_file.update_file_list()

        self.audio_player.stop_position_loading()
        self.audio_player.play_music()
        self.settings.system_settings.open_filename = path
        self.save_config_app()
        gc.collect()  # The previous waveform can be hundreds of megabytes
        self.audio_player.audio_graph.calculate_render_lines(forcedly=True)
        self.genre_widget.reset_result()

        # Lyrics come from the registry first, then from the file tags
        self.transcription_module.clear()
        transcription = self.file_meta_controller.get_track_transcription(self.audio_player.playable_track_id)
        if transcription is not None:
            self.transcription_module.set_transcription_data(transcription)
        else:
            transcription = self.transcription_module.get_lyrics_from_file()
            if transcription and transcription.get('segments', []):
                self.transcription_module.set_transcription_data(transcription)
        for index in self.ai_modules_tab_indexes:
            self.tab_widget.setTabEnabled(index, True)

    def get_current_lyrics(self) -> Optional[str]:
        """Read the lyrics of the currently opened track from its tags.

        :returns: str - Lyrics text, None when there are none.
        """
        track_id = self.audio_player.playable_track_id
        return self.file_meta_controller.get_lyrics(track_id)

    def save_config_app(self) -> None:
        """Write the current settings to the ini file.

        :returns: None.
        """
        self.settings.player_settings.volume = self.audio_player.volume_slider.value
        self.settings.save_to_ini(CONFIG_FILENAME)

    def closeEvent(self, event):
        """Close the profiler window and persist the settings.

        :param event: Qt close event.
        :returns: None.
        """
        if self.profiling.isVisible():
            self.profiling.close()
        if self.scan_thread.isRunning():
            # The scan stops after the current chunk, everything it wrote is committed
            self.scan_worker.cancel()
            self.scan_thread.quit()
            self.scan_thread.wait(5000)
        self.library_widget.shutdown()  # Stop the cover loader threads
        self.save_config_app()

    def on_tab_changed(self, index: int):
        """React to a tab switch.

        :param index: New tab index.
        :returns: None.
        """
        pass

    @pyqtSlot()
    def show_library_tab(self) -> None:
        """Bring the library tab to the front.

        :returns: None.
        """
        self.tab_widget.setCurrentIndex(self.library_tab_index)

    def paintEvent(self, event: QPaintEvent) -> None:
        """Fill the window background.

        :param event: Qt paint event.
        :returns: None.
        """
        super(MainForm, self).paintEvent(event)
        if self.isVisible():
            painter = QPainter(self)
            painter.fillRect(0, 0, self.width(), self.height(), QBrush(QColor("#B3B3B3")))