from typing import Optional, List

import librosa
import numpy as np
from scipy.signal import butter, lfilter

from src.core.log_system.profiling.line_profiler import profile


# region librosa
def get_mfcc(waveform: Optional[np.ndarray] = None,
             sample_rate: Optional[int] = None) -> Optional[List[float]]:
    if waveform is not None:
        mfcc: np.ndarray = librosa.feature.mfcc(y=waveform, sr=sample_rate)
        mfcc_list: List[float] = []
        for mccf_index in range(20):
            mfcc_part: np.ndarray = mfcc[mccf_index]
            mfcc_list += [mfcc_part.mean(), mfcc_part.var()]

        return mfcc_list
    return None


def get_tempo(waveform: Optional[np.ndarray] = None,
              sample_rate: Optional[int] = None) -> Optional[float]:
    if waveform is not None:
        tempo, _ = librosa.beat.beat_track(y=waveform, sr=sample_rate)
        return tempo
    return None


def get_chroma_stft(waveform: Optional[np.ndarray] = None,
                    sample_rate: Optional[int] = None) -> Optional[List[float]]:
    if waveform is not None:
        chroma: np.ndarray = librosa.feature.chroma_stft(y=waveform, sr=sample_rate)
        return [chroma.mean(), chroma.var()]
    return None


def get_rms(waveform: Optional[np.ndarray] = None) -> Optional[List[float]]:
    if waveform is not None:
        rms: np.ndarray = librosa.feature.rms(y=waveform)
        return [rms.mean(), rms.var()]
    return None


def get_spectral_centroid(waveform: Optional[np.ndarray] = None,
                          sample_rate: Optional[int] = None) -> Optional[List[float]]:
    if waveform is not None:
        spectral_centroid: np.ndarray = librosa.feature.spectral_centroid(y=waveform, sr=sample_rate)[0]
        return [spectral_centroid.mean(), spectral_centroid.var()]
    return None


def get_spectral_bandwidth(waveform: Optional[np.ndarray] = None,
                           sample_rate: Optional[int] = None) -> Optional[List[float]]:
    if waveform is not None:
        spectral_bandwidth: np.ndarray = librosa.feature.spectral_bandwidth(y=waveform, sr=sample_rate)[0]
        return [spectral_bandwidth.mean(), spectral_bandwidth.var()]
    return None


def get_spectral_rolloff(waveform: Optional[np.ndarray] = None,
                         sample_rate: Optional[int] = None) -> Optional[List[float]]:
    if waveform is not None:
        spectral_rolloff: np.ndarray = librosa.feature.spectral_rolloff(y=waveform, sr=sample_rate)[0]
        return [spectral_rolloff.mean(), spectral_rolloff.var()]
    return None


def get_zero_crossing_rate(waveform: Optional[np.ndarray] = None) -> Optional[List[float]]:
    if waveform is not None:
        zero_crossing_rate: np.ndarray = librosa.feature.zero_crossing_rate(y=waveform)
        return [zero_crossing_rate.mean(), zero_crossing_rate.var()]
    return None


def get_harmonics_and_perceptrual(waveform: Optional[np.ndarray] = None) -> Optional[List[float]]:
    if waveform is not None:
        y_harm, y_perc = librosa.effects.hpss(y=waveform)
        y_harm: np.ndarray
        y_perc: np.ndarray
        return [y_harm.mean(), y_harm.var(), y_perc.mean(), y_perc.var()]
    return None
# endregion


def get_genre_input_data(waveform: Optional[np.ndarray] = None, sample_rate: Optional[int] = None) -> List[float]:
    input_data: list = []
    input_data += get_chroma_stft(waveform, sample_rate)
    input_data += get_rms(waveform)
    input_data += get_spectral_centroid(waveform, sample_rate)
    input_data += get_spectral_bandwidth(waveform, sample_rate)
    input_data += get_spectral_rolloff(waveform, sample_rate)
    input_data += get_zero_crossing_rate(waveform)
    input_data += get_harmonics_and_perceptrual(waveform)
    input_data += [get_tempo(waveform, sample_rate)]
    input_data += get_mfcc(waveform, sample_rate)

    return input_data


@profile
def equalizer_librosa(audio, sr, gains, bands, n_fft=2048, hop_length=None):
    """
    Функция эквалайзера с использованием библиотеки librosa.

    Параметры:
    audio : numpy.array
        Входной аудиосигнал (моно).
    sr : int
        Частота дискретизации аудио.
    gains : list of float
        Список множителей усиления для каждой полосы (например, [1.5, 0.8, 1.0]).
    bands : list of tuple
        Список диапазонов частот в Гц для каждой полосы в виде кортежей (f_low, f_high),
        например, [(20, 300), (300, 2000), (2000, sr/2)].
    n_fft : int, optional
        Размер окна FFT (по умолчанию 2048).
    hop_length : int, optional
        Шаг окна. Если не задан, то используется значение n_fft // 4.

    Возвращает:
    audio_eq : numpy.array
        Эквализированный аудиосигнал.
    """
    if hop_length is None:
        hop_length = n_fft // 4
    audio = np.swapaxes(audio, 0, 1)

    # Вычисление спектрограммы с помощью STFT
    stft_matrix = librosa.stft(audio, n_fft=n_fft, hop_length=hop_length)

    # Получение массива частот для строк STFT
    frequencies = librosa.fft_frequencies(sr=sr, n_fft=n_fft)

    # Инициализация фильтра усиления (начальное значение 1 для каждой частоты)
    gain_filter = np.ones_like(frequencies)

    # Применение усиления для каждого заданного диапазона частот
    for gain, (f_low, f_high) in zip(gains, bands):
        # Определение индексов частот, попадающих в диапазон [f_low, f_high]
        indices = np.where((frequencies >= f_low) & (frequencies <= f_high))[0]
        gain_filter[indices] *= gain

    # Приведение фильтра к размерности матрицы STFT (добавляем ось времени)
    gain_filter = gain_filter[:, np.newaxis]

    # Применение фильтра к спектру (умножение каждой строки на соответствующий множитель)
    stft_eq = stft_matrix * gain_filter

    # Обратное преобразование спектра во временную область
    audio_eq = librosa.istft(stft_eq, hop_length=hop_length)
    audio_eq = np.swapaxes(audio_eq, 0, 1)

    return audio_eq
