from typing import TYPE_CHECKING, Optional

from PyQt6.QtCore import QEvent
from PyQt6.QtGui import QResizeEvent
from PyQt6.QtWidgets import QWidget, QTabWidget

from src.global_constants import EXPERIMENTAL_MODULES
from .LyricsPropertyCommon_class import LyricsPropertyCommon
from ...global_styles import AppColorSchemes

# Imported only when enabled, so the requests package stays optional
if EXPERIMENTAL_MODULES:
    from .SummariserModule_class import SummariserModule

if TYPE_CHECKING:
    from src.forms import MainForm


class TranscriptionPropertyModule(QWidget):
    """Right side panel of the lyrics tab.

    Always shows the Common page. The Summarization page needs the external service
    and appears only when EXPERIMENTAL_MODULES is on.
    """

    def __init__(self, mf, lyric_module, *args, **kwargs):
        """Build the panel and its pages.

        :param mf: Main form reference.
        :param lyric_module: Owning AudioLyricsModule.
        :returns: None.
        """
        super().__init__(*args, **kwargs)
        self.mf: MainForm = mf

        self.common_lyrics_property = LyricsPropertyCommon(self.mf, lyric_module)

        self.tab_widget = QTabWidget(self)
        self.tab_widget.setStyleSheet(f"""
            QWidget{{
                background-color: {AppColorSchemes.FILE_LIST_BACKGROUND};
                color: black;
            }}
            QTabWidget{{
                background-color: {AppColorSchemes.FILE_LIST_BACKGROUND};
                padding: 0px;
            }}
            QTabBar::tab {{
                color: black;
                background-color: #e0e0e0;
                border: 1px solid #939393;
                border-bottom-color: {AppColorSchemes.FILE_LIST_BACKGROUND};
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                min-width: 50px;
                min-height: 20px;
                padding: 0px 2px;
                margin-left: 1px;
            }}

            QTabBar::tab:selected {{
                color: black;
                background-color: {AppColorSchemes.FILE_LIST_BACKGROUND};
                border-bottom-color: {AppColorSchemes.FILE_LIST_BACKGROUND};
                font-weight: bold;
            }}

            QTabBar::tab:disabled {{
                color: gray;
            }}
        """)
        self.common_tab_index = self.tab_widget.addTab(self.common_lyrics_property, "")

        self.summariser: Optional[QWidget] = None
        self.summariser_tab_index: Optional[int] = None
        if EXPERIMENTAL_MODULES:
            self.summariser = SummariserModule(self.mf, lyric_module)
            self.summariser_tab_index = self.tab_widget.addTab(self.summariser, "")

        self.retranslate_ui()

    def changeEvent(self, event: QEvent) -> None:
        """Reapply the texts when the application language changes.

        :param event: Qt event.
        :returns: None.
        """
        if event.type() == QEvent.Type.LanguageChange:
            self.retranslate_ui()
        super().changeEvent(event)

    def retranslate_ui(self) -> None:
        """Apply the current translation to the tab captions.

        :returns: None.
        """
        self.tab_widget.setTabText(self.common_tab_index, self.tr("Common"))
        if self.summariser_tab_index is not None:
            self.tab_widget.setTabText(self.summariser_tab_index, self.tr("Summarization"))

    def resizeEvent(self, event: QResizeEvent) -> None:
        """Fit the tab widget to the panel.

        :param event: Qt resize event.
        :returns: None.
        """
        super().resizeEvent(event)
        self.tab_widget.resize(self.width(), self.height())