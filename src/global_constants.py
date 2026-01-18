import os

DEBUG = True
PROFILE = True
SHOW_TRACEBACK = True
TRACE = False
LOG_IN_FILE = False
LOG_IN_SIGNAL = False
AI_ENABLED = True
ONNX_INFERENCE = True
CUSTOM_TITLE_BAR = True

APP_NAME = "AudioNetLab"
APP_TITLE = f"{APP_NAME}"
VERSION = "0.0.0.3"

APP_ROAMING_DIR = os.path.join(os.getenv('APPDATA'), APP_NAME)
CONFIG_FILENAME = "config_app.ini"
RESOURCE_ICON_DIR = "res/icons/"
RESOURCE_DIR = "res/"
PATH_TO_LAST_REGISTRY = "data/registry/"

# region AI MODULES
GENRE_MODEL_PATH = "models/best_cls_genre_fma_3s_0.0001.onnx"
ONNX_SESS_PROVIDER = "CPUExecutionProvider"  # DmlExecutionProvider, CPUExecutionProvider
PATTERN_SIZE = 3
SAMPLING_RATE_AI = 22050
# endregion

LAST_FILE_LIMIT = 60
LAST_FILE_FILENAME = "local_history.bin"

EQ_SLIDER_COUNT = 20

GENRE_DICT = {
    0: "Electronic",
    1: "Experimental",
    2: "Folk",
    3: "Hip-Hop",
    4: "Instrumental",
    5: "International",
    6: "Pop",
    7: "Rock",
}

