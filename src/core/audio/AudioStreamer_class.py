import time
import math
from typing import Optional

import numpy as np
import pyaudio
import wavio

from PyQt6 import QtCore
from PyQt6.QtCore import QObject, QThread

from src.core.log_system import print_d
from src.enums import PlayerState


class AudioStreamer(QThread):
    progress = QtCore.pyqtSignal(int)
    finished = QtCore.pyqtSignal()
    playbackStateChanged = QtCore.pyqtSignal(PlayerState)
    durationChanged = QtCore.pyqtSignal(int)

    def __init__(self):
        super().__init__()
        self._position: int = 0
        self.player_state = PlayerState.NONE
        # self.stream_ref: Optional[pyaudio.Stream] = None
        self.waveform_ref: Optional[np.ndarray] = None
        self.sample_rate: Optional[float] = None
        self.thread_stop: bool = False
        self._chunk_size: int = 1024 * 2
        self._duration: int = 0
        self._channels: int = 2
        self._volume: float = 1.0
        self.log_volume: bool = True

        self.pyaudio_port: pyaudio.PyAudio = pyaudio.PyAudio()
        self.pyaudio_stream: Optional[pyaudio.Stream] = None

    def init_file(self, waveform: np.ndarray, sample_rate: float) -> None:
        self.stop()
        time.sleep(self._chunk_size / sample_rate + 0.01)
        self.waveform_ref = waveform
        self.sample_rate = sample_rate
        self._duration = int(waveform.size / sample_rate * 1000 / self._channels)
        self.durationChanged.emit(self._duration)

        if self.pyaudio_stream is not None:
            self.pyaudio_stream.close()

        self.pyaudio_stream = self.pyaudio_port.open(format=self.pyaudio_port.get_format_from_width(2),
                                                     channels=self._channels,
                                                     rate=int(self.sample_rate),
                                                     output=True)

    def close_audio_port(self) -> None:
        self.pyaudio_port.terminate()
        if self.pyaudio_stream is not None:
            self.pyaudio_stream.close()

    def run(self):
        print_d("AudioStreamer is running")
        while not self.thread_stop:
            if self.player_state is PlayerState.PLAY:
                wave_crop = self.waveform_ref[self._position:self._position + self._chunk_size]
                wave_type = wave_crop.dtype
                wave_crop = (wave_crop * self._volume).astype(wave_type)
                if wave_crop.size == 0:
                    self.stop()
                data = wavio._array2wav(wave_crop, 2)
                self.pyaudio_stream.write(data)
                self._position += self._chunk_size
                self.progress.emit(int(self._position / self.sample_rate * 1000))
            else:
                time.sleep(0.01)
                continue
        self.finished.emit()

    def set_position(self, position: int) -> None:
        self._position = round(position * self.sample_rate / 1000)

    def pause(self) -> None:
        self.player_state = PlayerState.PAUSE
        self.playbackStateChanged.emit(self.player_state)

    def play(self) -> None:
        self.player_state = PlayerState.PLAY
        self.playbackStateChanged.emit(self.player_state)

    def stop(self) -> None:
        self.player_state = PlayerState.STOP
        self.playbackStateChanged.emit(self.player_state)
        self._position = 0

    def set_volume(self, volume: float) -> None:
        if self.log_volume:
            self._volume = math.pow(volume, 2.0)
        else:
            self._volume = volume
        
    def set_chunk_size(self, chunk_size: int) -> None:
        self._chunk_size = chunk_size

    def duration(self) -> int:
        return self._duration


