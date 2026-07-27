from typing import TYPE_CHECKING, List

from PyQt6.QtCore import pyqtSlot, QEvent
from PyQt6.QtWidgets import QWidget, QCheckBox, QComboBox, QLabel, QVBoxLayout

from src.core.i18n import translation_manager
from src.core.settings.qt_widgets.SettingsSection_class import SettingsSection

if TYPE_CHECKING:
    from src.forms import MainForm


class SettingsInterfaceWidget(QWidget):
    """Settings page with the interface language selector and library click behaviour.

    Switching the language installs another translator right away, every widget
    reapplies its texts through the LanguageChange event, no restart is needed.
    """

    def __init__(self, mf, *args, **kwargs):
        """Build the language form.

        :param mf: Main form reference.
        :returns: None.
        """
        super().__init__(*args, **kwargs)
        self.mf: MainForm = mf
        self.language_codes: List[str] = []

        root = QVBoxLayout(self)

        self.language_section = SettingsSection(self)
        self.language_combo = QComboBox()
        self.language_combo.currentIndexChanged.connect(self.on_language_changed)
        self.hint_label = QLabel("")
        self.hint_label.setWordWrap(True)
        self.language_section.add_full_row(self.language_combo)
        self.language_section.add_full_row(self.hint_label)

        self.library_section = SettingsSection(self)
        self.double_click_label = QLabel("")
        self.double_click_label.setWordWrap(True)
        self.double_click_check = QCheckBox()
        self.double_click_check.toggled.connect(self.on_double_click_toggled)
        self.library_section.add_full_row(self.double_click_label)
        self.library_section.add_full_row(self.double_click_check)

        root.addWidget(self.language_section)
        root.addWidget(self.library_section)
        root.addStretch(1)

        self.load_data()
        self.retranslate_ui()

    def load_data(self) -> None:
        """Fill the combo box with the available languages and select the active one.

        :returns: None.
        """
        self.language_combo.blockSignals(True)  # Filling the list must not trigger a switch
        self.language_combo.clear()
        self.language_codes = []
        for code, name in translation_manager.available_languages().items():
            self.language_codes.append(code)
            self.language_combo.addItem(name)
        current = translation_manager.current_language
        if current in self.language_codes:
            self.language_combo.setCurrentIndex(self.language_codes.index(current))
        self.language_combo.blockSignals(False)

        self.double_click_check.blockSignals(True)
        self.double_click_check.setChecked(self.mf.settings.library_settings.open_on_double_click)
        self.double_click_check.blockSignals(False)

    @pyqtSlot(bool)
    def on_double_click_toggled(self, checked: bool) -> None:
        """Store the open gesture and apply it to the library grids at once.

        :param checked: True to open albums and artists on a double click.
        :returns: None.
        """
        self.mf.settings.library_settings.open_on_double_click = checked
        library = getattr(self.mf, "library_widget", None)
        if library is not None:
            library.set_open_on_double_click(checked)

    @pyqtSlot(int)
    def on_language_changed(self, index: int) -> None:
        """Apply the selected language and remember it in the settings.

        :param index: Index in the combo box.
        :returns: None.
        """
        if index < 0 or index >= len(self.language_codes):
            return
        language = self.language_codes[index]
        applied = translation_manager.set_language(language)
        self.mf.settings.system_settings.language = applied

    def changeEvent(self, event: QEvent) -> None:
        """Reapply the texts when the application language changes.

        :param event: Qt event.
        :returns: None.
        """
        if event.type() == QEvent.Type.LanguageChange:
            self.retranslate_ui()
        super().changeEvent(event)

    def retranslate_ui(self) -> None:
        """Apply the current translation to the texts of this page.

        :returns: None.
        """
        self.language_section.set_title(self.tr("Interface language"))
        self.hint_label.setText(self.tr("The language is applied immediately and is saved between runs."))
        self.library_section.set_title(self.tr("Library"))
        self.double_click_label.setText(
            self.tr("By default albums and artists in the library open on a single click."))
        self.double_click_check.setText(self.tr("Open them on a double click instead"))