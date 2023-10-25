import os

DEBUG = True
TRACE = False
LOG_IN_FILE = False
LOG_IN_SIGNAL = False

APP_NAME = "AudioNetLab"
APP_TITLE = f"{APP_NAME}"
VERSION = "0.0.0.1"

APP_ROAMING_DIR = os.path.join(os.getenv('APPDATA'), APP_NAME)
CONFIG_FILENAME = "config_app.ini"
