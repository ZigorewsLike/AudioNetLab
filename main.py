"""Application entry point: sets up logging, DPI and the main window."""
import ctypes
import os
import sys
import traceback
import tracemalloc
from datetime import datetime

from PyQt6.QtCore import Qt

from src.core.i18n import translation_manager
from src.core.log_system import print_e, print_d, OutputBuffer
from src.core.settings import SettingsDataObject
from src.global_constants import (APP_NAME, DEBUG, APP_ROAMING_DIR, TRACE, LOG_IN_FILE, PATH_TO_LAST_REGISTRY,
                                  CONFIG_FILENAME)

from PyQt6.QtGui import QIcon
from PyQt6 import QtWidgets
from PyQt6.QtWidgets import QMessageBox
from src.forms import MainForm

import warnings

warnings.filterwarnings('ignore')
if TRACE:
    tracemalloc.start(1)

os.system('cls')
os.environ['QT_MULTIMEDIA_PREFERRED_PLUGINS'] = 'windowsmediafoundation'


def except_hook(exc_type, exc_value, exc_tb):
    """Log an uncaught exception into error_log.txt and show it in a dialog.

    :param exc_type: Exception class.
    :param exc_value: Exception instance.
    :param exc_tb: Traceback object.
    :returns: None.
    """
    tb = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
    print_e("Some error:\n", tb, '\033[0m')

    with open('error_log.txt', 'a') as error_f:
        error_f.write(f"\n{datetime.now()} : {tb} \n {'#'*10} \n")

    error_critical_msg = QMessageBox()
    error_critical_msg.setText(f"{tb}")
    error_critical_msg.setIcon(QMessageBox.Icon.Critical)
    error_critical_msg.setWindowTitle(f'Critical Error: {exc_value}.')
    error_critical_msg.setStandardButtons(QMessageBox.StandardButton.Ok)
    error_critical_msg.exec()
    if not DEBUG:  # In debug the app keeps running so the state can be inspected
        QtWidgets.QApplication.quit()


if __name__ == '__main__':
    # Intercept uncaught errors and stdout
    sys.excepthook = except_hook
    sys.stdout = OutputBuffer()

    # region Create the directories and files the application needs
    for dir_name in ["data/local/", PATH_TO_LAST_REGISTRY]:
        os.makedirs(dir_name, exist_ok=True)
    os.makedirs(APP_ROAMING_DIR, exist_ok=True)
    if LOG_IN_FILE:
        os.makedirs('logs', exist_ok=True)
    # endregion

    # region Detect the DPI of monitors scaled above 100%
    user32 = ctypes.windll.user32
    w_curr = user32.GetSystemMetrics(0)  # Scaled width
    user32.SetProcessDPIAware()
    w_phys = user32.GetSystemMetrics(0)  # Physical width
    curr_dpi = round(w_phys * 96 / w_curr, 0)
    # endregion

    print_d("curr_dpi: ", curr_dpi, w_curr, w_phys)

    # region Application setup: name, icon, scaling policy and style
    app = QtWidgets.QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setWindowIcon(QIcon('Icon.ico'))
    app.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app.setStyle("fusion")
    screen = app.primaryScreen()
    size = screen.size()
    # endregion

    # The language must be installed before the first widget is built
    startup_settings = SettingsDataObject()
    startup_settings.load_from_ini(CONFIG_FILENAME)
    translation_manager.set_language(startup_settings.system_settings.language)

    # Window parameters (width and height of the screen)
    params_dist: dict = {"size_width": size.width(), "size_height": size.height()}
    mainWin = MainForm(params_dist)
    app.processEvents()
    mainWin.load_ann_models()

    mainWin.show()
    app.exec()
    # Restore the original stdout (OutputBuffer method)
    sys.stdout.reset()
    tracemalloc.stop()