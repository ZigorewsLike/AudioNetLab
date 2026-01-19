from datetime import datetime
import mimetypes
from bisect import bisect_right
from typing import TYPE_CHECKING, List, Union, Optional

import requests
from PyQt6.QtCore import Qt, pyqtSlot
from PyQt6.QtGui import QResizeEvent, QFont, QMouseEvent, QShowEvent
from PyQt6.QtWidgets import QWidget, QPushButton, QFrame, QScrollArea, QVBoxLayout, QLabel, QMenu, QComboBox, QCheckBox

from src.core.log_system import print_d
from src.global_styles import DEFAULT_SCROLLBAR_STYLE

if TYPE_CHECKING:
    from src.forms import MainForm


class AudioTranscriptionModule(QWidget):
    def __init__(self, mf, *args, **kwargs):
        super(AudioTranscriptionModule, self).__init__(*args, **kwargs)
        self.mf: MainForm = mf
        self.host = 'http://127.0.0.1:13000'
        self.end_point = 'audio/transcription/process'
        self.item_height: int = 18
        self.transcription_data: Optional[dict] = None
        self.segments_start: List[float] = []
        self.last_selected_segment: Optional[int] = None

        self.run_process_button = QPushButton("Run process", self)
        self.run_process_button.clicked.connect(self.run_process)

        self.model_name_combo = QComboBox(self)
        self.model_name_combo.addItems([
            "tiny",
            "base.en",
            "base",
            "small.en",
            "small",
            "medium.en",
            "medium",
            "large-v1",
            "large-v2",
            "large-v3",
            "large",
            "large-v3-turbo",
            "turbo"
        ])
        self.model_name_combo.setCurrentText("large-v3-turbo")

        self.show_timestamp_checkbox = QCheckBox("Show timestamp", self)
        self.show_timestamp_checkbox.stateChanged.connect(lambda : self.generate_transcription(self.transcription_data))

        self.label_frame = QFrame()
        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidget(self.label_frame)
        self.scroll_area.setStyleSheet(DEFAULT_SCROLLBAR_STYLE)
        self.scroll_area.move(0, 30)
        self.scroll_area.resize(self.width(), 500)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.v_layout = QVBoxLayout(self)
        self.v_layout.setSpacing(0)
        self.v_layout.setContentsMargins(0, 0, 0, 0)

        self.label_frame.setLayout(self.v_layout)

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self.recalc_position()

    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        self.recalc_position()

    def recalc_position(self):
        self.scroll_area.resize(self.width(), self.height() - 30)
        self.model_name_combo.move(self.run_process_button.width() + 10, 0)
        self.show_timestamp_checkbox.move(self.model_name_combo.width() + self.model_name_combo.x() + 10, 0)

    def run_process(self) -> None:
        url: str = f"{self.host}/{self.end_point}"
        opened_file = self.mf.audio_player.playable_file_file
        if opened_file is None:
            return

        mime_type, encoding = mimetypes.guess_type(opened_file)
        with open(opened_file, "rb") as f:
            r = requests.post(
                url,
                params={"model_name": self.model_name_combo.currentText()},
                files={"file": (opened_file, f, mime_type)},  # ключ "file" важен [web:31]
                timeout=300,
            )
        # print_d(r.status_code, r.json())
        if r.status_code == 200:
            data = r.json()
            self.generate_transcription(data)
            track_id = self.mf.audio_player.playable_track_id
            if track_id is not None:
                self.mf.file_meta_controller.save_track_transcription(track_id, data)

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

    def generate_transcription(self, data: dict) -> None:
        self.clear()
        if data is None:
            return
        segments = list(filter(lambda x: x.get('text'), data.get('segments', [])))
        self.segments_start = [x.get('start') for x in segments]
        for segment_index, segment in enumerate(segments):
            item = TrackLabelItem(segment, parent_list=self, show_timestamp=self.show_timestamp_checkbox.isChecked())
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


class TrackLabelItem(QWidget):
    def __init__(
            self, segment,
            parent_list: AudioTranscriptionModule,
            show_timestamp: bool = False,
            *args, **kwargs
    ):
        super(TrackLabelItem, self).__init__(*args, **kwargs)
        self.setMouseTracking(True)
        self.segment = segment
        self.parent_list: AudioTranscriptionModule = parent_list
        self.mouse_pressed = False
        self.show_timestamp: bool = show_timestamp

        self.text_label = QLabel(self.get_text(), self)
        self.text_label.move(10, 0)
        font = self.text_label.font()
        font.setPointSize(10)
        self.text_label.setFont(font)

    def set_selected(self, selected: bool) -> None:
        font = self.text_label.font()
        font.setBold(selected)
        self.text_label.setFont(font)
        self.text_label.adjustSize()

    def get_text(self) -> str:
        if self.show_timestamp:
            timestamp = datetime.strftime(datetime.fromtimestamp(self.segment.get('start')), '%M:%S')
            return f"{timestamp}: {self.segment.get('text')}"
        return self.segment.get('text')

    def mousePressEvent(self, event: QMouseEvent) -> None:
        super().mousePressEvent(event)
        self.mouse_pressed = True

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        super().mouseReleaseEvent(event)
        if self.mouse_pressed and event.button() == Qt.MouseButton.LeftButton:
            self.parent_list.set_position(self.segment.get('start'))
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
