import os
import time
from typing import Dict, Union, TYPE_CHECKING, Optional, List

import librosa
import numpy as np
from PyQt6.QtCore import pyqtSlot, Qt, QPoint, QThread
from PyQt6.QtGui import (QPaintEvent, QPainter, QBrush, QColor, QMouseEvent, QLinearGradient, QPen,
                         QFont, QResizeEvent)
from PyQt6.QtWidgets import QWidget, QLabel, QPushButton, QFileDialog
from openpyxl.styles import Font, NamedStyle
from openpyxl.workbook import Workbook
from openpyxl.worksheet.worksheet import Worksheet

from src.core.log_system import print_d, print_e, print_i
from src.core.qt_widgets import EQWidget
from src.core.workers import GenrePredictWorker
from src.enums import EQType
from src.function_lib.ai import load_sess_model
from src.function_lib.math_lib import median
from src.global_constants import ONNX_INFERENCE, PROFILE, ONNX_SESS_PROVIDER, GENRE_DICT, PATTERN_SIZE

if TYPE_CHECKING:
    from src.forms import MainForm


class GenreClassifierModule(QWidget):
    def __init__(self, model_path: str, main_form, *args, **kwargs):
        super(GenreClassifierModule, self).__init__(*args, **kwargs)
        self.model_path: str = model_path
        self.setMouseTracking(True)

        self.model = None
        self.model_path = model_path

        self.mf: Union[QWidget, MainForm] = main_form
        self.graph_y: int = 60
        self.graph_height: int = 60
        self.cursor_position: float = 0.0

        self.work_thread = QThread(self)
        self.worker = GenrePredictWorker()
        self.worker.mf = self.mf
        self.worker.finished.connect(self.predict_finished)
        self.worker.preloader_signal.connect(self.mf.preloader.set_help_text)

        self.predict_button = QPushButton("Predict", self)
        self.predict_button.move(10, 5)
        self.predict_button.clicked.connect(lambda: self.predict_current())

        self.status_label = QLabel("", self)
        self.status_label.move(self.predict_button.width() + 20, 5)

        self.analysis_button = QPushButton("Анализ", self)
        self.analysis_button.move(self.status_label.x() + self.status_label.width() + 10, 5)
        self.analysis_button.clicked.connect(self.do_analysis)

        self.best_of_label = QLabel("", self)
        self.best_of_label.move(10, self.graph_y + self.graph_height + 10)

        self.genre_gradient = QLinearGradient(0, 0, self.width(), 0)
        self.genre_gradient.setColorAt(0.0, QColor("#2A2A2A"))
        self.genre_gradient.setColorAt(1.0, QColor("#2A2A2A"))
        self.global_results: Optional[list] = None
        self.drawing_text_pos: Optional[QPoint] = None

        self.eq = EQWidget(EQType.ACTIVE, self)
        self.genre_eq: Dict[int, List[float]] = {}
        self.current_genre: str = ""

        self.genre_dict: Dict[int, str] = GENRE_DICT

        self.genre_color: Dict[int, str] = {
            3: "#742CFA",
            7: "#FA474A",
            8: "#D1FA58",
            2: "#6A9EFA",
            9: "#FA7543",
            4: "#6AFAD2",
            5: "#56FA86",
            1: "#DB81FA",
            0: "#FAF550",
            6: "#ADBDFA",
        }

    def load_model(self) -> None:
        print_i(f"AI inference mode: {'ONNX' if ONNX_INFERENCE else 'PyTorch'}")
        self.model = load_sess_model(self.model_path, ONNX_SESS_PROVIDER)

    def predict_current(self) -> None:
        self.worker.moveToThread(self.work_thread)
        self.work_thread.started.connect(self.worker.run)
        self.work_thread.start()
        self.mf.show_preloader()

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self.recalc_sizes()

    def set_gradient_color(self, genre_result: List[int]) -> None:
        self.genre_gradient = QLinearGradient(0, 0, self.width(), 0)
        sample_width = self.mf.audio_player.sample_rate * PATTERN_SIZE
        for step, result in enumerate(genre_result):
            self.genre_gradient.setColorAt(
                (step * sample_width + sample_width / 2) / self.mf.audio_player.waveform.shape[0],
                QColor(self.genre_color[result]))
            self.genre_gradient.setColorAt(
                ((step + 1) * sample_width) / self.mf.audio_player.waveform.shape[0],
                QColor(self.genre_color[result]))

    def recalc_sizes(self) -> None:
        if self.global_results:
            self.set_gradient_color(self.global_results)
        self.eq.move(int(self.width() / 2 - self.eq.width() / 2),
                     self.best_of_label.y() + self.best_of_label.height() + 10)
        self.update()

    @pyqtSlot(list)
    def predict_finished(self, out: List[int]) -> None:
        if not out:
            # TODO: Сообщить о том, что выход пустой
            return
        self.set_gradient_color(out)
        self.global_results = out
        print_d(out)
        counts = np.bincount(np.array(out))

        best_of_text: str = ""
        for inx, count in enumerate(counts):
            best_of_text += (f"<span style=' font-size:8pt; font-weight: bold; color:{self.genre_color[inx]};'>"
                             f"{self.genre_dict[inx]}</span> : {round(count / counts.sum() * 100, 2)}%<br>")
        self.best_of_label.setText(best_of_text)
        self.best_of_label.adjustSize()
        self.eq.move(int(self.width() / 2 - self.eq.width() / 2),
                     self.best_of_label.y() + self.best_of_label.height() + 10)

        print_d(f"Final genre: {np.argmax(counts)}, name: {self.genre_dict[int(np.argmax(counts))]}")
        self.status_label.setText(f"<span style=' font-size:8pt; font-weight: bold; color:#4477C9;'>ИТОГ:</span> "
                                  f"{self.genre_dict[int(np.argmax(counts))]}")
        self.status_label.adjustSize()
        self.update()

        self.mf.preloader.setVisible(False)
        self.worker_reset()
        self.resize(self.width(), self.eq.y() + self.eq.height())

    def worker_reset(self) -> None:
        self.work_thread.exit(0)
        self.worker = GenrePredictWorker()
        self.worker.mf = self.mf
        self.worker.finished.connect(self.predict_finished)
        self.worker.preloader_signal.connect(self.mf.preloader.set_help_text)

    def paintEvent(self, event: QPaintEvent) -> None:
        super().paintEvent(event)
        if self.isVisible():
            start_time: float = time.time()
            painter = QPainter(self)
            painter.fillRect(0, self.graph_y, self.width(), self.graph_height, QBrush(self.genre_gradient))

            painter.setPen(QPen(QColor("#FA6900"), 1.0, Qt.PenStyle.DashLine))
            cursor_x: int = round(self.cursor_position * (self.width()))
            painter.drawLine(cursor_x, self.graph_y, cursor_x, self.graph_y + self.graph_height)

            if self.drawing_text_pos is not None and self.global_results is not None and len(self.global_results) > 0:
                painter.setPen(QPen(Qt.GlobalColor.white, 1.0, Qt.PenStyle.DashLine))
                painter.setFont(QFont("Arial", 14))
                painter.drawLine(self.drawing_text_pos.x(), self.graph_y, self.drawing_text_pos.x(),
                                 self.graph_y + self.graph_height)

                # painter.setCompositionMode(QPainter.CompositionMode.RasterOp_SourceXorDestination)
                index_factor: float = (self.drawing_text_pos.x()) / (self.width())
                index: int = median(0, round((len(self.global_results) - 1) * index_factor), len(self.global_results) - 1)
                genre_text: str = self.genre_dict[self.global_results[index]]
                genre_text_width: int = painter.fontMetrics().boundingRect(genre_text).width()
                text_pos_x = int(self.drawing_text_pos.x() - genre_text_width/2)
                painter.drawText(median(0, text_pos_x, self.width() - genre_text_width - 10),
                                 self.graph_y - 10, genre_text)
                # painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
            elif self.global_results:
                painter.setPen(QPen(Qt.GlobalColor.white, 1.0, Qt.PenStyle.DashLine))
                painter.setFont(QFont("Arial", 14))
                # index: int = median(0, round((len(self.global_results) - 1) * self.cursor_position), len(self.global_results) - 1)
                # genre_text: str = self.genre_dict[self.global_results[index]]
                genre_text_width: int = painter.fontMetrics().boundingRect(self.current_genre).width()
                painter.drawText(median(0, int(cursor_x - genre_text_width / 2), self.width() - genre_text_width - 10),
                                 self.graph_y - 10, self.current_genre)
            if PROFILE:
                self.mf.profiling.add_draw_time(self.__class__.__name__, time.time() - start_time)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        super().mouseMoveEvent(event)
        if self.graph_y <= event.pos().y() <= self.graph_y + self.graph_height:
            self.drawing_text_pos = event.pos()
        else:
            self.drawing_text_pos = None
        self.update()

    def leaveEvent(self, a0) -> None:
        self.drawing_text_pos = None
        self.update()

    def do_analysis(self) -> None:
        file_path = QFileDialog.getExistingDirectory(self, 'Путь к директории, где музыка по жанрам')
        if not file_path:
            return

        wb = Workbook()
        sheet: Worksheet = wb.active
        sheet.title = 'Analysis'
        # analysis_sheet = wb.create_sheet("Analysis")
        sheet["A1"] = "Анализ"
        header1_style = NamedStyle("Header1", Font(bold=True, size=12))
        header2_style = NamedStyle("Header2", Font(bold=True, size=11))

        for index, genre in enumerate(self.genre_dict.values()):
            sheet[f"{chr(65 + index + 1)}2"] = genre
            sheet[f"{chr(65 + index + 1)}2"].style = header1_style
        sheet[f"{chr(65 + 11)}2"] = "Итог"
        sheet[f"{chr(65 + 11)}2"].style = header1_style
        sheet.column_dimensions[chr(65)].width = 50

        data_begin_index: int = 3
        row_count: int = 0
        for root, _, files in os.walk(file_path):
            folder_name: str = ""
            if files:
                folder_name = os.path.basename(root)
                sheet[f"A{data_begin_index + row_count}"] = folder_name
                sheet[f"A{data_begin_index + row_count}"].style = header2_style
                row_count += 1
            for file_index, _file in enumerate(files):
                print_d(folder_name, _file)
                sheet[f"A{data_begin_index + row_count + file_index}"] = _file
                file_path = os.path.join(root, _file)

                waveform, sample_rate = librosa.load(file_path)

                self.work_thread.exit(0)
                self.worker = GenrePredictWorker()
                self.worker.mf = self.mf
                self.worker.waveform = waveform
                self.worker.sample_rate = sample_rate

                results = self.worker.run()

                for col in range(len(self.genre_dict.values())):
                    sheet[f"{chr(65 + 1 + col)}{data_begin_index + row_count + file_index}"] = 0.0

                counts = np.bincount(np.array(results))
                print(results, counts)
                for count_index, count in enumerate(counts):
                    percents = round(count / counts.sum() * 100, 2)
                    sheet[f"{chr(65 + 1 + count_index)}{data_begin_index + row_count + file_index}"] = percents
                sheet[f"{chr(65 + 11)}{data_begin_index + row_count + file_index}"] = self.genre_dict[int(np.argmax(counts))]
            row_count += len(files)

        wb.save('data/local/analysis.xlsx')

    def reset_result(self) -> None:
        self.global_results = None
        self.genre_gradient = QLinearGradient(0, 0, self.width(), 0)
        self.genre_gradient.setColorAt(0.0, QColor("#2A2A2A"))
        self.genre_gradient.setColorAt(1.0, QColor("#2A2A2A"))
        self.best_of_label.setText("")
        self.best_of_label.adjustSize()
        self.recalc_sizes()

    @pyqtSlot(float)
    def set_cursor_position(self, position: float) -> None:
        self.cursor_position = position
        if self.global_results is not None:
            position *= self.mf.audio_player.waveform[:, 0].size
            genre: int = self.global_results[int(position / self.mf.audio_player.sample_rate / PATTERN_SIZE)]
            self.current_genre = self.genre_dict[genre]
            if self.eq.auto_eq:
                gains: np.ndarray = np.array(self.genre_eq[genre])
                self.eq.set_sliders((gains * self.eq.accuracy).astype(np.uint16), interpolation=True)
        self.update()

    @pyqtSlot(dict)
    def on_preset_changed(self, presets: dict) -> None:
        self.genre_eq = presets



