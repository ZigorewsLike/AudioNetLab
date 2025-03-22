from typing import Optional, List

import librosa
import numpy as np
from scipy import ifft
from scipy.signal import butter, lfilter
from sympy import fft

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


def bandpass_filter(data, lowcut, highcut, fs, order=5):
    """
    Applies a bandpass filter to the input data.

    Args:
        data (numpy.ndarray): The input audio data.
        lowcut (float): The lower cutoff frequency in Hz.
        highcut (float): The upper cutoff frequency in Hz.
        fs (int): The sampling rate of the audio data in Hz.
        order (int): The order of the filter. Higher orders result in steeper
            cutoff but can introduce more artifacts.

    Returns:
        numpy.ndarray: The filtered audio data.
    """
    nyq = 0.5 * fs
    low = lowcut / nyq
    high = highcut / nyq
    b, a = butter(order, [low, high], btype='bandpass', analog=True)
    filtered = lfilter(b, a, data)
    return filtered


def equalizer_10band(data, fs,
                     gain1=0, gain2=0, gain3=0, gain4=0, gain5=0,
                     gain6=0, gain7=0, gain8=0, gain9=0, gain10=0):
    """
    Applies a 10-band equalizer to the input data.

    Args:
        data (numpy.ndarray): The input audio data.
        fs (int): The sampling rate of the audio data in Hz.
        gain1 through gain10 (float): The gain in dB for each of the 10 bands.

    Returns:
        numpy.ndarray: The equalized audio data.
    """
    order = 3
    band1 = bandpass_filter(data, 20, 39, fs, order=order) * 10**(gain1/20)
    band2 = bandpass_filter(data, 40, 79, fs, order=order) * 10**(gain2/20)
    band3 = bandpass_filter(data, 80, 159, fs, order=order) * 10**(gain3/20)
    band4 = bandpass_filter(data, 160, 299, fs, order=order) * 10**(gain4/20)
    band5 = bandpass_filter(data, 300, 599, fs, order=order) * 10**(gain5/20)
    band6 = bandpass_filter(data, 600, 1199, fs, order=order) * 10**(gain6/20)
    band7 = bandpass_filter(data, 1200, 2399, fs, order=order) * 10**(gain7/20)
    band8 = bandpass_filter(data, 2400, 4999, fs, order=order) * 10**(gain8/20)
    band9 = bandpass_filter(data, 5000, 9999, fs, order=order) * 10**(gain9/20)
    band10 = bandpass_filter(data, 10000, 20000, fs, order=order) * 10**(gain10/20)

    signal = (band1 + band2 + band3 + band4 + band5 +
              band6 + band7 + band8 + band9 + band10)
    return band2


def equalize_signal(x, fs, gains, bands):
    """
    Equalizes an audio signal in the frequency domain.

    Parameters:
    - x: numpy array of the time-domain audio signal.
    - fs: sampling frequency (Hz).
    - gains: list of gain multipliers for each frequency band.
    - bands: list of tuples (f_low, f_high) defining frequency ranges for each band.

    Returns:
    - x_eq: the equalized time-domain audio signal.
    """
    N = len(x)
    # FFT conversion to frequency domain
    X = librosa.stft(x, hop_length=N)
    freqs = np.fft.fftfreq(N, 1 / fs)

    # Initialize a gain array with ones (no change)
    gain_array = np.ones(N)

    # Apply each gain to the corresponding frequency band
    for gain, (f_low, f_high) in zip(gains, bands):
        # Find indices for frequencies within the specified band
        band_indices = np.where((np.abs(freqs) >= f_low) & (np.abs(freqs) <= f_high))[0]
        gain_array[band_indices] *= gain

    # Apply the gain adjustments in the frequency domain
    X_eq = X * gain_array

    # Convert the modified signal back to the time domain
    x_eq = np.real(ifft(X_eq))
    return x_eq


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
