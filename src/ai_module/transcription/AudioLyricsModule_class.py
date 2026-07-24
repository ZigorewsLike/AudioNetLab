import re
from datetime import datetime
import mimetypes
from bisect import bisect_right
from typing import TYPE_CHECKING, List, Union, Optional

import requests
from PyQt6.QtCore import Qt, pyqtSlot
from PyQt6.QtGui import QResizeEvent, QFont, QMouseEvent, QShowEvent
from PyQt6.QtWidgets import QWidget, QPushButton, QFrame, QScrollArea, QVBoxLayout, QLabel, QMenu, QComboBox, QCheckBox, \
    QSplitter

from .LyricsPropertyModule_class import TranscriptionPropertyModule
from src.global_styles import DEFAULT_SCROLLBAR_STYLE
from ...core.log_system import print_d

if TYPE_CHECKING:
    from src.forms import MainForm


class AudioLyricsModule(QWidget):
    """"Lyrics" tab: line by line lyrics that follow the playback position.

    Lyrics come either from the file tags or from the external transcription service.
    Clicking a line seeks the track to its timestamp.
    """

    def __init__(self, mf, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.mf: MainForm = mf
        self.item_height: int = 18
        self.summariser_width: int = 250
        self.transcription_data: Optional[dict] = None
        self.segments_start: List[float] = []
        self.last_selected_segment: Optional[int] = None

        self.property = TranscriptionPropertyModule(mf, self)
        self.property.setMinimumWidth(200)

        self.regex_timestamp_lyrics = re.compile(r"^\[(\d{2}:\d{2}\.\d{2})\]\s?(.*)$", re.MULTILINE)

        self.label_frame = QFrame()
        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidget(self.label_frame)
        self.scroll_area.setStyleSheet(DEFAULT_SCROLLBAR_STYLE)
        # self.scroll_area.move(0, 30)
        self.scroll_area.resize(self.width() - self.summariser_width, 500)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.splitter = QSplitter(Qt.Orientation.Horizontal, self)
        self.splitter.addWidget(self.scroll_area)
        self.splitter.addWidget(self.property)
        self.splitter.setSizes([self.width() - 200, 200])

        self.v_layout = QVBoxLayout(self)
        self.v_layout.setSpacing(0)
        self.v_layout.setContentsMargins(0, 0, 0, 0)

        self.label_frame.setLayout(self.v_layout)

        self.show_timestamp: bool = True

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self.recalc_position()

    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        self.recalc_position()

    def recalc_position(self):
        self.splitter.resize(self.width(), self.height())

    def set_transcription_data(self, data: dict) -> None:
        self.transcription_data = data
        self.generate_transcription(self.transcription_data)

    def clear(self) -> None:
        for i in reversed(range(self.v_layout.count())):
            item = self.v_layout.itemAt(i)
            if item.widget() is not None:
                item.widget().deleteLater()
            self.v_layout.removeItem(item)
        self.last_selected_segment = None
        self.segments_start = []
        self.property.summariser.clear()

    def update_transcription_list(self) -> None:
        self.generate_transcription(self.transcription_data)

    def get_segments(self) -> Optional[List[dict]]:
        return list(filter(lambda x: x.get('text'), self.transcription_data.get('segments', [])))

    def generate_transcription(self, data: dict) -> None:
        self.clear()
        if data is None:
            return
        segments = self.get_segments()
        self.segments_start = [x.get('start') for x in segments if x.get('start') is not None]
        for segment_index, segment in enumerate(segments):
            item = TrackLabelItem(segment, parent_list=self, show_timestamp=self.show_timestamp)
            item.setFixedHeight(self.item_height)
            self.v_layout.addWidget(item)
        self.v_layout.addStretch()
        self.label_frame.resize(self.width(), self.item_height * (self.v_layout.count() - 1))

    def segment_at(self, timestamp: float) -> Union[None, int]:
        i = bisect_right(self.segments_start, timestamp) - 1
        if i < 0:
            return None
        return i

    @pyqtSlot(int)
    def on_position_changed(self, position: int) -> None:
        if self.isVisible():
            t = position / 1000
            segment_index = self.segment_at(t)
            if (segment_index is not None and
                    (self.last_selected_segment is None or self.last_selected_segment != segment_index)):
                seg: Union["TrackLabelItem", QWidget] = self.v_layout.itemAt(segment_index).widget()
                seg.set_selected(True)
                if self.last_selected_segment is not None:
                    last_seg: Union["TrackLabelItem", QWidget] = self.v_layout.itemAt(self.last_selected_segment).widget()
                    last_seg.set_selected(False)
                    # print_d(f"selected {segment_index} for {seg.get_text()}")
                self.last_selected_segment = segment_index

    def set_position(self, position: float) -> None:
        self.mf.audio_player.set_track_position(int(position * 1000))

    def get_lyrics_from_file(self) -> Optional[dict]:
        lyrics = self.mf.get_current_lyrics()
        if lyrics is None:
            return None
        data = {
            'lyric_source': 'tags',
            'text': lyrics,
            'segments': []
        }
        lyrics = lyrics.replace('\n\n', '\n')
        matches = self.regex_timestamp_lyrics.finditer(lyrics)
        for match_num, match in enumerate(matches, start=1):
            time_str, text = match.groups()
            minutes, seconds = time_str.split(':')
            total_seconds: float = int(minutes) * 60 + float(seconds)
            data['segments'].append({'start': total_seconds, 'text': text})
        if not data['segments']:
            for line in lyrics.split('\n'):
                data['segments'].append({'start': None, 'text': line})
        return data

    @pyqtSlot()
    def set_lyrics_from_file(self) -> None:
        data = self.get_lyrics_from_file()
        if data:
            self.set_transcription_data(data)
            track_id = self.mf.audio_player.playable_track_id
            if track_id is not None:
                self.mf.file_meta_controller.save_track_transcription(track_id, data)


class TrackLabelItem(QWidget):
    """One lyrics line, goes bold while it is the current one and seeks on a click."""

    def __init__(
            self, segment,
            parent_list: AudioLyricsModule,
            show_timestamp: bool = False,
            *args, **kwargs
    ):
        """Build the label of one lyrics segment.

        :param segment: Segment with the start time and the text.
        :param parent_list: Owning AudioLyricsModule.
        :param show_timestamp: Prefix the line with its timestamp.
        :returns: None.
        """
        super(TrackLabelItem, self).__init__(*args, **kwargs)
        self.setMouseTracking(True)
        self.segment = segment
        self.parent_list: AudioLyricsModule = parent_list
        self.mouse_pressed = False
        self.show_timestamp: bool = show_timestamp

        self.text_label = QLabel(self.get_text(), self)
        self.text_label.move(10, 0)
        font = self.text_label.font()
        font.setPointSize(10)
        self.text_label.setFont(font)
        self.text_label.adjustSize()
        self.resize(self.text_label.width(), self.height())

    def set_selected(self, selected: bool) -> None:
        font = self.text_label.font()
        font.setBold(selected)
        self.text_label.setFont(font)
        self.text_label.adjustSize()

    def get_text(self) -> str:
        time = self.segment.get('start')
        if self.show_timestamp and time:
            timestamp = datetime.strftime(datetime.fromtimestamp(time), '%M:%S')
            return f"{timestamp}: {self.segment.get('text')}"
        return self.segment.get('text')

    def mousePressEvent(self, event: QMouseEvent) -> None:
        super().mousePressEvent(event)
        self.mouse_pressed = True

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        super().mouseReleaseEvent(event)
        if self.mouse_pressed and event.button() == Qt.MouseButton.LeftButton:
            time = self.segment.get('start')
            if time:
                self.parent_list.set_position(time)
        self.mouse_pressed = False
    
    def leaveEvent(self, event: QMouseEvent) -> None:
        super().leaveEvent(event)
        self.mouse_pressed = False

    def contextMenuEvent(self, event):
        context_menu = QMenu(self)
        for key, value in self.segment.items():
            if key == 'words':
                context_menu.addAction(f"words:")
                for line in value:
                    context_menu.addAction(f"  - {line}")
            else:
                context_menu.addAction(f"{key}: {value}")
        action = context_menu.exec(self.mapToGlobal(event.pos()))
