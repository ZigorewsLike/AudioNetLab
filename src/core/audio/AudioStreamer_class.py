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
    """Класс для потокового воспроизведения аудио с поддержкой EQ и управления устройствами.

    :signals: progress (int), finished (), playbackStateChanged (PlayerState), durationChanged (float)
    :attributes: _position, player_state, waveform_ref, sample_rate, thread_stop, chunk_size, duration, channels, volume, log_volume, eq_active, eq_gains, bands, pyaudio_port, pyaudio_stream
    """
    
    progress = QtCore.pyqtSignal(int)  # Сигнал обновления положения (ms)
    finished = QtCore.pyqtSignal()  # Сигнал завершения воспроизведения
    playbackStateChanged = QtCore.pyqtSignal(PlayerState)  # Сигнал изменения состояния воспроизведения
    durationChanged = QtCore.pyqtSignal(float)  # Сигнал изменения длительности трека

    def __init__(self):
        """Инициализация потока для воспроизведения аудио.

        :returns: None
        """
        super().__init__()
        # Текущая позиция воспроизведения в сэмплах
        self._position: int = 0
        # Состояние плеера (NONE/PLAY/PAUSE/STOP)
        self.player_state = PlayerState.NONE
        # Ссылка на форму волны для воспроизведения
        self.waveform_ref: Optional[np.ndarray] = None
        # Частота дискретизации в Hz
        self.sample_rate: Optional[int] = None
        # Флаг остановки потока
        self.thread_stop: bool = False
        # Размер буфера вывода (чанк) в сэмплах — 512*2 для стерео
        self._chunk_size: int = 512 * 2
        # Вычисленная длительность трека в миллисекундах
        self._duration: float = 0
        # Количество каналов (обычно 2 для стерео)
        self._channels: int = 2
        # Текущая громкость (линейное значение)
        self._volume: float = 1.0
        # Флаг логарифмического отображения громкости в логах
        self.log_volume: bool = True
        # Активация/деактивация эквалайзера
        self.eq_active: bool = True
        # Коэффициенты усиления для каждого бэнда эквалайзера (20 бэндов)
        self.eq_gains: List[float] = [1.0 for _ in range(20)]
        # Конфигурация частотных полос EQ (частота, ширина, тип наклона)
        self.bands: List[tuple] = []

        # Порт PyAudio для вывода звука
        self.pyaudio_port: pyaudio.PyAudio = pyaudio.PyAudio()
        # Потоковая передача аудио (будет создана при инициализации файла)
        self.pyaudio_stream: Optional[pyaudio.Stream] = None

    def init_file(self, waveform: np.ndarray, sample_rate: int) -> None:
        """Инициализация потока воспроизведением файла.

        :param waveform: Двумерный массив формы волны [channels, samples].
        :param sample_rate: Частота дискретизации в Hz.
        :returns: None.
        """
        self.stop()  # Остановка текущего воспроизведения
        time.sleep(self._chunk_size / sample_rate + 0.01)  # Задержка для сброса буфера
        
        self.waveform_ref = waveform  # Сохранение формы волны для обработки
        self.sample_rate = sample_rate  # Установление частоты дискретизации
        self._duration = waveform.size / sample_rate * 1000 / self._channels  # Вычисление длительности в мс
        
        self.durationChanged.emit(self._duration)  # Сообщаем о новой длительности
        
        if self.pyaudio_stream is not None:  # Закрываем существующий поток
            self.pyaudio_stream.close()

        self.open_stream()  # Открываем новый аудиопоток

    def open_stream(self, device_index: Optional[int] = None) -> None:
        """Открытие аудиопотока для вывода звука.

        :param device_index: Индекс выходного устройства (по умолчанию - default device).
        :returns: None.
        """
        if device_index is None:  # Получаем индекс default устройства по умолчанию
            device_index = sd.query_devices(kind='output').get("index")
        
        self.pyaudio_stream = self.pyaudio_port.open(
            format=self.pyaudio_port.get_format_from_width(2),  # Format для 16-bit звука
            channels=self._channels,  # Количество каналов (обычно 2)
            rate=int(self.sample_rate),  # Частота дискретизации
            output_device_index=device_index,  # Индекс выходного устройства
            frames_per_buffer=self._chunk_size,  # Размер буфера вывода
            output=True  # Выходной поток
        )

    def switch_device(self, device_index: Optional[int] = None) -> bool:
        """Смена выходного аудиоустройства.

        :param device_index: Индекс целевого устройства (по умолчанию - default device).
        :returns: True если переключение успешно, False при ошибке.
        """
        try:
            if self.pyaudio_stream is not None:  # Если поток активен
                if self.pyaudio_stream.is_active():  # Останавливаем текущую передачу
                    self.pyaudio_stream.stop_stream()
                self.pyaudio_stream.close()  # Закрываем старый поток
            self.open_stream(device_index)  # Открываем новый поток для устройства
            
            return True  # Успешное переключение
        except Exception as e:  # При ошибке
            print_e("Unable to switch device", e)  # Логирование ошибки
            self.open_stream()  # Пытаемся использовать default устройство
            return False  # Возвращаем False на ошибку

    def close_audio_port(self) -> None:
        """Закрытие аудиопорта и освобождение ресурсов.

        :returns: None.
        """
        self.pyaudio_port.terminate()  # Терминирование порта PyAudio
        if self.pyaudio_stream is not None:  # Если поток существует
            self.pyaudio_stream.close()  # Закрытие потока

    def run(self):
        """Основной цикл воспроизведения потока.

        :returns: None (выполняется в потоке).
        """
        print_d("AudioStreamer is running")  # Логирование запуска потока
        
        while not self.thread_stop:  # Основной цикл обработки чанков
            if self.player_state is PlayerState.PLAY:  # Если воспроизведение активно
                
                left_padding = self._chunk_size  # Левый padding для начала трека
                right_padding = self._chunk_size  # Правый padding для конца трека
                
                # Убираем левый пэдинг для старта трека
                if self._position == 0:
                    left_padding = 0
                    right_padding = self._chunk_size  # Добавляем правый пэдинг только в начале
                
                # Вырезаем сегмент волны для текущего чанка
                wave_crop = self.waveform_ref[self._position - left_padding:self._position + self._chunk_size + right_padding]
                
                if wave_crop is None or wave_crop.size == 0:  # Если трек закончился
                    self.stop()  # Останавливаем воспроизведение
                
                wave_type = wave_crop.dtype  # Определяем тип данных волны
                
                wave_crop = wave_crop.astype(np.float32) / np.iinfo(wave_type).max  # Нормализация в диапазон [-1, 1]
                
                # region EQ — Применяем эквалайзер если активен
                if self.eq_active:
                    wave_crop = equalizer_librosa(wave_crop, self.sample_rate, self.eq_gains, self.bands)
                    wave_crop = np.clip(wave_crop, -1.0, 1.0)  # Климпируем после EQ
                # endregion
                
                # Применяем громкость и возвращаем в исходный тип данных
                wave_crop = (wave_crop * self._volume)
                wave_crop = (wave_crop * np.iinfo(wave_type).max).astype(wave_type)
                
                data = wavio._array2wav(wave_crop[left_padding:self._chunk_size+left_padding], 2)  # Конвертация в формат PyAudio
                
                try:
                    self.pyaudio_stream.write(data)  # Вывод чанка в поток
                except OSError as e:  # При ошибке с устройством
                    self.switch_device()  # Переключаемся на другое устройство
                    self.pyaudio_stream.write(data)  # Повторяем вывод
                
                self._position += self._chunk_size  # Сдвигаем позицию вперед
                
                self.progress.emit(int(self._position / self.sample_rate * 1000))  # Сообщаем о прогрессе (ms)
            
            else:  # Если не PLAY — ждём короткое время
                time.sleep(0.01)
                continue
        
        self.finished.emit()  # Сообщаем о завершении воспроизведения

    def set_position(self, position: int) -> None:
        """Установка позиции воспроизведения в миллисекундах.

        :param position: Позиция в миллисекундах от начала трека.
        :returns: None.
        """
        self._position = round(position * self.sample_rate / 1000)  # Конвертация мс -> сэмплы

    def pause(self) -> None:
        """Возврат воспроизведения в состояние паузы.

        :returns: None.
        """
        self.player_state = PlayerState.PAUSE
        self.playbackStateChanged.emit(self.player_state)  # Сообщаем о смене состояния

    def play(self) -> None:
        """Запуск воспроизведения трека.

        :returns: None.
        """
        self.player_state = PlayerState.PLAY
        self.playbackStateChanged.emit(self.player_state)  # Сообщаем о смене состояния

    def stop(self) -> None:
        """Полная остановка воспроизведения.

        :returns: None.
        """
        self.player_state = PlayerState.STOP
        self.playbackStateChanged.emit(self.player_state)  # Сообщаем о смене состояния
        self._position = 0  # Сброс позиции в начало

    def set_volume(self, volume: float) -> None:
        """Установка громкости воспроизведения.

        :param volume: Значение громкости от 0 до 1 (линейное). Если log_volume=True, применяется квадратичная трансформация для логарифмического восприятия.
        :returns: None.
        """
        if self.log_volume:  # Логарифмическое отображение громкости в логах
            self._volume = math.pow(volume, 2.0)  # Компенсация нелинейности восприятия
        else:  # Линейное отображение
            self._volume = volume

    def get_volume(self) -> float:
        """Получение текущего значения громкости.

        :returns: float — Текущее значение громкости (линейное).
        """
        return self._volume
        
    def set_chunk_size(self, chunk_size: int) -> None:
        """Изменение размера буфера вывода (чанка).
        
        Аргументы:
            chunk_size (int): Новый размер чанка в сэмплах. Влияет на плавность воспроизведения.
                             Большие значения — более плавный звук, меньше задержка.
        """
        self._chunk_size = chunk_size  # Обновление размера чанка

    def get_chunk_size(self) -> int:
        """Получение текущего размера буфера вывода.

        :returns: int — Текущий размер чанка в сэмплах.
        """
        return self._chunk_size  # Возврат текущего значения

    def duration(self) -> float:
        """Получение общей длительности трека.

        :returns: float — Длительность воспроизведения в миллисекундах.
        """
        return self._duration  # Возврат вычисленной длительности
        
    @pyqtSlot(bool)
    def set_eq_active(self, eq_active: bool) -> None:
        """Включение/выключение эквалайзера во время воспроизведения.

        :param eq_active: True — активировать EQ, False — отключить. Изменение применяется к следующему чанку после выключения.
        :returns: None.
        """
        self.eq_active = eq_active  # Обновление статуса эквалайзера

    def print_all_devices(self):
        """Вывод всех доступных выходных аудиоустройств в консоль.

        :returns: None.
        """
        print_d(self.get_output_devices())  # Печать списка устройств

    @staticmethod
    def get_output_devices() -> List[Dict[str, any]]:
        """Получение списка выходных аудиоустройств системы.

        :returns: List[Dict] — Список словарей с информацией о каждом устройстве (index, name, hostapi, hostapi_name). Фильтрует только устройства с поддержкой >1 канала.
        """
        devs = sd.query_devices()  # Получаем все устройства
        
        hostapis = sd.query_hostapis()  # Информация о HostAPI системах
        
        out = []  # Список для результата
        
        for i, d in enumerate(devs):  # Проходим по всем устройствам
            if d.get("max_output_channels", 0) > 1:  # Только многоканальные устройства
                out.append({  # Добавляем устройство в список
                    "index": d.get("index"),
                    "name": d.get("name"),
                    "hostapi": d.get("hostapi"),
                    "hostapi_name": hostapis[d.get("hostapi")]["name"],
                })
        return out  # Возврат списка устройств

    @staticmethod
    def get_default_output() -> Dict[str, any]:
        """Получение информации о устройстве вывода по умолчанию.

        :returns: Dict — Словарь с информацией об устройстве (index, name, hostapi, hostapi_name).
        """
        device = sd.query_devices(kind="output")  # Получаем выходное устройство
        
        hostapis = sd.query_hostapis()  # Информация о HostAPI системах
        
        return {  # Возврат словаря с информацией об устройстве
            "index": device.get("index"),
            "name": device.get("name"),
            "hostapi": device.get("hostapi"),
            "hostapi_name": hostapis[device.get("hostapi")]["name"],
        }


