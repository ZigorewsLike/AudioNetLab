from PyQt6.QtCore import pyqtSlot, QPoint, Qt
from PyQt6.QtGui import QPaintEvent, QPainter, QColor, QMouseEvent, QIcon, QPixmap, QResizeEvent
from PyQt6.QtWidgets import QWidget, QLabel, QMenuBar, QPushButton

from src.function_lib.math_lib import median
from src.global_constants import RESOURCE_ICON_DIR
from src.global_styles import AppColorSchemes


class TitleBar(QWidget):

    def __init__(self, *args, **kwargs):
        super(TitleBar, self).__init__(*args, **kwargs)
        self.resize(900, 46)
        self.setMouseTracking(True)
        self.setAutoFillBackground(True)

        self.menu_bar = QMenuBar(self)
        self.menu_bar.move(56, 0)
        self.menu_bar.resize(100, 40)

        self.parent().installEventFilter(self)

        self.setStyleSheet("""
        QMenuBar {
            background-color: transparent;
            spacing: 1px; /* spacing between menu bar items */
            color: black;
            font-family: Arimo; 
            font-size: 12px;
        }
        
        QMenuBar::item {
            padding: 16px 5px;
            background: transparent;
            border-radius: 0px;
        }
        
        QMenuBar::item:selected { /* when selected using mouse or keyboard */
            background: #a8a8a8;
        }
        
        QMenuBar::item:pressed {
            background: #888888;
        }
        
        QPushButton#TitleButtons, QPushButton#TitleButtonsClose{
            color: #666666;
            background: transparent;
            border: 0px;
        }
        QPushButton#TitleButtons:hover{
            background: #9C9C9C;
        }
        QPushButton#TitleButtonsClose:hover{
            background: #C22024;
            color: white;
        }
        """)

        self._pixmap = QPixmap(RESOURCE_ICON_DIR + "app_logo.png")
        self._pixmap = self._pixmap.scaled(30, 30)
        self.icon_logo = QLabel("", self)
        self.icon_logo.resize(30, 30)
        self.icon_logo.setPixmap(self._pixmap)
        self.icon_logo.move(6, 6)

        self.button_width: int = 45

        self.button_minimize = QPushButton("", self)
        self.button_minimize.setIcon(QIcon(RESOURCE_ICON_DIR + "minimize_button.png"))
        self.button_minimize.clicked.connect(self.hide_window)
        self.button_minimize.setObjectName("TitleButtons")
        self.button_minimize.resize(self.button_width, self.height())
        self.button_minimize.setIconSize(self.button_minimize.size())

        self.button_maximize = QPushButton("", self)
        self.button_maximize.setIcon(QIcon(RESOURCE_ICON_DIR + "maximize_button.png"))
        self.button_maximize.clicked.connect(self.maximize_window)
        self.button_maximize.setObjectName("TitleButtons")
        self.button_maximize.resize(self.button_width, self.height())
        self.button_maximize.setIconSize(self.button_maximize.size())

        self.button_close = QPushButton("", self)
        self.button_close.setIcon(QIcon(RESOURCE_ICON_DIR + "close_button.png"))
        self.button_close.clicked.connect(self.close_window)
        self.button_close.setObjectName("TitleButtonsClose")
        self.button_close.resize(self.button_width, self.height())
        self.button_close.setIconSize(self.button_close.size())

        self.is_pressing: bool = False
        self.is_maximize: bool = False
        self.press_point: QPoint = QPoint()

    @pyqtSlot()
    def hide_window(self) -> None:
        self.parent().showMinimized()

    @pyqtSlot()
    def maximize_window(self) -> None:
        if self.parent().windowState() is Qt.WindowState.WindowMaximized:
            self.parent().setWindowState(Qt.WindowState.WindowNoState)
        else:
            self.parent().setWindowState(Qt.WindowState.WindowMaximized)
        self.parent().windowStateChanged.emit()  # noqa

    @pyqtSlot()
    def close_window(self) -> None:
        self.parent().close()

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self.menu_bar.adjustSize()
        self.button_close.move(self.width() - self.button_close.width(), 0)
        self.button_maximize.move(self.width() - self.button_close.width() * 2, 0)
        self.button_minimize.move(self.width() - self.button_close.width() * 3, 0)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        super().mousePressEvent(event)
        if event.button() == Qt.MouseButton.LeftButton:
            self.is_pressing = True
            self.press_point = event.pos()
            self.parent().block_update = False

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        super().mousePressEvent(event)
        self.is_pressing = False
        self.parent().block_update = False

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        super().mouseMoveEvent(event)
        if self.is_pressing:
            if self.parent().windowState() is not Qt.WindowState.WindowNoState:
                delta_size = self.parent().settings.system_settings.form_width  # noqa
                self.parent().setWindowState(Qt.WindowState.WindowNoState)
                self.parent().windowStateChanged.emit()  # noqa
                self.parent().move(median(0, self.press_point.x() - delta_size // 2, self.parent().width() - delta_size), 1)
                self.update()
            else:
                self.parent().window().windowHandle().startSystemMove()

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        self.maximize_window()

    def paintEvent(self, event: QPaintEvent) -> None:
        super().paintEvent(event)
        painter = QPainter(self)
        painter.fillRect(0, 0, self.width(), self.height(), QColor(AppColorSchemes.SCROLLBAR_BACKGROUND))



