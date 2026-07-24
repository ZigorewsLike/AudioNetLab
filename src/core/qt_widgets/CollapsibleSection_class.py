
from PyQt6 import QtCore
from PyQt6.QtWidgets import QWidget, QToolButton, QFrame, QSizePolicy, QScrollArea, QGridLayout, QLayout


class CollapsibleSection(QWidget):
    """Section with a header that expands and collapses its content with an animation."""

    def __init__(self, title: str = "", animation_duration: int = 30, parent=None):
        super().__init__(parent)

        self._animation_duration = animation_duration

        self.toggle_button = QToolButton(text=title, checkable=True, checked=False)
        self.toggle_button.setToolButtonStyle(
            QtCore.Qt.ToolButtonStyle.ToolButtonTextBesideIcon
        )
        self.toggle_button.setArrowType(QtCore.Qt.ArrowType.RightArrow)
        self.toggle_button.setStyleSheet("QToolButton { border: none; }")

        self.header_line = QFrame()
        self.header_line.setFrameShape(QFrame.Shape.HLine)
        self.header_line.setFrameShadow(QFrame.Shadow.Sunken)
        self.header_line.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Maximum,
        )

        self.content_area = QScrollArea()
        self.content_area.setStyleSheet("QScrollArea { border: none; }")
        self.content_area.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        self.content_area.setMaximumHeight(0)
        self.content_area.setMinimumHeight(0)
        self.content_area.setWidgetResizable(True)

        self.toggle_animation = QtCore.QParallelAnimationGroup(self)
        self.toggle_animation.addAnimation(QtCore.QPropertyAnimation(self, b"minimumHeight"))
        self.toggle_animation.addAnimation(QtCore.QPropertyAnimation(self, b"maximumHeight"))
        self.toggle_animation.addAnimation(QtCore.QPropertyAnimation(self.content_area, b"maximumHeight"))

        layout = QGridLayout(self)
        layout.setVerticalSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)

        row = 0
        layout.addWidget(self.toggle_button, row, 0, 1, 1, QtCore.Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(self.header_line, row, 1, 1, 1)
        row += 1
        layout.addWidget(self.content_area, row, 0, 1, 2)

        self.toggle_button.toggled.connect(self._on_toggled)

    def _on_toggled(self, checked: bool):
        self.toggle_button.setArrowType(
            QtCore.Qt.ArrowType.DownArrow if checked else QtCore.Qt.ArrowType.RightArrow
        )
        self.toggle_animation.setDirection(
            QtCore.QAbstractAnimation.Direction.Forward
            if checked
            else QtCore.QAbstractAnimation.Direction.Backward
        )
        self.toggle_animation.start()

    def set_content(self, content_widget: QWidget):
        # Внутри QScrollArea должен быть widget, а layout ставим на него
        self.content_area.setWidget(content_widget)

        collapsed_height = self.sizeHint().height() - self.content_area.maximumHeight()
        content_height = content_widget.height()

        for i in range(self.toggle_animation.animationCount() - 1):
            anim = self.toggle_animation.animationAt(i)
            anim.setDuration(self._animation_duration)
            anim.setStartValue(collapsed_height)
            anim.setEndValue(collapsed_height + content_height)

        content_anim = self.toggle_animation.animationAt(self.toggle_animation.animationCount() - 1)
        content_anim.setDuration(self._animation_duration)
        content_anim.setStartValue(0)
        content_anim.setEndValue(content_height)


# if __name__ == "__main__":
#     import sys
#
#     app = QApplication(sys.argv)
#
#     w = QWidget()
#     root = QVBoxLayout(w)
#
#     section = CollapsibleSection("Доп. настройки", animation_duration=20)
#
#     form = QFormLayout()
#     form.addRow("Host:", QLineEdit("localhost"))
#     form.addRow("Port:", QSpinBox())
#     form.addRow("", QPushButton("Применить"))
#     section.set_content_layout(form)
#
#     root.addWidget(QLabel("Контент сверху"))
#     root.addWidget(section)
#     root.addStretch(1)
#
#     w.resize(420, 240)
#     w.show()
#
#     sys.exit(app.exec())

