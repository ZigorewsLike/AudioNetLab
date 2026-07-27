import time
import math
from typing import Optional, List, Dict

import numpy as np
import pyaudio
import wavio
import sounddevice as sd

from PyQt6 import QtCore
from PyQt6.QtCore import QThread, pyqtSlot

from src.core.log_system import print_d, print_e
from src.enums import PlayerState
from src.function_lib.audio import equalizer_librosa


class AudioStreamer(QThread):
    """Background thread that streams a waveform to an output device with optional EQ.

    :signals: progress (int), finished (), trackEnded (), playbackStateChanged (PlayerState),
              durationChanged (float)
    """

    progress = QtCore.pyqtSignal(int)  # Playback position, ms
    finished = QtCore.pyqtSignal()  # Streaming loop has stopped
    trackEnded = QtCore.pyqtSignal()  # The waveform played to its end, unlike a user stop
    playbackStateChanged = QtCore.pyqtSignal(PlayerState)
    durationChanged = QtCore.pyqtSignal(float)  # Track duration, ms

    def __init__(self):
        """Prepare the streaming thread and open the PyAudio port.

        :returns: None.
        """
        super().__init__()
        self._position: int = 0  # Playback position, samples
        self.player_state = PlayerState.NONE
        self.waveform_ref: Optional[np.ndarray] = None
        self.sample_rate: Optional[int] = None
        self.thread_stop: bool = False
        self._chunk_size: int = 512 * 2  # Output buffer size, samples per channel
        self._duration: float = 0
        self._channels: int = 2
        self._volume: float = 1.0
        self.log_volume: bool = True  # Apply a curve so the slider feels linear to the ear
        self.eq_active: bool = True
        self.eq_gains: List[float] = [1.0 for _ in range(20)]  # Linear multiplier per EQ band
        self.bands: List[tuple] = []  # Frequency ranges (f_low, f_high) matching eq_gains

        self.pyaudio_port: pyaudio.PyAudio = pyaudio.PyAudio()
        self.pyaudio_stream: Optional[pyaudio.Stream] = None

    def init_file(self, waveform: np.ndarray, sample_rate: int) -> None:
        """Bind a decoded track to the streamer and reopen the output stream.

        :param waveform: Interleaved sample array of shape [samples, channels].
        :param sample_rate: Sampling rate in Hz.
        :returns: None.
        """
        self.stop()
        time.sleep(self._chunk_size / sample_rate + 0.01)  # Let the current chunk drain

        self.waveform_ref = waveform
        self.sample_rate = sample_rate
        self._duration = waveform.size / sample_rate * 1000 / self._channels

        self.durationChanged.emit(self._duration)

        if self.pyaudio_stream is not None:
            self.pyaudio_stream.close()

        self.open_stream()

    def open_stream(self, device_index: Optional[int] = None) -> None:
        """Open a 16-bit output stream on the given device.

        :param device_index: Output device index, system default when None.
        :returns: None.
        """
        if device_index is None:
            device_index = sd.query_devices(kind='output').get("index")

        self.pyaudio_stream = self.pyaudio_port.open(
            format=self.pyaudio_port.get_format_from_width(2),
            channels=self._channels,
            rate=int(self.sample_rate),
            output_device_index=device_index,
            frames_per_buffer=self._chunk_size,
            output=True
        )

    def switch_device(self, device_index: Optional[int] = None) -> bool:
        """Move playback to another output device.

        :param device_index: Target device index, system default when None.
        :returns: True on success, False when the device was rejected and the default was used.
        """
        try:
            if self.pyaudio_stream is not None:
                if self.pyaudio_stream.is_active():
                    self.pyaudio_stream.stop_stream()
                self.pyaudio_stream.close()
            self.open_stream(device_index)

            return True
        except Exception as e:
            print_e("Unable to switch device", e)
            self.open_stream()  # Fall back to the default device
            return False

    def close_audio_port(self) -> None:
        """Release the PyAudio port and the output stream.

        :returns: None.
        """
        self.pyaudio_port.terminate()
        if self.pyaudio_stream is not None:
            self.pyaudio_stream.close()

    def run(self):
        """Stream the waveform chunk by chunk until the thread is stopped.

        :returns: None (runs inside the thread).
        """
        print_d("AudioStreamer is running")

        while not self.thread_stop:
            if self.player_state is PlayerState.PLAY:

                # Overlap the cut with neighbour samples so the EQ does not produce edge artifacts
                left_padding = self._chunk_size
                right_padding = self._chunk_size

                if self._position == 0:
                    left_padding = 0

                wave_crop = self.waveform_ref[self._position - left_padding:self._position + self._chunk_size + right_padding]

                if wave_crop is None or wave_crop.size == 0:  # End of the track
                    # Distinct from a user stop so the queue advances; the empty chunk is not processed
                    self.trackEnded.emit()
                    self.stop()
                    continue

                wave_type = wave_crop.dtype

                wave_crop = wave_crop.astype(np.float32) / np.iinfo(wave_type).max  # Normalise to [-1, 1]

                # region EQ
                if self.eq_active:
                    wave_crop = equalizer_librosa(wave_crop, self.sample_rate, self.eq_gains, self.bands)
                    wave_crop = np.clip(wave_crop, -1.0, 1.0)
                # endregion

                wave_crop = (wave_crop * self._volume)
                wave_crop = (wave_crop * np.iinfo(wave_type).max).astype(wave_type)

                # Drop the padding and pack the payload chunk into raw PCM bytes
                data = wavio._array2wav(wave_crop[left_padding:self._chunk_size + left_padding], 2)

                try:
                    self.pyaudio_stream.write(data)
                except OSError as e:
                    self.switch_device()  # Device disappeared, retry on another one
                    self.pyaudio_stream.write(data)

                self._position += self._chunk_size

                self.progress.emit(int(self._position / self.sample_rate * 1000))

            else:
                time.sleep(0.01)
                continue

        self.finished.emit()

    def set_position(self, position: int) -> None:
        """Seek to a position inside the track.

        :param position: Offset from the track start in milliseconds.
        :returns: None.
        """
        self._position = round(position * self.sample_rate / 1000)

    def pause(self) -> None:
        """Suspend playback and keep the current position.

        :returns: None.
        """
        self.player_state = PlayerState.PAUSE
        self.playbackStateChanged.emit(self.player_state)

    def play(self) -> None:
        """Resume playback from the current position.

        :returns: None.
        """
        self.player_state = PlayerState.PLAY
        self.playbackStateChanged.emit(self.player_state)

    def stop(self) -> None:
        """Stop playback and rewind to the track start.

        :returns: None.
        """
        self.player_state = PlayerState.STOP
        self.playbackStateChanged.emit(self.player_state)
        self._position = 0

    def set_volume(self, volume: float) -> None:
        """Set the output volume.

        :param volume: Linear value in the range 0..1.
        :returns: None.
        """
        if self.log_volume:
            self._volume = math.pow(volume, 2.0)  # Compensate the non-linear loudness perception
        else:
            self._volume = volume

    def get_volume(self) -> float:
        """Return the current volume multiplier.

        :returns: float - Linear volume value.
        """
        return self._volume

    def set_chunk_size(self, chunk_size: int) -> None:
        """Change the output buffer size.

        :param chunk_size: Buffer size in samples. Larger values are safer against dropouts but add latency.
        :returns: None.
        """
        self._chunk_size = chunk_size

    def get_chunk_size(self) -> int:
        """Return the current output buffer size.

        :returns: int - Buffer size in samples.
        """
        return self._chunk_size

    def duration(self) -> float:
        """Return the duration of the bound track.

        :returns: float - Duration in milliseconds.
        """
        return self._duration

    @pyqtSlot(bool)
    def set_eq_active(self, eq_active: bool) -> None:
        """Enable or disable the equalizer during playback.

        :param eq_active: True enables the EQ, applied starting from the next chunk.
        :returns: None.
        """
        self.eq_active = eq_active

    def print_all_devices(self):
        """Print every available output device to the console.

        :returns: None.
        """
        print_d(self.get_output_devices())

    @staticmethod
    def get_output_devices() -> List[Dict[str, any]]:
        """Collect the multichannel output devices of the system.

        :returns: List[Dict] - Device descriptions (index, name, hostapi, hostapi_name).
        """
        devs = sd.query_devices()

        hostapis = sd.query_hostapis()

        out = []

        for i, d in enumerate(devs):
            if d.get("max_output_channels", 0) > 1:  # Stereo capable devices only
                out.append({
                    "index": d.get("index"),
                    "name": d.get("name"),
                    "hostapi": d.get("hostapi"),
                    "hostapi_name": hostapis[d.get("hostapi")]["name"],
                })
        return out

    @staticmethod
    def get_default_output() -> Dict[str, any]:
        """Describe the system default output device.

        :returns: Dict - Device description (index, name, hostapi, hostapi_name).
        """
        device = sd.query_devices(kind="output")

        hostapis = sd.query_hostapis()

        return {
            "index": device.get("index"),
            "name": device.get("name"),
            "hostapi": device.get("hostapi"),
            "hostapi_name": hostapis[device.get("hostapi")]["name"],
        }