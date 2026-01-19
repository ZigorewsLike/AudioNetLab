import time
import math
from typing import Optional, List

import numpy as np
import pyaudio
import wavio
import sounddevice as sd

from PyQt6 import QtCore
from PyQt6.QtCore import QThread, pyqtSlot

from src.core.log_system import print_d
from src.enums import PlayerState
from src.function_lib.audio import equalizer_librosa


class AudioStreamer(QThread):
    progress = QtCore.pyqtSignal(int)
    finished = QtCore.pyqtSignal()
    playbackStateChanged = QtCore.pyqtSignal(PlayerState)
    durationChanged = QtCore.pyqtSignal(float)

    def __init__(self):
        super().__init__()
        self._position: int = 0
        self.player_state = PlayerState.NONE
        self.waveform_ref: Optional[np.ndarray] = None
        self.sample_rate: Optional[int] = None
        self.thread_stop: bool = False
        self._chunk_size: int = 512 * 2
        self._duration: float = 0
        self._channels: int = 2
        self._volume: float = 1.0
        self.log_volume: bool = True
        self.eq_active: bool = True
        self.eq_gains: List[float] = [1.0 for _ in range(20)]
        self.bands: List[tuple] = []

        self.pyaudio_port: pyaudio.PyAudio = pyaudio.PyAudio()
        self.pyaudio_stream: Optional[pyaudio.Stream] = None

    def init_file(self, waveform: np.ndarray, sample_rate: int) -> None:
        self.stop()
        time.sleep(self._chunk_size / sample_rate + 0.01)
        self.waveform_ref = waveform
        self.sample_rate = sample_rate
        self._duration = waveform.size / sample_rate * 1000 / self._channels
        self.durationChanged.emit(self._duration)

        if self.pyaudio_stream is not None:
            self.pyaudio_stream.close()

        self.pyaudio_stream = self.pyaudio_port.open(format=self.pyaudio_port.get_format_from_width(2),
                                                     channels=self._channels,
                                                     rate=int(self.sample_rate),
                                                     frames_per_buffer=self._chunk_size,
                                                     output=True)
        # self.print_all_devices()

    def close_audio_port(self) -> None:
        self.pyaudio_port.terminate()
        if self.pyaudio_stream is not None:
            self.pyaudio_stream.close()

    def run(self):
        print_d("AudioStreamer is running")
        while not self.thread_stop:
            if self.player_state is PlayerState.PLAY:
                left_padding = self._chunk_size
                right_padding = self._chunk_size
                if self._position == 0:
                    left_padding = 0
                    right_padding = self._chunk_size
                wave_crop = self.waveform_ref[self._position - left_padding:self._position + self._chunk_size + right_padding]
                if wave_crop is None or wave_crop.size == 0:
                    self.stop()
                wave_type = wave_crop.dtype
                wave_crop = wave_crop.astype(np.float32) / np.iinfo(wave_type).max
                # region EQ
                if self.eq_active:
                    wave_crop = equalizer_librosa(wave_crop, self.sample_rate, self.eq_gains, self.bands)
                    wave_crop = np.clip(wave_crop, -1.0, 1.0)
                wave_crop = (wave_crop * self._volume)
                wave_crop = (wave_crop * np.iinfo(wave_type).max).astype(wave_type)
                # endregion
                data = wavio._array2wav(wave_crop[left_padding:self._chunk_size+left_padding], 2)
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

    def get_volume(self) -> float:
        return self._volume
        
    def set_chunk_size(self, chunk_size: int) -> None:
        self._chunk_size = chunk_size

    def get_chunk_size(self) -> int:
        return self._chunk_size

    def duration(self) -> float:
        return self._duration

    @pyqtSlot(bool)
    def set_eq_active(self, eq_active: bool) -> None:
        self.eq_active = eq_active

    def print_all_devices(self):
        print_d(sd.query_devices())



