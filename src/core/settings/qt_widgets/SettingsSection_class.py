from typing import Optional, Union

from PyQt6.QtWidgets import QFormLayout, QLabel, QLayout, QVBoxLayout, QWidget


class SettingsSection(QWidget):
    """A titled group of settings: a bold, slightly larger header over a form body.

    Sections stack vertically inside a page to give it visual structure. Everything is
    laid out by Qt, so a longer translation, a wrapped line or DPI scaling need no manual
    positioning. The title is set through set_title so a page can retranslate it.
    """

    def __init__(self, parent: Optional[QWidget] = None):
        """Build an empty section with a header and a form body.

        :param parent: Parent widget.
        :returns: None.
        """
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 14)
        root.setSpacing(6)

        self.header = QLabel("", self)
        font = self.header.font()
        base = font.pointSize() if font.pointSize() > 0 else 9
        font.setPointSize(base + 2)
        font.setBold(True)
        self.header.setFont(font)

        self.form = QFormLayout()
        self.form.setContentsMargins(10, 0, 0, 0)  # Indent the rows under the header

        root.addWidget(self.header)
        root.addLayout(self.form)

    def set_title(self, text: str) -> None:
        """Set the header text.

        :param text: Section title.
        :returns: None.
        """
        self.header.setText(text)

    def add_row(self, label: Union[str, QWidget], field: Union[QWidget, QLayout]) -> None:
        """Add a labelled row: a caption on the left, a control on the right.

        :param label: Row caption or a widget used as the label.
        :param field: Control widget or a layout of controls.
        :returns: None.
        """
        self.form.addRow(label, field)

    def add_full_row(self, content: Union[QWidget, QLayout]) -> None:
        """Add a row that spans the whole width, with no separate caption column.

        :param content: Widget or layout to place across the row.
        :returns: None.
        """
        self.form.addRow(content)