import os
from typing import Dict, List, Optional

from PyQt6.QtCore import QCoreApplication, QLibraryInfo, QLocale, QTranslator

from src.core.log_system import print_d, print_e
from src.global_constants import I18N_DIR, LANGUAGE_NAMES, SOURCE_LANGUAGE


class TranslationManager:
    """Loads the application and the Qt translations and switches them at runtime.

    Installing a QTranslator makes Qt post a LanguageChange event to every widget,
    so a widget only has to reapply its texts in changeEvent. Two catalogs are used:
    the application one from res/i18n and the Qt one bundled with PyQt6, which covers
    the standard dialog buttons.
    """

    def __init__(self):
        """Create the manager without loading anything yet.

        :returns: None.
        """
        self._app_translator: Optional[QTranslator] = None
        self._qt_translator: Optional[QTranslator] = None
        self._current_language: str = SOURCE_LANGUAGE

    @property
    def current_language(self) -> str:
        """Language code currently applied.

        :returns: str - Language code, for example "en" or "ru".
        """
        return self._current_language

    @staticmethod
    def system_language() -> str:
        """Language code of the operating system locale.

        :returns: str - Two letter language code.
        """
        return QLocale.system().name().split("_")[0]

    @staticmethod
    def available_languages() -> Dict[str, str]:
        """Languages that can be selected, the source language plus every compiled catalog.

        :returns: Dict[str, str] - Display name per language code.
        """
        languages: Dict[str, str] = {SOURCE_LANGUAGE: LANGUAGE_NAMES.get(SOURCE_LANGUAGE, SOURCE_LANGUAGE)}
        if os.path.isdir(I18N_DIR):
            for file_name in sorted(os.listdir(I18N_DIR)):
                if not file_name.endswith(".qm"):
                    continue
                code = os.path.splitext(file_name)[0].split("_")[-1]
                languages[code] = LANGUAGE_NAMES.get(code, code)
        return languages

    def resolve_language(self, language: str) -> str:
        """Turn a stored setting into a language that can actually be loaded.

        :param language: Language code, or an empty string to follow the system locale.
        :returns: str - Available language code, falls back to the source language.
        """
        if not language:
            language = self.system_language()
        if language in self.available_languages():
            return language
        return SOURCE_LANGUAGE

    def set_language(self, language: str) -> str:
        """Apply a language to the whole application.

        :param language: Language code, or an empty string to follow the system locale.
        :returns: str - Language code that was actually applied.
        """
        language = self.resolve_language(language)
        app = QCoreApplication.instance()
        if app is None:
            print_e("Unable to set language, QApplication does not exist")
            return self._current_language

        for translator in (self._app_translator, self._qt_translator):
            if translator is not None:
                app.removeTranslator(translator)
        self._app_translator = None
        self._qt_translator = None

        # The source language needs no catalog, removing the translators is enough
        if language != SOURCE_LANGUAGE:
            self._app_translator = self._load_app_translator(language)
            if self._app_translator is not None:
                app.installTranslator(self._app_translator)
            self._qt_translator = self._load_qt_translator(language)
            if self._qt_translator is not None:
                app.installTranslator(self._qt_translator)

        self._current_language = language
        print_d(f"Language set to '{language}'")
        return language

    @staticmethod
    def _load_app_translator(language: str) -> Optional[QTranslator]:
        """Load the application catalog res/i18n/audionetlab_<language>.qm.

        :param language: Language code.
        :returns: QTranslator - Loaded translator, None when the catalog is missing.
        """
        translator = QTranslator()
        path = os.path.join(I18N_DIR, f"audionetlab_{language}.qm")
        if translator.load(path):
            return translator
        print_e(f"Translation catalog not found: {path}")
        return None

    @staticmethod
    def _load_qt_translator(language: str) -> Optional[QTranslator]:
        """Load the Qt catalog bundled with PyQt6 for the standard dialogs.

        :param language: Language code.
        :returns: QTranslator - Loaded translator, None when Qt has no such catalog.
        """
        translator = QTranslator()
        qt_path = QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)
        if translator.load(f"qtbase_{language}", qt_path):
            return translator
        return None


translation_manager: TranslationManager = TranslationManager()