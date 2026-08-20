import time
import math
import threading
from typing import Optional, List, Dict, Tuple

import numpy as np
import pyaudio
import sounddevice as sd

from PyQt6 import QtCore
from PyQt6.QtCore import QThread, pyqtSlot

from src.core.log_system import print_d, print_e
from src.enums import PlayerState
from src.function_lib.audio import equalizer_librosa


class _AudioRingBuffer:
    """Lock-guarded ring buffer of interleaved float32 frames shared by producer and callback."""

    def __init__(self, capacity_frames: int, channels: int):
        """Allocate the buffer.

        :param capacity_frames: Buffer size in frames (samples per channel).
        :param channels: Channel count per frame.
        :returns: None.
        """
        self._cap = max(capacity_frames, 1)
        self._ch = channels
        self._buf = np.zeros((self._cap, channels), dtype=np.float32)
        self._read = 0
        self._write = 0
        self._count = 0  # Frames currently stored
        self._lock = threading.Lock()

    def clear(self) -> None:
        """Drop every buffered frame.

        :returns: None.
        """
        with self._lock:
            self._read = self._write = self._count = 0

    def available(self) -> int:
        """Frames ready to be read.

        :returns: int - Stored frame count.
        """
        with self._lock:
            return self._count

    def free(self) -> int:
        """Free space left for the producer.

        :returns: int - Writable frame count.
        """
        with self._lock:
            return self._cap - self._count

    def write(self, frames: np.ndarray) -> int:
        """Append frames, dropping any overflow the producer failed to throttle.

        :param frames: Array of shape [n, channels], float32.
        :returns: int - Number of frames actually stored.
        """
        n = frames.shape[0]
        with self._lock:
            n = min(n, self._cap - self._count)
            if n <= 0:
                return 0
            first = min(n, self._cap - self._write)
            self._buf[self._write:self._write + first] = frames[:first]
            second = n - first
            if second:
                self._buf[0:second] = frames[first:first + second]
            self._write = (self._write + n) % self._cap
            self._count += n
            return n

    def keep_head(self, n: int) -> int:
        """Drop the newest frames, keeping at most n of the oldest ones near the playhead.

        :param n: Frames to keep.
        :returns: int - Frames discarded from the tail.
        """
        with self._lock:
            keep = min(n, self._count)
            discarded = self._count - keep
            self._count = keep
            self._write = (self._read + keep) % self._cap
            return discarded

    def read(self, n: int) -> Tuple[np.ndarray, int]:
        """Pull up to n frames, zero padding the tail on underrun.

        :param n: Requested frame count.
        :returns: Tuple - (frames [n, channels] float32, real frames delivered).
        """
        out = np.zeros((n, self._ch), dtype=np.float32)
        real = self.read_into(out, n)
        return out, real

    def read_into(self, out: np.ndarray, n: int) -> int:
        """Fill out[:n] from the buffer, zero padding the tail on underrun.

        :param out: Preallocated target array of shape [>= n, channels], float32.
        :param n: Requested frame count.
        :returns: int - Real frames delivered.
        """
        with self._lock:
            real = min(n, self._count)
            first = min(real, self._cap - self._read)
            out[:first] = self._buf[self._read:self._read + first]
            second = real - first
            if second:
                out[first:real] = self._buf[0:second]
            if real < n:
                out[real:n] = 0.0
            self._read = (self._read + real) % self._cap
            self._count -= real
        return real


