import gc
import math
import os
import time
from copy import deepcopy
from datetime import timedelta, datetime
from gettext import find
from typing import TYPE_CHECKING, Union, Optional, List, Dict, Tuple, Any
from math import atan2, cos, sin, pi

import numpy as np
import pyaudio
import mutagen
from mutagen.flac import FLAC
from mutagen.mp3 import MP3
import librosa

from PyQt6 import QtMultimedia, QtCore
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from PyQt6.QtCore import Qt, QPoint, QRectF, QRect, QUrl, QDir, pyqtSlot, QSize, QObject, QPropertyAnimation, \
    QEasingCurve, QThread
from PyQt6.QtGui import (QPainter, QFont, QPaintEvent, QBrush, QColor, QPen, QMouseEvent, QLinearGradient, QCursor,
                         QWheelEvent, QKeyEvent, QPolygon, QDropEvent, QResizeEvent, QPixmap, QIcon, QShowEvent, QImage,
                         QRegion, QPainterPath)
from PyQt6.QtWidgets import QWidget, QMessageBox, QApplication, QLabel, QPushButton, QListWidget, QListWidgetItem, \
    QSlider

from src.core.render.graphics_system import GraphPanelAudio
from src.core.qt_widgets import SimpleSlider, MetaListItem
from src.core.log_system import print_d, print_e
from src.enums import PlayerState, StateMode
from src.global_constants import PROFILE
from .AudioStreamer_class import AudioStreamer

if TYPE_CHECKING:
    from src.forms import MainForm


