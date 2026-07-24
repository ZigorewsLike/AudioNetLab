from typing import Optional, List

import librosa
import numpy as np
from scipy.signal import butter, lfilter

from src.core.log_system.profiling.line_profiler import profile


# region librosa
def get_mfcc(waveform: Optional[np.ndarray] = None,
             sample_rate: Optional[int] = None) -> Optional[List[float]]:
    """Mean and variance of the first 20 MFCC coefficients.

    :param waveform: Mono waveform.
    :param sample_rate: Sampling rate in Hz.
    :returns: List[float] - 40 values (mean, var per coefficient), None without a waveform.
    """
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
    """Estimated tempo of the fragment.

    :param waveform: Mono waveform.
    :param sample_rate: Sampling rate in Hz.
    :returns: float - Tempo in BPM, None without a waveform.
    """
    if waveform is not None:
        tempo, _ = librosa.beat.beat_track(y=waveform, sr=sample_rate)
        return tempo
    return None


def get_chroma_stft(waveform: Optional[np.ndarray] = None,
                    sample_rate: Optional[int] = None) -> Optional[List[float]]:
    """Mean and variance of the chromagram.

    :param waveform: Mono waveform.
    :param sample_rate: Sampling rate in Hz.
    :returns: List[float] - [mean, var], None without a waveform.
    """
    if waveform is not None:
        chroma: np.ndarray = librosa.feature.chroma_stft(y=waveform, sr=sample_rate)
        return [chroma.mean(), chroma.var()]
    return None


def get_rms(waveform: Optional[np.ndarray] = None) -> Optional[List[float]]:
    """Mean and variance of the RMS envelope.

    :param waveform: Mono waveform.
    :returns: List[float] - [mean, var], None without a waveform.
    """
    if waveform is not None:
        rms: np.ndarray = librosa.feature.rms(y=waveform)
        return [rms.mean(), rms.var()]
    return None


def get_spectral_centroid(waveform: Optional[np.ndarray] = None,
                          sample_rate: Optional[int] = None) -> Optional[List[float]]:
    """Mean and variance of the spectral centroid.

    :param waveform: Mono waveform.
    :param sample_rate: Sampling rate in Hz.
    :returns: List[float] - [mean, var], None without a waveform.
    """
    if waveform is not None:
        spectral_centroid: np.ndarray = librosa.feature.spectral_centroid(y=waveform, sr=sample_rate)[0]
        return [spectral_centroid.mean(), spectral_centroid.var()]
    return None


def get_spectral_bandwidth(waveform: Optional[np.ndarray] = None,
                           sample_rate: Optional[int] = None) -> Optional[List[float]]:
    """Mean and variance of the spectral bandwidth.

    :param waveform: Mono waveform.
    :param sample_rate: Sampling rate in Hz.
    :returns: List[float] - [mean, var], None without a waveform.
    """
    if waveform is not None:
        spectral_bandwidth: np.ndarray = librosa.feature.spectral_bandwidth(y=waveform, sr=sample_rate)[0]
        return [spectral_bandwidth.mean(), spectral_bandwidth.var()]
    return None


def get_spectral_rolloff(waveform: Optional[np.ndarray] = None,
                         sample_rate: Optional[int] = None) -> Optional[List[float]]:
    """Mean and variance of the spectral rolloff.

    :param waveform: Mono waveform.
    :param sample_rate: Sampling rate in Hz.
    :returns: List[float] - [mean, var], None without a waveform.
    """
    if waveform is not None:
        spectral_rolloff: np.ndarray = librosa.feature.spectral_rolloff(y=waveform, sr=sample_rate)[0]
        return [spectral_rolloff.mean(), spectral_rolloff.var()]
    return None


def get_zero_crossing_rate(waveform: Optional[np.ndarray] = None) -> Optional[List[float]]:
    """Mean and variance of the zero crossing rate.

    :param waveform: Mono waveform.
    :returns: List[float] - [mean, var], None without a waveform.
    """
    if waveform is not None:
        zero_crossing_rate: np.ndarray = librosa.feature.zero_crossing_rate(y=waveform)
        return [zero_crossing_rate.mean(), zero_crossing_rate.var()]
    return None


