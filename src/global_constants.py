import os

DEBUG = True
TRACE = False
LOG_IN_FILE = False
LOG_IN_SIGNAL = False
AI_ENABLED = True
ONNX_INFERENCE = True

APP_NAME = "AudioNetLab"
APP_TITLE = f"{APP_NAME}"
VERSION = "0.0.0.2"

APP_ROAMING_DIR = os.path.join(os.getenv('APPDATA'), APP_NAME)
CONFIG_FILENAME = "config_app.ini"

# region AI MODULES
GENRE_MODEL_PATH = "models/best_cls_genre_3s_0.001.onnx"
# endregion