class AudioStreamer(QThread):
    """Streams a waveform to an output device with optional EQ.

    The thread runs as a producer that processes audio into a decode-ahead ring buffer,
    while a PortAudio callback pulls the pre-processed float32 frames on its own high
    priority thread. This isolates playback from load on the Python/GUI threads.

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
        self._position: int = 0  # Producer read cursor, frames
        self._frames_played: int = 0  # Frames drained by the callback, frames
        self.player_state = PlayerState.NONE
        self.waveform_ref: Optional[np.ndarray] = None
        self.sample_rate: Optional[int] = None
        self.thread_stop: bool = False
        self._chunk_size: int = 512 * 2  # Producer processing block, frames
        self._device_buffer: int = 4096  # PortAudio buffer, frames - the stutter-resistance knob
        self._duration: float = 0
        self._channels: int = 2
        self._volume: float = 1.0
        self.log_volume: bool = True  # Apply a curve so the slider feels linear to the ear
        self.eq_active: bool = True
        self.eq_gains: List[float] = [1.0 for _ in range(20)]  # Linear multiplier per EQ band
        self.bands: List[tuple] = []  # Frequency ranges (f_low, f_high) matching eq_gains

        self._buffer: Optional[_AudioRingBuffer] = None
        self._target_fill: int = 0  # Frames the producer keeps queued ahead of playback
        self._prebuffer: int = 0  # Frames to gather before the callback starts a fresh segment
        self._cb_out: Optional[np.ndarray] = None  # Preallocated callback output, avoids per-call alloc
        self._silence: bytes = b""  # Preallocated silence for one device buffer
        self._prebuffering: bool = True
        self._reached_end: bool = False
        self._lock = threading.Lock()  # Guards waveform/position swaps
        self._last_progress: float = 0.0

        self._eq_target: int = 0  # Small lookahead kept while the EQ is being changed
        self._resync_requested: bool = False  # Set by the UI, handled by the producer thread
        self._eq_interacting_until: float = 0.0  # Timestamp until which the EQ counts as active
        self._epoch: int = 0  # Bumped on every seek/stop so in-flight chunks are dropped

        self.pyaudio_port: pyaudio.PyAudio = pyaudio.PyAudio()
        self.pyaudio_stream: Optional[pyaudio.Stream] = None

    def init_file(self, waveform: np.ndarray, sample_rate: int) -> None:
        """Bind a decoded track to the streamer, reusing the open stream when possible.

        :param waveform: Interleaved sample array of shape [samples, channels].
        :param sample_rate: Sampling rate in Hz.
        :returns: None.
        """
        self.stop()

        channels = waveform.shape[1] if waveform.ndim == 2 else 1
        # Only the sample rate or channel count forces a stream reopen; a plain track
        # change keeps the device open so it does not glitch.
        needs_reopen = (self.pyaudio_stream is None
                        or sample_rate != self.sample_rate
                        or channels != self._channels)

        with self._lock:
            self.waveform_ref = waveform
            self.sample_rate = sample_rate
            self._channels = channels
            self._duration = waveform.size / sample_rate * 1000 / channels
            self._position = 0
            self._frames_played = 0
            self._reached_end = False
            self._prebuffering = True
            self._epoch += 1
            self._setup_buffer()

        self.durationChanged.emit(self._duration)

        if needs_reopen:
            if self.pyaudio_stream is not None:
                self.pyaudio_stream.close()
            self.open_stream()

    def _setup_buffer(self) -> None:
        """Size the ring buffer and the fill thresholds for the current sample rate.

        :returns: None (call while holding the lock).
        """
        sr = int(self.sample_rate)
        self._target_fill = sr  # Keep ~1 s queued ahead of the device
        # Cushion before a fresh segment: at least two device buffers, so the callback
        # never starts against a partially filled buffer even at large buffer sizes.
        self._prebuffer = max(int(sr * 0.15), self._device_buffer * 2)
        self._eq_target = int(sr * 0.12)  # Lookahead while the EQ is being dragged, ~120 ms
        self._buffer = _AudioRingBuffer(sr * 2, self._channels)  # ~2 s capacity
        self._alloc_callback_scratch()

    def _alloc_callback_scratch(self) -> None:
        """Preallocate the callback output and silence so the audio thread never allocates.

        :returns: None (call while holding the lock).
        """
        self._cb_out = np.zeros((self._device_buffer, self._channels), dtype=np.float32)
        self._silence = bytes(self._device_buffer * self._channels * 4)

    def open_stream(self, device_index: Optional[int] = None) -> None:
        """Open a float32 callback stream on the given device.

        :param device_index: Output device index, system default when None.
        :returns: None.
        """
        if device_index is None:
            device_index = sd.query_devices(kind='output').get("index")

        self.pyaudio_stream = self.pyaudio_port.open(
            format=pyaudio.paFloat32,
            channels=self._channels,
            rate=int(self.sample_rate),
            output_device_index=device_index,
            frames_per_buffer=self._device_buffer,
            output=True,
            stream_callback=self._audio_callback,
        )

    def _audio_callback(self, in_data, frame_count, time_info, status):
        """Feed the device from the ring buffer without any processing on this thread.

        :returns: Tuple - (interleaved float32 bytes, paContinue).
        """
        buffer = self._buffer
        if buffer is None or self.player_state is not PlayerState.PLAY:
            return self._silence_bytes(frame_count), pyaudio.paContinue

        # Wait until a cushion is queued before a freshly started or seeked segment plays
        if self._prebuffering:
            if not self._reached_end and buffer.available() < self._prebuffer:
                return self._silence_bytes(frame_count), pyaudio.paContinue
            self._prebuffering = False

        out = self._cb_out
        if out is None or frame_count > out.shape[0] or out.shape[1] != self._channels:
            data, real = buffer.read(frame_count)  # Fallback for an unexpected frame count
            self._frames_played += real
            data *= self._volume
            return data.tobytes(), pyaudio.paContinue

        real = buffer.read_into(out, frame_count)
        self._frames_played += real  # Only real frames count, so progress pauses on underrun
        view = out[:frame_count]
        view *= self._volume  # Applied here, past the buffer, so the slider reacts instantly
        return view.tobytes(), pyaudio.paContinue

    def _silence_bytes(self, frame_count: int) -> bytes:
        """Return a silent buffer, reusing the preallocated one for the common size.

        :param frame_count: Requested frame count.
        :returns: bytes - Interleaved float32 zeros.
        """
        if frame_count == self._device_buffer and self._silence:
            return self._silence
        return bytes(frame_count * self._channels * 4)

    def switch_device(self, device_index: Optional[int] = None) -> bool:
        """Move playback to another output device, keeping the buffered audio.

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
        """Stop the producer, release the PyAudio port and the output stream.

        :returns: None.
        """
        self.thread_stop = True
        if self.pyaudio_stream is not None:
            self.pyaudio_stream.close()
        self.pyaudio_port.terminate()

    def run(self):
        """Fill the ring buffer ahead of playback until the thread is stopped.

        :returns: None (runs inside the thread).
        """
        print_d("AudioStreamer is running")

        while not self.thread_stop:
            if self.player_state is not PlayerState.PLAY or self._buffer is None:
                self._emit_progress()
                time.sleep(0.01)
                continue

            if self._reached_end:
                # Wait for the queued tail to drain, then advance the queue
                if self._buffer.available() == 0:
                    with self._lock:
                        still_end = self._reached_end  # A seek here resets it before clearing
                        self._reached_end = False
                    if still_end:
                        self.trackEnded.emit()
                        self.stop()
                else:
                    self._emit_progress()
                    time.sleep(0.01)
                continue

            # While the EQ is being changed, keep only a short lookahead so new gains are
            # heard almost at once; otherwise run ~1 s ahead for load protection.
            interacting = time.time() < self._eq_interacting_until
            if self._resync_requested:
                self._resync_requested = False
                self._apply_resync()
            target = self._eq_target if interacting else self._target_fill

            if self._buffer.free() < self._chunk_size or self._buffer.available() >= target:
                self._emit_progress()
                time.sleep(0.005)  # Enough queued, wait before topping up
                continue

            payload = self._produce_chunk()
            if payload is None:  # End of track or a chunk dropped after a seek
                continue

            self._buffer.write(payload)
            self._emit_progress()

        self.finished.emit()

    def _produce_chunk(self) -> Optional[np.ndarray]:
        """Process the next block into interleaved float32, or None at the end of the track.

        :returns: numpy.ndarray - Processed frames [n, channels], or None.
        """
        with self._lock:
            waveform = self.waveform_ref
            if waveform is None:
                return None
            epoch = self._epoch  # Captured so a seek during the render can be detected
            position = self._position
            chunk = self._chunk_size

            # Overlap the cut with neighbour samples so the EQ does not produce edge artifacts
            left_padding = min(position, chunk)
            start = position - left_padding
            crop = waveform[start:position + chunk + chunk]
            end_of_track = crop.shape[0] <= left_padding  # Nothing beyond the padding

        if end_of_track:
            with self._lock:
                if epoch == self._epoch:
                    self._reached_end = True
            return None

        wave = crop.astype(np.float32) / 32767.0

        gains = self.eq_gains
        if self.eq_active and self.bands and not np.allclose(gains, 1.0):
            wave = equalizer_librosa(wave, self.sample_rate, gains, self.bands)
            np.clip(wave, -1.0, 1.0, out=wave)

        payload = wave[left_padding:left_padding + chunk]

        # Volume is applied in the callback, not here, so it stays out of the buffered audio

        with self._lock:
            if epoch != self._epoch:
                return None  # A seek landed while rendering, drop this now stale chunk
            if payload.shape[0] == 0:
                self._reached_end = True
                return None
            self._position += payload.shape[0]

        return np.ascontiguousarray(payload, dtype=np.float32)

    def _apply_resync(self) -> None:
        """Shrink the lookahead to the interaction window so a new EQ curve is heard quickly.

        Runs on the producer thread, between chunks, so it never races an in-flight render.
        Only the tail past the kept cushion is dropped, so playback does not fall silent, and
        once the lookahead is already small this is a no-op splice.

        :returns: None.
        """
        if self._buffer is None:
            return
        with self._lock:
            discarded = self._buffer.keep_head(self._eq_target)
            self._position -= discarded  # Rewind the producer over the frames it must redo
            self._reached_end = False

    def _emit_progress(self) -> None:
        """Report the played position, throttled to keep UI redraws off the audio path.

        :returns: None.
        """
        if not self.sample_rate:
            return
        now = time.time()
        if now - self._last_progress < 0.04:
            return
        self._last_progress = now
        self.progress.emit(int(self._frames_played / self.sample_rate * 1000))

    def set_position(self, position: int) -> None:
        """Seek to a position inside the track.

        :param position: Offset from the track start in milliseconds.
        :returns: None.
        """
        with self._lock:
            self._position = round(position * self.sample_rate / 1000)
            self._frames_played = self._position
            self._reached_end = False
            self._prebuffering = True
            self._epoch += 1
        if self._buffer is not None:
            self._buffer.clear()

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
        with self._lock:
            self._position = 0
            self._frames_played = 0
            self._reached_end = False
            self._prebuffering = True
            self._epoch += 1
        if self._buffer is not None:
            self._buffer.clear()

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
        """Change the device (PortAudio) buffer size, reopening the stream.

        This is the stutter-resistance knob: a larger buffer lets the Python callback
        tolerate longer stalls under CPU load, at the cost of latency. The producer's
        processing block is independent and stays small so the EQ keeps reacting quickly.

        :param chunk_size: Device buffer size in frames.
        :returns: None.
        """
        if chunk_size == self._device_buffer:
            return
        self._device_buffer = chunk_size
        if self.pyaudio_stream is not None and self.sample_rate is not None:
            was_playing = self.player_state is PlayerState.PLAY
            self.player_state = PlayerState.PAUSE
            try:
                self.pyaudio_stream.close()
                with self._lock:
                    self._prebuffer = max(int(self.sample_rate * 0.15), self._device_buffer * 2)
                    self._alloc_callback_scratch()
                    self._prebuffering = True
                if self._buffer is not None:
                    self._buffer.clear()
                self.open_stream()
            except Exception as e:
                print_e("Unable to resize the audio buffer", e)
            if was_playing:
                self.player_state = PlayerState.PLAY

    def get_chunk_size(self) -> int:
        """Return the current device buffer size.

        :returns: int - Device buffer size in frames.
        """
        return self._device_buffer

    def duration(self) -> float:
        """Return the duration of the bound track.

        :returns: float - Duration in milliseconds.
        """
        return self._duration

    def _request_eq_resync(self) -> None:
        """Ask the producer to shorten its lookahead so EQ edits are heard quickly.

        :returns: None.
        """
        self._eq_interacting_until = time.time() + 0.35  # Keep the short lookahead during a drag
        self._resync_requested = True

    def set_eq_gains(self, gains: List[float]) -> None:
        """Set the EQ band gains and re-render the buffered audio so the change is heard at once.

        :param gains: Linear multiplier per band.
        :returns: None.
        """
        self.eq_gains = gains
        if self.player_state is PlayerState.PLAY:
            self._request_eq_resync()

    @pyqtSlot(bool)
    def set_eq_active(self, eq_active: bool) -> None:
        """Enable or disable the equalizer during playback.

        :param eq_active: True enables the EQ, re-rendering the buffered audio.
        :returns: None.
        """
        self.eq_active = eq_active
        if self.player_state is PlayerState.PLAY:
            self._request_eq_resync()

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