def get_harmonics_and_perceptrual(waveform: Optional[np.ndarray] = None) -> Optional[List[float]]:
    """Statistics of the harmonic and percussive components.

    :param waveform: Mono waveform.
    :returns: List[float] - [harm mean, harm var, perc mean, perc var], None without a waveform.
    """
    if waveform is not None:
        y_harm, y_perc = librosa.effects.hpss(y=waveform)
        y_harm: np.ndarray
        y_perc: np.ndarray
        return [y_harm.mean(), y_harm.var(), y_perc.mean(), y_perc.var()]
    return None
# endregion


def get_genre_input_data(waveform: Optional[np.ndarray] = None, sample_rate: Optional[int] = None) -> List[float]:
    """Build the feature vector expected by the genre classifier.

    The order of the features must match the one used during training.

    :param waveform: Mono fragment of the track.
    :param sample_rate: Sampling rate in Hz.
    :returns: List[float] - 57 feature values.
    """
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
    """Apply a Butterworth bandpass filter to the signal.

    :param data: Input audio data.
    :param lowcut: Lower cutoff frequency in Hz.
    :param highcut: Upper cutoff frequency in Hz.
    :param fs: Sampling rate in Hz.
    :param order: Filter order, higher means a steeper cutoff and more artifacts.
    :returns: numpy.ndarray - Filtered audio data.
    """
    nyq = 0.5 * fs
    low = lowcut / nyq
    high = highcut / nyq
    b, a = butter(order, [low, high], btype='bandpass', analog=False)
    filtered = lfilter(b, a, data)
    return filtered


def equalizer_10band(data, fs,
                     gain1=0, gain2=0, gain3=0, gain4=0, gain5=0,
                     gain6=0, gain7=0, gain8=0, gain9=0, gain10=0):
    """Apply a 10 band equalizer built from bandpass filters.

    Kept as a reference implementation, playback uses equalizer_librosa.

    :param data: Input audio data.
    :param fs: Sampling rate in Hz.
    :param gain1: Gain in dB for 20-39 Hz.
    :param gain2: Gain in dB for 40-79 Hz.
    :param gain3: Gain in dB for 80-159 Hz.
    :param gain4: Gain in dB for 160-299 Hz.
    :param gain5: Gain in dB for 300-599 Hz.
    :param gain6: Gain in dB for 600-1199 Hz.
    :param gain7: Gain in dB for 1200-2399 Hz.
    :param gain8: Gain in dB for 2400-4999 Hz.
    :param gain9: Gain in dB for 5000-9999 Hz.
    :param gain10: Gain in dB for 10000-20000 Hz.
    :returns: numpy.ndarray - Equalized audio data.
    """
    order = 5
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
    return signal


@profile
def equalizer_librosa(audio, sr, gains, bands, n_fft=2048, hop_length=None):
    """Equalize a chunk in the frequency domain via STFT.

    Called for every playback chunk: the spectrum is scaled per band and
    transformed back, which is cheaper than a bank of IIR filters.

    :param audio: Input chunk of shape [samples, channels].
    :param sr: Sampling rate in Hz.
    :param gains: Linear multiplier per band, for example [1.5, 0.8, 1.0].
    :param bands: Frequency ranges (f_low, f_high) in Hz matching gains.
    :param n_fft: FFT window size.
    :param hop_length: Window step, n_fft // 4 when not set.
    :returns: numpy.ndarray - Equalized chunk with the same layout as the input.
    """
    if hop_length is None:
        hop_length = n_fft // 4
    audio = np.swapaxes(audio, 0, 1)  # librosa expects [channels, samples]

    stft_matrix = librosa.stft(audio, n_fft=n_fft, hop_length=hop_length)

    frequencies = librosa.fft_frequencies(sr=sr, n_fft=n_fft)

    gain_filter = np.ones_like(frequencies)

    # Build one gain value per frequency bin out of the band ranges
    for gain, (f_low, f_high) in zip(gains, bands):
        indices = np.where((frequencies >= f_low) & (frequencies <= f_high))[0]
        gain_filter[indices] *= gain

    gain_filter = gain_filter[:, np.newaxis]  # Broadcast the filter over the time axis

    stft_eq = stft_matrix * gain_filter

    audio_eq = librosa.istft(stft_eq, hop_length=hop_length)
    audio_eq = np.swapaxes(audio_eq, 0, 1)

    return audio_eq