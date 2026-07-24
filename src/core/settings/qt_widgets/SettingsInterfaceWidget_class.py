from typing import TYPE_CHECKING, List

from PyQt6.QtCore import pyqtSlot, QEvent
from PyQt6.QtWidgets import QWidget, QComboBox, QFormLayout, QLabel

from src.core.i18n import translation_manager

if TYPE_CHECKING:
    from src.forms import MainForm


class SettingsInterfaceWidget(QWidget):
    """Settings page with the interface language selector.

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

        self.form_layout = QFormLayout(self)

        self.language_combo = QComboBox()
        self.language_combo.currentIndexChanged.connect(self.on_language_changed)

        self.language_label = QLabel("")
        self.hint_label = QLabel("")
        self.hint_label.setWordWrap(True)

        self.form_layout.addRow(self.language_label, self.language_combo)
        self.form_layout.addRow(self.hint_label)

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
        self.language_label.setText(self.tr("Interface language"))
        self.hint_label.setText(self.tr("The language is applied immediately and is saved between runs."))