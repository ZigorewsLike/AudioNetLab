import os
import subprocess
import sys
from datetime import datetime
from math import pi, cos
from typing import Optional, TYPE_CHECKING, Union, Dict

from PyQt6.QtCore import QRect, Qt, QSize, QTimer
from PyQt6.QtGui import QPainter, QBrush, QColor, QResizeEvent, QFont, QPixmap, QIcon, QShowEvent, QImage, QHideEvent, \
    QMouseEvent
from PyQt6.QtWidgets import QWidget, QLabel, QPushButton, QFrame, QScrollArea, QVBoxLayout, QMenu

from src.api.db.db_handler import DBHandler
from src.api.db.models import Track
from src.core.log_system import print_d
from src.function_lib.math_lib import fixed_hash
from src.global_constants import RESOURCE_ICON_DIR, PATH_TO_LAST_REGISTRY
from src.global_styles import DEFAULT_SCROLLBAR_STYLE, AppColorSchemes

if TYPE_CHECKING:
    from src.forms import MainForm


class LastFileList(QWidget):
    resource_icon_dir = "resource/2x/"

    def __init__(self, width, mf, *args, **kwargs):
        super(LastFileList, self).__init__(*args, **kwargs)

        self.widget_width = width
        self.mf: MainForm = mf

        self.item_height: int = 100
        self.playing_track_id: Optional[int] = None
        self.item_track_map: Dict[int, int] = {}

        self.setStyleSheet("""
        QLabel{
            color: white;
            background-color: transparent;
        }
        QFrame{
            background-color: """ + AppColorSchemes.FILE_LIST_BACKGROUND + """;
            border: 0px solid black;
        }
        QPushButton#openFolder{
            border: 0px solid black;
            background-color: rgba(0, 0, 0, 50);
            margin: 0px;
        }
        QPushButton#openFolder:hover{
            background-color: rgba(0, 0, 0, 80);
        }

        """ + DEFAULT_SCROLLBAR_STYLE)
        self.file_frame = QFrame()
        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidget(self.file_frame)
        self.scroll_area.move(0, 0)
        self.scroll_area.resize(width, 500)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.v_layout = QVBoxLayout(self)
        self.v_layout.setSpacing(0)
        self.v_layout.setContentsMargins(0, 0, 0, 0)

        self.file_frame.setLayout(self.v_layout)
        self.right_padding = 30

        self.file_frame.resize(width - self.right_padding, 145 * 1)
        self.db = DBHandler()

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self.widget_width = self.width()
        self.call_resize()

    def call_resize(self):
        self.scroll_area.resize(self.widget_width, self.height())
        self.file_frame.resize(self.widget_width - self.right_padding, self.item_height * (self.v_layout.count() - 1))

        for item_index in range(self.v_layout.count()):
            item = self.v_layout.itemAt(item_index)
            if item.widget() is not None:
                item.widget().resize(self.widget_width - self.right_padding, item.widget().height())

    def showEvent(self, event) -> None:
        super().showEvent(event)

    def update_file_list(self) -> None:
        self.item_track_map.clear()
        for i in reversed(range(self.v_layout.count())):
            item = self.v_layout.itemAt(i)
            if item.widget() is not None:
                item.widget().deleteLater()
            self.v_layout.removeItem(item)
        self.db.connect()
        track_list = self.db.get_all_track()
        self.db.disconnect()
        for item_index, track in enumerate(track_list):
            file_exist = os.path.exists(track.path)
            last_file = LastFileItem(track, self.mf, self, file_exist=file_exist)
            last_file.setFixedHeight(self.item_height)
            if track.id == self.playing_track_id:
                last_file.is_playing = True
            self.v_layout.addWidget(last_file)
            self.item_track_map[track.id] = item_index
        self.v_layout.addStretch()
        self.file_frame.resize(self.widget_width - self.right_padding, self.item_height * (self.v_layout.count() - 1))

    def add(self, title: str, path: str) -> Optional[int]:
        self.db.connect()
        track_id: int = self.db.add_track(title, path)
        self.db.disconnect()
        return track_id

    def delete_elem(self, item: Union[QWidget, 'LastFileItem']):
        self.v_layout.removeWidget(item)
        self.db.connect()
        self.db.delete_track(track=item.track)
        self.db.disconnect()
        self.mf.file_meta_controller.delete_track(item.track.id)
        self.update_file_list()

    def update_track_last_opened(self, track_id: int) -> None:
        self.db.connect()
        self.db.update_track_last_opened(track_id=track_id)
        self.db.disconnect()

    def get_item_by_track_id(self, track_id: int) -> Optional["LastFileItem"]:
        item_index: int = self.item_track_map.get(track_id)
        if item_index is None:
            return None
        item = self.v_layout.itemAt(item_index)
        if item:
            return item.widget()
        return None

    def item_click(self, track_id: int) -> None:
        if track_id != self.playing_track_id:
            if self.playing_track_id is not None:
                item = self.get_item_by_track_id(self.playing_track_id)
                if item:
                    item.is_playing = False
            self.playing_track_id = track_id
            item = self.get_item_by_track_id(self.playing_track_id)
            if item:
                item.is_playing = True
                self.mf.open_file(item.track.path, track_id)
                self.update_track_last_opened(track_id)


