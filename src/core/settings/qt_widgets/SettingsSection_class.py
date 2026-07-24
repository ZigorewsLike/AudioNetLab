from typing import List, Tuple

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QResizeEvent, QPaintEvent, QPainter, QPen, QColor, QShowEvent
from PyQt6.QtWidgets import QFrame, QLabel, QWidget, QScrollArea

from src.core.log_system import print_d
from src.global_styles import DEFAULT_CHECKBOX_BLACK_STYLE


class SectionWidget(QFrame):
    """Frame that lays its widgets out in rows. Currently unused."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.widget_parent: QWidget = self
        self._widget_container: List[List[QWidget]] = []
        self.widget_padding: Tuple[int, int] = (0, 0)  # Left, Top
        self.widget_spacing: Tuple[int, int] = (0, 0)  # Left, Top
        self.fixed_height: int = 0

    def add_widget(self, *widgets: QWidget) -> None:
        for widget in widgets:
            widget.setParent(self.widget_parent)
        self._widget_container.append(list(widgets))

    def reposition_widgets(self) -> None:
        height_sum: int = self.widget_padding[1]
        for index, widget_list in enumerate(self._widget_container):
            height_max: int = max(widget_list, key=lambda x: x.height()).height()
            width_sum: int = self.widget_padding[0]
            for col, widget in enumerate(widget_list):
                widget.adjustSize()
                if self.fixed_height != 0:
                    widget.move(width_sum,
                                height_sum - (widget.height() - height_max) // 2 - (height_max - self.fixed_height)//2)
                else:
                    widget.move(width_sum,
                                height_sum - (widget.height() - height_max) // 2)

                width_sum += widget.width() + self.widget_spacing[0]
            height_sum += height_max + self.widget_spacing[1]


class SettingsSection(SectionWidget):
    """Settings section with a title bar. Currently unused."""

    def __init__(self, title: str, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setFrameStyle(QFrame.Shape.Panel | QFrame.Shadow.Raised)
        self.title_height: int = 40
        self.background_color: str = "#989599"
        self.custom_widget_style: bool = True

        self.update_stylesheet()

        self.frame_header = QFrame(self)
        self.frame_header.setObjectName("header")
        # self.frame_header.setFrameStyle(QFrame.Panel | QFrame.Raised)

        self.title_label = QLabel(title, self.frame_header)
        self.title_label.setStyleSheet("""
        QLabel{
            font-size: 12pt;
        }
        """)
        self.title_label.adjustSize()
        self.title_label.move(10, 10)

        self.frame_widgets = QFrame()
        self.frame_widgets.setObjectName("body")
        self.frame_widgets.setStyleSheet("""
        QFrame{
            background-color: transparent;
        }
        """)

        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidget(self.frame_widgets)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.scroll_area.move(0, self.title_height)

        self.widget_padding: Tuple[int, int] = (15, 15)  # Left, Top
        self.widget_spacing: Tuple[int, int] = (10, 20)  # Left, Top
        self.widget_parent = self.frame_widgets

    def update_stylesheet(self) -> None:
        style_sheet = """
                SettingsSection{
                    background-color: """ + self.background_color + """;
                }
                SettingsSection > QFrame#header{
                    border-left: 1px solid #6E6E6E
                }
                QLabel{
                    background-color: transparent;
                    font-size: 10pt;
                }
                QScrollArea{
                    background-color: transparent;
                }
                """ + DEFAULT_CHECKBOX_BLACK_STYLE
        if self.custom_widget_style:
            style_sheet += """
                QSpinBox, QLineEdit{
                    background-color: """ + self.background_color + """;
                }
                """
        self.setStyleSheet(style_sheet)

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self.frame_header.resize(self.width(), self.title_height)
        self.scroll_area.resize(self.width(), self.height() - self.title_height)

    def adjustSize(self) -> None:
        self.reposition_widgets()
        super().adjustSize()
        self.frame_widgets.adjustSize()

    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        self.reposition_widgets()
        self.frame_widgets.adjustSize()
        self.scroll_area.move(0, self.title_height)


class SettingsSubSection(SectionWidget):
    """Nested settings section without a frame. Currently unused."""

    def __init__(self, title: str, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setStyleSheet("""
        SettingsSubSection, QLabel{
            background-color: transparent;
        }
        QSpinBox{
            background-color: #989599;
        }
        QTextEdit {
            border: 1px solid #535353;
        }
        QSlider{
            background-color: transparent;
        }
        """ + DEFAULT_CHECKBOX_BLACK_STYLE)

        self.title_label = QLabel(title, self)
        self.title_label.setStyleSheet("""
                        QLabel{
                            font-size: 12pt;
                        }
                        """)
        self.title_label.adjustSize()
        self.title_label.move(10, 0)

        self.widget_padding: Tuple[int, int] = (20, 30)  # Left, Top
        self.widget_spacing: Tuple[int, int] = (10, 15)  # Left, Top
        self.fixed_height: int = 20

    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        self.reposition_widgets()
        self.adjustSize()

    def set_title_text(self, text: str) -> None:
        self.title_label.setText(text)
        self.title_label.adjustSize()

    def adjustSize(self) -> None:
        self.reposition_widgets()
        super().adjustSize()

    def paintEvent(self, event: QPaintEvent) -> None:
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        painter.setPen(QPen(QColor("#6E6E6E"), 1, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap,
                            Qt.PenJoinStyle.RoundJoin))
        painter.drawLine(0, 0, 2, 0)
        painter.drawLine(0, 0, 0, self.height()-1)
        painter.drawLine(0, self.height()-1, 2, self.height()-1)
