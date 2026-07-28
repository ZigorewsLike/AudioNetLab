import os
import time
from datetime import datetime
from typing import TYPE_CHECKING, Union, Optional, List, Dict, Any

import librosa
import numpy as np
import pyaudio
from PyQt6 import QtCore
from PyQt6.QtCore import Qt, QPoint, QRect, QRectF, pyqtSlot, QSize, QPropertyAnimation, QEasingCurve, QThread
from PyQt6.QtGui import (QPainter, QFont, QPaintEvent, QColor, QResizeEvent, QIcon, QShowEvent, QImage,
                         QMouseEvent, QPainterPath)
from PyQt6.QtWidgets import QWidget, QLabel, QPushButton

from src.core.log_system import print_d
from src.core.qt_widgets import SimpleSlider, MetaListItem, MetaListWidget
from src.core.render.graphics_system import GraphPanelAudio
from src.enums import PlayerState
from src.global_constants import PROFILE
from .AudioStreamer_class import AudioStreamer

if TYPE_CHECKING:
    from src.forms import MainForm


class AudioPlayer(QWidget):
    """Player panel: transport controls, waveform graph, track meta and the AudioStreamer thread.

    :signals: positionChanged (float) - relative playback position in the range 0..1
    """
    positionChanged = QtCore.pyqtSignal(float)

    def __init__(self, mf, *args, **kwargs):
        """Build the player UI and start the streaming thread.

        :param mf: Main form reference.
        :returns: None.
        """
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

        self.resize(400, 135)
        self.image_size: int = 25
        self.player_state: PlayerState = PlayerState.NONE
        self.graph_visible: bool = True
        self.meta_visible: bool = False
        self.mute_audio: bool = False

        self.waveform: Optional[np.ndarray] = None
        self.sample_rate: Optional[int] = None
        self.playable_track_id: Optional[int] = None
        self.playable_file_file: Optional[str] = None

        self.pyaudio_port: Optional[pyaudio.PyAudio] = pyaudio.PyAudio()
        self.pyaudio_stream: Optional[pyaudio.Stream] = None
        self.audio_streamer: AudioStreamer = AudioStreamer()
        self.audio_thread: QThread = QThread()

        self.setMouseTracking(True)

        self.track_meta: Optional[Dict[str, Any]] = None

        # region UI
        self.title_tack = QLabel("", self)
        self.title_tack.setStyleSheet("""
        QLabel{
            color: black;
        }
        """)
        font = QFont("Arima")
        font.setPointSize(13)
        font.setBold(True)
        self.title_tack.setFont(font)

        self.author_tack = QLabel("", self)
        self.author_tack.setStyleSheet("""
        QLabel{
            color: black;
        }
        """)
        font = QFont("Arima")
        font.setPointSize(9)
        font.setBold(False)
        self.author_tack.setFont(font)
        # Clicks fall through to the panel, which routes them to the artist page
        self.author_tack.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        self.play_button = QPushButton("", self)
        self.play_button.clicked.connect(self.play_button_click)
        self.play_button.resize(self.image_size, self.image_size)
        self.play_button.setIconSize(QSize(25, 25))
        self.play_button.setObjectName("PlayerButtons")

        self.prev_button = QPushButton("", self)
        self.prev_button.setObjectName("PlayerButtons")
        self.prev_button.resize(22, 22)
        self.prev_button.setIcon(QIcon('res/icons/skip_previous.png'))
        self.prev_button.setIconSize(QSize(22, 22))
        self.prev_button.clicked.connect(lambda: self.mf.playback.play_prev())

        self.next_button = QPushButton("", self)
        self.next_button.setObjectName("PlayerButtons")
        self.next_button.resize(22, 22)
        self.next_button.setIcon(QIcon('res/icons/skip_next.png'))
        self.next_button.setIconSize(QSize(22, 22))
        self.next_button.clicked.connect(lambda: self.mf.playback.play_next())

        self.queue_button = QPushButton("", self)
        self.queue_button.setObjectName("PlayerButtons")
        self.queue_button.resize(22, 20)
        self.queue_button.setIcon(QIcon('res/icons/queue_music.png'))
        self.queue_button.setIconSize(QSize(22, 20))
        self.queue_button.clicked.connect(lambda: self.mf.queue_panel.toggle())

        self.track_meta_image_bytes: Optional[bytes] = None
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
        self.graph_visible_button.clicked.connect(self.switch_graph_visible)
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

        # The streaming loop must not be starved by the UI thread
        self.audio_streamer.start(QThread.Priority.TimeCriticalPriority)
        self.change_play_icon()

        self.meta_list = MetaListWidget(self.parent())
        self.meta_list.move(self.width(), 0)
        self.meta_list.resize(300, 300)

        self.meta_show_anim = QPropertyAnimation(self.meta_list, b"pos")
        self.meta_show_anim.setDuration(200)

        self.set_graph_visible(False)
        self.set_default_track_cover()

    def paintEvent(self, event: QPaintEvent) -> None:
        """Draw the panel background and the rounded track cover.

        :param event: Qt paint event.
        :returns: None.
        """
        super().paintEvent(event)
        start_time = time.time()
        painter = QPainter(self)

        painter.fillRect(0, 0, self.width() - 1, self.height() - 1, QColor("#B3B3B3"))

        path = QPainterPath()
        path.addRoundedRect(QRectF(20, self.height() - 50 - 10, 50, 50), 15, 15)
        painter.fillPath(path, QColor(255, 255, 255, 255))
        painter.drawImage(20, self.height() - 50 - 10, self.track_meta_image_drawable)

        if PROFILE:
            self.mf.profiling.add_draw_time("AudioPlayer", time.time() - start_time)

    def _cover_rect(self) -> QRect:
        """Rect of the painted track cover, the clickable area that opens the album.

        :returns: QRect - Cover rect in panel coordinates.
        """
        return QRect(20, self.height() - 50 - 10, 50, 50)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Open the album from the cover and the artist page from the name.

        :param event: Qt mouse event.
        :returns: None.
        """
        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.position().toPoint()
            if self._cover_rect().contains(pos):
                self.mf.open_current_album()
                return
            if self.author_tack.geometry().contains(pos):
                self.mf.open_current_artist()
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        """Show the hand cursor over the cover and the artist name.

        :param event: Qt mouse event.
        :returns: None.
        """
        pos = event.position().toPoint()
        over_link = self._cover_rect().contains(pos) or self.author_tack.geometry().contains(pos)
        self.setCursor(Qt.CursorShape.PointingHandCursor if over_link else Qt.CursorShape.ArrowCursor)
        super().mouseMoveEvent(event)

    def showEvent(self, event: QShowEvent) -> None:
        """Lay out the child widgets when the panel becomes visible.

        :param event: Qt show event.
        :returns: None.
        """
        super().showEvent(event)
        self.recalc_sizes()

    def resizeEvent(self, event: QResizeEvent) -> None:
        """Lay out the child widgets on resize.

        :param event: Qt resize event.
        :returns: None.
        """
        super().resizeEvent(event)
        if self.isVisible():
            self.recalc_sizes()

    def __del__(self) -> None:
        """Release the audio port together with the widget.

        :returns: None.
        """
        self.audio_streamer.close_audio_port()

    def recalc_sizes(self) -> None:
        """Reposition every child widget relative to the current panel size.

        :returns: None.
        """
        self.title_tack.move(80, self.height() - 35 - 21)
        self.author_tack.move(80, self.height() - 35)
        self.play_button.move(round(self.width() / 2 - self.play_button.width() / 2),
                              self.height() - 22 - self.play_button.height())
        # Previous and next flank the play button, vertically centred on it
        button_y = self.play_button.y() + (self.play_button.height() - self.prev_button.height()) // 2
        self.prev_button.move(self.play_button.x() - self.prev_button.width() - 14, button_y)
        self.next_button.move(self.play_button.x() + self.play_button.width() + 14, button_y)

        self.position_slider.resize(self.width() - 40, 16)

        self.audio_graph.resize(self.width() - 40, 120)
        if self.graph_visible:
            self.position_slider.move(20, 20 + self.audio_graph.height())
        else:
            self.position_slider.move(20, 10)

        if self.meta_visible:
            self.meta_list.move(self.width() - self.meta_list.width(),
                                self.mf.central_widget.height() - self.meta_list.height() - 52)
        else:
            self.meta_list.move(self.width(),
                                self.mf.central_widget.height() - self.meta_list.height() - 52)

        self.graph_visible_button.move(self.width() - self.graph_visible_button.width() - 30,
                                       self.height() - self.graph_visible_button.height() - 25)
        self.meta_visible_button.move(self.graph_visible_button.x() - 20 - self.meta_visible_button.width(),
                                      self.graph_visible_button.y())
        self.queue_button.move(self.meta_visible_button.x() - 20 - self.queue_button.width(),
                               self.meta_visible_button.y())
        self.mute_volume_button.move(self.queue_button.x() - 20 - self.mute_volume_button.width(),
                                     self.queue_button.y())
        self.volume_slider.move(self.mute_volume_button.x() - self.volume_slider.width() - 20,
                                self.height() - self.volume_slider.height() - 24)

        self.label_duration_right.move(self.width() - self.label_duration_right.width() - 20 - 5,
                                       self.position_slider.y() + 1)
        self.label_duration_left.move(25, self.position_slider.y() + 1)

        self.update()

    def change_play_icon(self) -> None:
        """Switch the transport button icon to match the player state.

        :returns: None.
        """
        if self.player_state is PlayerState.PLAY:
            self.play_button.setIcon(QIcon('res/icons/player_pause_icon_black.png'))
        else:
            self.play_button.setIcon(QIcon('res/icons/player_play_icon_black.png'))
        self.update()

    @pyqtSlot()
    def play_button_click(self) -> None:
        """Toggle playback from the transport button.

        :returns: None.
        """
        if self.player_state is PlayerState.WAIT or self.player_state is PlayerState.PAUSE:
            self.play_music()
        elif self.player_state is PlayerState.PLAY:
            self.pause_music()

    def set_graph_visible(self, visible: bool) -> None:
        """Show or hide the waveform graph and resize the panel accordingly.

        :param visible: True shows the graph.
        :returns: None.
        """
        if visible:
            self.audio_graph.setVisible(True)
            self.audio_graph.calculate_render_lines(forcedly=True)
            self.resize(self.width(), self.height() + self.audio_graph.height() + 10)
        else:
            self.audio_graph.setVisible(False)
            self.resize(self.width(), self.height() - self.audio_graph.height() - 10)
        self.graph_visible = visible

    @pyqtSlot()
    def switch_graph_visible(self) -> None:
        """Invert the graph visibility and store it in the settings.

        :returns: None.
        """
        self.graph_visible = not self.graph_visible
        self.set_graph_visible(self.graph_visible)
        self.mf.settings.player_settings.graph_visible = self.graph_visible
        self.mf.resized.emit()

    @pyqtSlot()
    def switch_visible_meta(self) -> None:
        """Slide the track meta list in or out.

        :returns: None.
        """
        self.meta_visible = not self.meta_visible
        self.meta_show_anim.stop()
        if self.meta_visible:
            self.meta_show_anim.setEndValue(QPoint(self.width() - self.meta_list.width(),
                                                   self.meta_list.y()))
            self.meta_show_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        else:
            self.meta_show_anim.setEndValue(QPoint(self.width(),
                                                   self.meta_list.y()))
            self.meta_show_anim.setEasingCurve(QEasingCurve.Type.InCubic)
        self.meta_show_anim.start()

    @pyqtSlot()
    def switch_mute_audio(self) -> None:
        """Mute or restore the volume kept by the slider.

        :returns: None.
        """
        self.mute_audio = not self.mute_audio
        if not self.mute_audio:
            self.mute_volume_button.setIcon(QIcon('res/icons/player_volume_icon_black.png'))
            self.set_track_volume(self.volume_slider.value)
        else:
            self.mute_volume_button.setIcon(QIcon('res/icons/player_volume_off_black_2.png'))
            self.audio_streamer.set_volume(0)

    def set_current_time(self, position: float) -> None:
        """Update the elapsed and remaining time labels around the progress slider.

        :param position: Playback position in milliseconds.
        :returns: None.
        """
        self.label_duration_left.setText(f"{datetime.strftime(datetime.fromtimestamp(position / 1000), '%M:%S')}")
        self.label_duration_left.adjustSize()
        slider_position: float = self.position_slider.width() * position / self.audio_streamer.duration()
        # Labels ride along the slider and switch colour once they overlap the filled part
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
        """Propagate the streamer progress to the slider, labels and graph.

        :param position: Playback position in milliseconds.
        :returns: None.
        """
        self.position_slider.set_value(position)
        self.set_current_time(position)

        if self.audio_streamer.duration() != 0:
            self.audio_graph.changeCursorPosition.emit(position / self.audio_streamer.duration())
            self.positionChanged.emit(position / self.audio_streamer.duration())
            if self.isVisible():
                self.audio_graph.change_scale_graph()

    @pyqtSlot(PlayerState)
    def player_state_changed(self, state: PlayerState):
        """React to the streamer state changes.

        :param state: New streamer state.
        :returns: None.
        """
        print_d(state)
        if state is PlayerState.STOP:
            self.position_slider.set_value(0)
            self.player_state = PlayerState.WAIT
            self.change_play_icon()

    # region Player methods
    def prepare_to_open_file(self, path: str, track_meta: Optional[dict]) -> bool:
        """Reset the panel and fill the title, artist and meta list before decoding.

        :param path: Path to the audio file.
        :param track_meta: Tag dictionary read from the registry, may be None.
        :returns: True when the panel is ready for the file.
        """
        self.audio_streamer.stop()
        self.meta_list.clear()
        print_d(f"Open file: {path}")

        self.track_meta_image_drawable = QImage()
        filename, file_extension = os.path.splitext(os.path.basename(path))

        if track_meta is not None:
            for key, value in track_meta.items():
                self.meta_list.add(MetaListItem(key, value))
                # print_d(key, value)
            self.meta_list.recalculate_size()
        else:
            track_meta = {}

        track_name = track_meta.get('title')
        artist_name = track_meta.get('artist')

        self.title_tack.setText(track_name[0] if track_name is not None else filename)
        self.title_tack.adjustSize()

        self.author_tack.setText(", ".join(artist_name) if artist_name is not None else self.tr("Unknown"))
        self.author_tack.adjustSize()
        return True

    def set_default_track_cover(self, icon_index: int = 0) -> None:
        """Draw one of the bundled placeholder covers.

        :param icon_index: Placeholder index in the range 0..5.
        :returns: None.
        """
        img = QImage()
        img.load(f"res/icons/track_default_cover_{icon_index + 1}.png")
        self.track_meta_image_drawable = img.scaled(50, 50, Qt.AspectRatioMode.KeepAspectRatio,
                                                    Qt.TransformationMode.SmoothTransformation)

    def set_track_cover(self, image: Optional[QImage]) -> None:
        """Show the cover extracted from the track, or a placeholder.

        :param image: Cover image, None falls back to the placeholder.
        :returns: None.
        """
        if image is not None:
            self.track_meta_image_drawable = image.scaled(50, 50, Qt.AspectRatioMode.KeepAspectRatio,
                                                          Qt.TransformationMode.SmoothTransformation)
        else:
            self.set_default_track_cover()

    def open_file(self, path) -> None:
        """Decode the file and hand the waveform over to the streamer and the graph.

        Called from the OpenFileWorker thread because decoding is slow.

        :param path: Path to the audio file.
        :returns: None.
        """
        waveform_np, sample_rate = librosa.load(path, sr=None, mono=False, dtype=np.int16)
        if waveform_np.ndim == 1:
            waveform_np = waveform_np[None, :]
        print_d(waveform_np.shape, waveform_np[0], sample_rate)
        # The graph gets a heavily decimated copy, drawing every sample is pointless
        self.audio_graph.set_data(waveform_np[0, ::sample_rate // 22050 * 10] * 1.0, calc_line=False)
        self.audio_graph.set_shift(0, 1)

        waveform_np = np.swapaxes(waveform_np, 0, 1)  # From [channels, samples] to interleaved [samples, channels]

        self.waveform = waveform_np
        self.sample_rate = sample_rate

        self.audio_streamer.init_file(waveform_np, int(sample_rate))
        print_d(self.pyaudio_port.get_default_output_device_info())
        self.audio_graph.changeCursorPosition.emit(0)

    def get_output_devices(self) -> List[Dict[str, any]]:
        """List the available output devices.

        :returns: List[Dict] - Device descriptions.
        """
        return self.audio_streamer.get_output_devices()

    def get_default_output(self) -> Dict[str, any]:
        """Describe the system default output device.

        :returns: Dict - Device description.
        """
        return self.audio_streamer.get_default_output()

    def switch_device(self, device_index: Optional[int] = None) -> bool:
        """Switch the output device, pausing playback while the stream is reopened.

        :param device_index: Target device index, system default when None.
        :returns: True on success.
        """
        if self.is_playable:
            self.pause_music()
            success = self.audio_streamer.switch_device(device_index)
            self.play_music()
        else:
            success = self.audio_streamer.switch_device(device_index)
        return success

    @pyqtSlot(float)
    def duration_is_changed(self, duration: float) -> None:
        """Rescale the progress slider for a newly loaded track.

        :param duration: Track duration in milliseconds.
        :returns: None.
        """
        self.position_slider.set_range(0, int(duration))
        self.label_duration_right.setText(f"{datetime.strftime(datetime.fromtimestamp(duration / 1000), '%M:%S')}")
        self.label_duration_right.adjustSize()

    @property
    def is_playable(self) -> bool:
        """Whether transport commands may be sent to the streamer.

        :returns: bool - False while no track is loaded or a file is still opening.
        """
        return self.player_state is not PlayerState.NONE and self.player_state is not PlayerState.OPENING

    @pyqtSlot()
    def play_music(self) -> None:
        """Start playback.

        :returns: None.
        """
        if self.is_playable:
            self.audio_streamer.play()
            self.player_state = PlayerState.PLAY
            self.change_play_icon()

    @pyqtSlot()
    def pause_music(self) -> None:
        """Pause playback.

        :returns: None.
        """
        if self.is_playable:
            self.audio_streamer.pause()
            self.player_state = PlayerState.PAUSE
            self.change_play_icon()

    @pyqtSlot()
    def stop_music(self) -> None:
        """Stop playback and rewind.

        :returns: None.
        """
        if self.is_playable:
            self.audio_streamer.stop()
            self.player_state = PlayerState.WAIT
            self.change_play_icon()

    @pyqtSlot(int)
    def set_track_position(self, value: int) -> None:
        """Seek the track from the progress slider.

        :param value: New position in milliseconds.
        :returns: None.
        """
        if self.is_playable:
            self.audio_streamer.set_position(value)
            self.set_current_time(value)
            self.positionChanged.emit(value / self.audio_streamer.duration())

    def set_log_volume(self, log_volume: bool) -> None:
        """Switch between linear and perceptual volume curves.

        :param log_volume: True enables the perceptual curve.
        :returns: None.
        """
        self.audio_streamer.log_volume = log_volume
        self.set_track_volume(self.volume_slider.value)

    @pyqtSlot(int)
    def set_track_volume(self, value: int) -> None:
        """Apply the volume slider value to the streamer.

        :param value: Slider value in the range 0..volume_slider.maximum.
        :returns: None.
        """
        if not self.mute_audio:
            self.audio_streamer.set_volume(value / self.volume_slider.maximum)

    @pyqtSlot(list)
    def set_eq_gains(self, gains: List[float]) -> None:
        """Push new EQ band gains to the streamer.

        :param gains: Linear multiplier per band.
        :returns: None.
        """
        self.audio_streamer.set_eq_gains(gains)

    def start_position_loading(self) -> None:
        """Turn the progress slider into an indeterminate loading bar.

        :returns: None.
        """
        self.position_slider.set_loading_mode(True)

    def stop_position_loading(self) -> None:
        """Return the progress slider to the normal mode.

        :returns: None.
        """
        self.position_slider.set_loading_mode(False)
    # endregion