class LastFileItem(QWidget):
    def __init__(self, track_obj: Track, main_form, container, file_exist: bool = True, *args, **kwargs):
        super(LastFileItem, self).__init__(*args, **kwargs)
        self.color = 'transparent'
        self.setMouseTracking(True)

        self.track: Track = track_obj
        self.mf: MainForm = main_form
        self.container: LastFileList = container
        self.file_exist: bool = file_exist
        self.is_playing: bool = False

        self.angular_velocity: float = .05
        self.angle: float = .0
        self.timer = QTimer()
        self.timer.timeout.connect(self.rotate_wave)

        self.resize(self.width(), self.container.item_height)

        header_style: str = """
        QLabel{
            color: black;
            background-color: transparent;
        }
        """

        self.label_filename = QLabel(self.track.title, self)
        self.label_filename.setGeometry(QRect(90, 13, 300, 40))
        font = QFont("Arima")
        font.setPointSize(13)
        font.setBold(True)
        self.label_filename.setFont(font)
        self.label_filename.setStyleSheet(header_style)
        self.label_filename.adjustSize()

        self.label_date = QLabel("Посл. открытие: ", self)
        self.label_date.setGeometry(QRect(90, 44, 280, 25))
        font = QFont("Arima")
        font.setPointSize(9)
        self.label_date.setFont(font)
        self.label_date.setStyleSheet(header_style)
        self.label_date.adjustSize()

        if not file_exist:
            file_path = "File not found"
        else:
            file_path = os.path.abspath(self.track.path).replace('\\', '/')
        self.label_path = QLabel(file_path, self)
        font = QFont("Arima")
        font.setPointSize(9)
        self.label_path.setFont(font)
        self.label_path.setGeometry(QRect(90, 63, 360, 60))
        self.label_path.setStyleSheet(header_style)
        # self.label_path.setWordWrap(True)

        self.button_open_size: QSize = QSize(70, 70)

        self.button_open = QPushButton(self)
        self.button_open.setGeometry(QRect(10, 10, self.button_open_size.width(), self.button_open_size.height()))
        self.button_open.setObjectName("openFolder")
        self.button_open.clicked.connect(self.click_open_folder)

        self.right_pixmap = QPixmap(RESOURCE_ICON_DIR + "audio_wave_plane")
        self.right_plane = QLabel(self)
        self.right_plane.setPixmap(self.right_pixmap)
        self.right_plane.setStyleSheet("""
        QLabel{
            background: transparent;
        }
        """)

        self.track_meta_image: Optional[QImage] = None
        img = self.mf.file_meta_controller.get_preview_cover(track_id=self.track.id, file_path=self.track.path)
        if img is None:
            icon_index: int = fixed_hash(str(self.track.id)) % 6
            img = QImage()
            img.load(f"res/icons/track_default_cover_{icon_index + 1}.png")

        self.track_meta_image = img.scaled(self.button_open_size.width(),
                                           self.button_open_size.height(),
                                           Qt.AspectRatioMode.KeepAspectRatio,
                                           Qt.TransformationMode.SmoothTransformation)

    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        self.recalc_sizes()
        if self.is_playing:
            # self.button_open.setIcon(QIcon())
            if self.timer.isActive():
                self.timer.stop()
            self.timer.start(10)

    def hideEvent(self, event: QHideEvent) -> None:
        super().hideEvent(event)
        if self.timer.isActive():
            self.timer.stop()

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        if self.isVisible():
            self.recalc_sizes()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        super().mouseMoveEvent(event)
        if not self.file_exist:
            icon = QPixmap(os.path.join(RESOURCE_ICON_DIR, 'file_error_icon_white.png'))
            self.button_open.setIconSize(QSize(38, 35))
        else:
            icon = QPixmap(os.path.join(RESOURCE_ICON_DIR, 'play_icon_white.png'))
            self.button_open.setIconSize(QSize(30, 35))
        self.button_open.setIcon(QIcon(icon))

    def leaveEvent(self, event) -> None:
        self.button_open.setIcon(QIcon())

    def recalc_sizes(self) -> None:
        self.label_path.resize(self.width() - 20, 60)
        self.label_path.adjustSize()
        self.right_plane.move(self.width() - self.right_plane.width(), 5)

    def click_open_folder(self):
        self.container.item_click(self.track.id)

    def contextMenuEvent(self, event):
        # self.color = '#2C2A35'
        self.update()
        contextMenu = QMenu(self)
        open_folder = contextMenu.addAction("Открыть")
        show_folder = contextMenu.addAction("Показать в проводнике")
        delete_elem = contextMenu.addAction("Удалить из списка")
        action = contextMenu.exec(self.mapToGlobal(event.pos()))
        if action == open_folder:
            self.button_open.click()
        elif action == show_folder:
            path = self.track.path
            path = path.replace('/', '\\')
            if sys.platform == "win32":
                subprocess.call(f'explorer /select,"{path}"')
            else:
                subprocess.call(["open", "-R", path])
        elif action == delete_elem:
            self.container.delete_elem(self)
        self.color = 'transparent'
        self.update()

    def rotate_wave(self) -> None:
        if self.isVisible():
            self.angle += self.angular_velocity
            if self.angle >= pi * 2:
                self.angle -= pi * 2
            self.update()

    def paintEvent(self, event):
        super(LastFileItem, self).paintEvent(event)
        if self.isVisible():
            painter = QPainter(self)
            painter.fillRect(0, 0, self.width(), self.container.item_height - 10,
                             QBrush(QColor(AppColorSchemes.FILE_LIST_ITEM_BODY)))
            painter.fillRect(0, 2, self.width(), self.height(), QBrush(QColor(self.color)))

            if self.track_meta_image is not None:
                painter.drawImage(10, 10, self.track_meta_image)

            if self.is_playing:
                rect_count = 4
                rect_width = 10
                rect_shift = 5
                rect_height = self.button_open_size.height() * 0.2
                calc_rect_width: int = rect_shift + rect_width
                for i in range(0, rect_count):
                    painter.setBrush(QBrush(QColor(self.color), Qt.BrushStyle.SolidPattern))
                    painter.fillRect(
                        int(calc_rect_width * i - (rect_count * calc_rect_width / 2) + (self.button_open_size.width() / 2) + rect_shift / 2) + 10,
                        10 + self.button_open_size.height(),
                        rect_width,
                        -int(abs(cos(self.angle + i / pi * 1.2)) * rect_height),
                        QBrush(QColor("#A1FFA8"), Qt.BrushStyle.SolidPattern))