class AudioPlayer(QWidget):
    positionChanged = QtCore.pyqtSignal(float)

    def __init__(self, mf, *args, **kwargs):
        super(AudioPlayer, self).__init__(*args, **kwargs)
        self.mf: Union[MainForm, QWidget] = mf
        self.setStyleSheet("""
        QPushButton#PlayerButtons{
            background-color: transparent;
            border: 0px;
        }
        QLabel#PositionLabel{
            background-color: transparent;
            border-radius: 5px;
            color: #FAFAFA;
        }
        QLabel#PositionLabelGray{
            background-color: transparent;
            border-radius: 5px;
            color: #606060;
        }
        """)
        "767676"
        "EAEAEA"

        self.resize(400, 224)
        self.image_size: int = 25
        self.player_state: PlayerState = PlayerState.NONE
        self.graph_visible: bool = True
        self.meta_visible: bool = False
        self.mute_audio: bool = False

        self.waveform: Optional[np.ndarray] = None
        self.sample_rate: Optional[int] = None

        self.pyaudio_port: Optional[pyaudio.PyAudio] = pyaudio.PyAudio()
        self.pyaudio_stream: Optional[pyaudio.Stream] = None
        self.audio_streamer: AudioStreamer = AudioStreamer()
        self.audio_thread: QThread = QThread()

        self.track_meta: Optional[Dict[str, Any]] = None

        # region UI
        self.title_tack = QLabel("Трек отрой сначала Taa", self)
        self.title_tack.setStyleSheet("""
        QLabel{
            color: black;
        }
        """)
        font = QFont("Arima")
        font.setPointSize(13)
        font.setBold(True)
        self.title_tack.setFont(font)

        self.author_tack = QLabel("Unknown", self)
        self.author_tack.setStyleSheet("""
        QLabel{
            color: black;
        }
        """)
        font = QFont("Arima")
        font.setPointSize(9)
        font.setBold(False)
        self.author_tack.setFont(font)

        # self.track_image = QPixmap(f'res/TrackImage.png')
        # self.track_image = self.track_image.scaled(self.image_size, self.image_size,
        #                                            Qt.AspectRatioMode.IgnoreAspectRatio,
        #                                            Qt.TransformationMode.SmoothTransformation)

        self.play_button = QPushButton("", self)
        self.play_button.clicked.connect(self.play_button_click)
        self.play_button.resize(self.image_size, self.image_size)
        self.play_button.setIconSize(QSize(25, 25))
        self.play_button.setObjectName("PlayerButtons")

        self.track_meta_image_bytes: Optional[bytes] = None
        self.track_meta_image = QImage()
        self.track_meta_image_drawable = QImage()

        self.position_slider = SimpleSlider(self)
        self.position_slider.set_range(0, 1)
        self.position_slider.top_bottom_margin = 0
        self.position_slider.sliderMoved.connect(self.set_track_position)
        self.position_slider.resize(self.width() - 40, 14)
        self.position_slider.slider_height = 5

        self.volume_slider = SimpleSlider(self)
        self.volume_slider.set_range(0, 1000)
        self.volume_slider.set_value(500)
        self.volume_slider.sliderMoved.connect(self.set_track_volume)
        self.volume_slider.resize(80, 13)
        self.volume_slider.slider_height = 3

        self.audio_graph = GraphPanelAudio(self.mf, self)
        self.audio_graph.move(20, 10)
        self.audio_graph.background_corner = 5
        self.audio_graph.background_corner_color = "#666666"
        self.audio_graph.background_color = "#B3B3B3"

        self.graph_visible_button = QPushButton("", self)
        self.graph_visible_button.clicked.connect(self.switch_visible_graph)
        self.graph_visible_button.resize(20, 20)
        self.graph_visible_button.setIcon(QIcon('res/icons/player_spectrogram_icon_black.png'))
        self.graph_visible_button.setObjectName("PlayerButtons")

        self.meta_visible_button = QPushButton("", self)
        self.meta_visible_button.clicked.connect(self.switch_visible_meta)
        self.meta_visible_button.resize(20, 20)
        self.meta_visible_button.setIcon(QIcon('res/icons/player_meta_icon_black.png'))
        self.meta_visible_button.setObjectName("PlayerButtons")

        self.mute_volume_button = QPushButton("", self)
        self.mute_volume_button.clicked.connect(self.switch_mute_audio)
        self.mute_volume_button.resize(22, 20)
        self.mute_volume_button.setIcon(QIcon('res/icons/player_volume_icon_black.png'))
        self.mute_volume_button.setIconSize(QSize(22, 20))
        self.mute_volume_button.setObjectName("PlayerButtons")

        self.meta_show_anim = QPropertyAnimation(self.mf.meta_list, b"pos")
        self.meta_show_anim.setDuration(200)

        font = QFont("Arima")
        font.setPointSize(9)
        font.setBold(False)

        self.label_duration_left = QLabel("00:00", self)
        self.label_duration_left.setObjectName("PositionLabelGray")
        self.label_duration_left.setFont(font)
        self.label_duration_left.adjustSize()
        self.label_duration_left.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        self.label_duration_right = QLabel("00:00", self)
        self.label_duration_right.setObjectName("PositionLabelGray")
        self.label_duration_right.setFont(font)
        self.label_duration_right.adjustSize()
        self.label_duration_right.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        # endregion

        self.audio_streamer.set_volume(50)
        self.audio_streamer.progress.connect(self.track_position_changed)
        self.audio_streamer.playbackStateChanged.connect(self.player_state_changed)
        self.audio_streamer.durationChanged.connect(self.duration_is_changed)

        self.audio_streamer.start(QThread.Priority.TimeCriticalPriority)
        # # self.player.positionChanged.connect(self.track_position_changed)
        # self.player.playbackStateChanged.connect(self.player_state_changed)
        # self.player.durationChanged.connect(self.duration_is_changed)

        self.change_play_icon()

    def paintEvent(self, event: QPaintEvent) -> None:
        super().paintEvent(event)
        start_time = time.time()
        painter = QPainter(self)

        painter.fillRect(0, 0, self.width() - 1, self.height() - 1, QColor("#B3B3B3"))

        # painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Difference)

        path = QPainterPath()
        path.addRoundedRect(QRectF(20, self.height() - 50 - 10, 50, 50), 15, 15)
        painter.fillPath(path, QColor(255, 255, 255, 255))
        painter.drawImage(20, self.height() - 50 - 10, self.track_meta_image_drawable)

        # painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Exclusion)

        # painter.fillRect(0, 0, self.width() - 1, self.height() - 1, QColor("#B3B3B3"))

        # painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
        if PROFILE:
            self.mf.profiling.add_draw_time("AudioPlayer", time.time() - start_time)

    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        self.recalc_sizes()

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        if self.isVisible():
            self.recalc_sizes()

    def __del__(self) -> None:
        self.audio_streamer.close_audio_port()

    def recalc_sizes(self) -> None:
        self.title_tack.move(80, self.height() - 35 - 21)
        self.author_tack.move(80, self.height() - 35)
        self.play_button.move(round(self.width() / 2 - self.play_button.width() / 2),
                              self.height() - 22 - self.play_button.height())

        self.position_slider.resize(self.width() - 40, 16)
        self.volume_slider.move(self.width() - self.volume_slider.width() - 142,
                                self.height() - self.volume_slider.height() - 24)

        self.audio_graph.resize(self.width() - 40, 120)
        if self.graph_visible:
            self.position_slider.move(20, 20 + self.audio_graph.height())
        else:
            self.position_slider.move(20, 10)

        self.graph_visible_button.move(self.width() - self.graph_visible_button.width() - 30,
                                       self.height() - self.graph_visible_button.height() - 25)

        self.meta_visible_button.move(self.graph_visible_button.x() - 20 - self.meta_visible_button.width(),
                                      self.graph_visible_button.y())

        self.mute_volume_button.move(self.meta_visible_button.x() - 20 - self.mute_volume_button.width(),
                                     self.meta_visible_button.y())
        self.label_duration_right.move(self.width() - self.label_duration_right.width() - 20 - 5,
                                       self.position_slider.y() + 1)
        self.label_duration_left.move(25, self.position_slider.y() + 1)

        self.update()

    def change_play_icon(self) -> None:
        if self.player_state is PlayerState.PLAY:
            self.play_button.setIcon(QIcon('res/icons/player_pause_icon_black.png'))
        else:
            self.play_button.setIcon(QIcon('res/icons/player_play_icon_black.png'))
        self.update()

    @pyqtSlot()
    def play_button_click(self) -> None:
        if self.player_state is PlayerState.WAIT or self.player_state is PlayerState.PAUSE:
            self.play_music()
        elif self.player_state is PlayerState.PLAY:
            self.pause_music()

    @pyqtSlot()
    def switch_visible_graph(self) -> None:
        self.graph_visible = not self.graph_visible
        if not self.graph_visible:
            self.resize(self.width(), self.height() - self.audio_graph.height() - 10)
            self.audio_graph.setVisible(False)
        else:
            self.resize(self.width(), self.height() + self.audio_graph.height() + 10)
            self.audio_graph.setVisible(True)
        self.mf.settings.player_settings.graph_visible = self.graph_visible
        self.mf.resized.emit()

    @pyqtSlot()
    def switch_visible_meta(self) -> None:
        self.meta_visible = not self.meta_visible
        self.meta_show_anim.stop()
        if self.meta_visible:
            self.meta_show_anim.setEndValue(QPoint(self.width() - self.mf.meta_list.width(),
                                                   self.mf.meta_list.y()))
            self.meta_show_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        else:
            self.meta_show_anim.setEndValue(QPoint(self.width(),
                                                   self.mf.meta_list.y()))
            self.meta_show_anim.setEasingCurve(QEasingCurve.Type.InCubic)
        # self.mf.meta_list.setVisible(self.meta_visible)
        self.meta_show_anim.start()

    @pyqtSlot()
    def switch_mute_audio(self) -> None:
        self.mute_audio = not self.mute_audio
        if not self.mute_audio:
            self.mute_volume_button.setIcon(QIcon('res/icons/player_volume_icon_black.png'))
            self.set_track_volume(self.volume_slider.value)
        else:
            self.mute_volume_button.setIcon(QIcon('res/icons/player_volume_off_black_2.png'))
            self.audio_streamer.set_volume(0)

    def set_current_time(self, position: float) -> None:
        self.label_duration_left.setText(f"{datetime.strftime(datetime.fromtimestamp(position / 1000), '%M:%S')}")
        self.label_duration_left.adjustSize()
        slider_position: float = self.position_slider.width() * position / self.audio_streamer.duration()
        if slider_position - 10 < self.label_duration_left.width():
            self.label_duration_left.move(int(slider_position) + 5 + self.position_slider.x(),
                                          self.label_duration_left.y())
            self.label_duration_left.setObjectName("PositionLabelGray")
        else:
            self.label_duration_left.move(5 + self.position_slider.x(), self.label_duration_left.y())
            self.label_duration_left.setObjectName("PositionLabel")

        if slider_position + 10 > self.position_slider.width() - self.label_duration_right.width():
            self.label_duration_right.move(int(slider_position) - 5 + self.position_slider.x() - self.label_duration_right.width(),
                                           self.label_duration_right.y())
            self.label_duration_right.setObjectName("PositionLabel")
        else:
            self.label_duration_right.move(self.position_slider.x() + self.position_slider.width() - self.label_duration_right.width() - 5,
                                           self.label_duration_left.y())
            self.label_duration_right.setObjectName("PositionLabelGray")
        self.label_duration_left.setStyleSheet(self.styleSheet())
        self.label_duration_right.setStyleSheet(self.styleSheet())

    @pyqtSlot(int)
    def track_position_changed(self, position: int) -> None:
        self.position_slider.set_value(position)
        self.set_current_time(position)

        if self.audio_streamer.duration() != 0:
            self.audio_graph.changeCursorPosition.emit(position / self.audio_streamer.duration())
            self.positionChanged.emit(position / self.audio_streamer.duration())
            if self.isVisible():
                self.audio_graph.change_scale_graph()

    @pyqtSlot(PlayerState)
    def player_state_changed(self, state: PlayerState):
        print_d(state)
        if state is PlayerState.STOP:
            # self.audio_streamer.stop()
            self.position_slider.set_value(0)
            self.player_state = PlayerState.WAIT
            self.change_play_icon()

    # region Player methods
    def prepare_to_open_file(self, path: str) -> bool:
        self.audio_streamer.stop()
        self.mf.meta_list.clear()
        print_d(f"Open file: {path}")

        self.track_meta_image_bytes = None
        self.track_meta_image = QImage()
        self.track_meta_image_drawable = QImage()

        # region Meta info
        filename, file_extension = os.path.splitext(os.path.basename(path))
        try:
            if file_extension.lower() == '.flac':
                audio = FLAC(path)
                self.track_meta_image_bytes = audio.pictures[0].data
                self.track_meta_image.loadFromData(self.track_meta_image_bytes)
            elif file_extension.lower() == '.mp3':
                audio = MP3(path)
                apic = audio.tags.get("APIC:", None)
                if apic:
                    self.track_meta_image_bytes = apic.data
                    self.track_meta_image.loadFromData(apic.data)
            else:
                raise ValueError
        except Exception as e:
            print_e("Meta read error", e)
            audio = mutagen.File(path)
        if audio is None:
            print_e(f'Open file error. {filename}')
            return False
        # endregion

        for key, value in audio.items():
            self.mf.meta_list.add(MetaListItem(key, value))
            print(key, value)
        self.mf.meta_list.recalculate_size()

        track_name = audio.get('title', None)
        # TODO: mp3 artist parser
        artist_name = audio.get('artist', None)

        self.title_tack.setText(track_name[0] if track_name is not None else filename)
        self.title_tack.adjustSize()

        self.author_tack.setText(", ".join(artist_name) if artist_name is not None else "Unknown")
        self.author_tack.adjustSize()

        self.track_meta_image_drawable = self.track_meta_image.scaled(50, 50, Qt.AspectRatioMode.KeepAspectRatio,
                                                                      Qt.TransformationMode.SmoothTransformation)

        return True

    def open_file_ai(self, path) -> None:
        waveform_np, sample_rate = librosa.load(path, sr=None, mono=False, dtype=np.int16)
        print_d(waveform_np.shape, waveform_np[0], sample_rate)
        self.audio_graph.set_data(waveform_np[0, ::sample_rate // 22100 * 10] * 1.0, calc_line=False)
        self.audio_graph.set_shift(0, 1)

        waveform_np = np.swapaxes(waveform_np, 0, 1)

        self.waveform = waveform_np
        self.sample_rate = sample_rate

        self.audio_streamer.init_file(waveform_np, int(sample_rate))
        print_d(self.pyaudio_port.get_default_output_device_info())

    @pyqtSlot(int)
    def duration_is_changed(self, duration: int) -> None:
        self.position_slider.set_range(0, duration)
        self.label_duration_right.setText(f"{datetime.strftime(datetime.fromtimestamp(duration / 1000), '%M:%S')}")
        self.label_duration_right.adjustSize()

    @pyqtSlot()
    def play_music(self) -> None:
        if self.mf.state is StateMode.PLAYER:
            self.audio_streamer.play()
            self.player_state = PlayerState.PLAY
            self.change_play_icon()

    @pyqtSlot()
    def pause_music(self) -> None:
        if self.mf.state is StateMode.PLAYER:
            self.audio_streamer.pause()
            self.player_state = PlayerState.PAUSE
            self.change_play_icon()

    @pyqtSlot()
    def stop_music(self) -> None:
        if self.mf.state is StateMode.PLAYER:
            self.audio_streamer.stop()
            self.player_state = PlayerState.WAIT
            self.change_play_icon()

    @pyqtSlot(int)
    def set_track_position(self, value: int) -> None:
        if self.mf.state is StateMode.PLAYER:
            self.audio_streamer.set_position(value)
            self.set_current_time(value)
            self.positionChanged.emit(value / self.audio_streamer.duration())

    @pyqtSlot(int)
    def set_track_volume(self, value: int) -> None:
        if not self.mute_audio:
            self.audio_streamer.set_volume(value / self.volume_slider.maximum)

    @pyqtSlot(list)
    def set_eq_gains(self, gains: List[int]) -> None:
        self.audio_streamer.eq_gains = gains

    # endregion
