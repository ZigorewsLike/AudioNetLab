import os

# region Feature flags
DEBUG = True  # Debug logging and access to the AI tabs without an opened track
PROFILE = True  # Collect draw and math timings for the profiler window
SHOW_TRACEBACK = True
TRACE = False  # tracemalloc memory tracing
LOG_IN_FILE = False  # Duplicate the console output into logs/
LOG_IN_SIGNAL = False  # Duplicate the console output into a Qt signal
AI_ENABLED = True  # Load the genre model at startup
ONNX_INFERENCE = True
CUSTOM_TITLE_BAR = True  # Frameless window with the custom title bar
# Experimental modules that call an external HTTP service: audio transcription, lyrics
# translation, lyrics summarization and the chat tab. Off means the application needs no
# network and no requests package, while lyrics display, tag extraction and the timeline
# on the Lyrics tab keep working.
EXPERIMENTAL_MODULES = False
# endregion

APP_NAME = "AudioNetLab"
APP_TITLE = f"{APP_NAME}"
VERSION = "0.0.2.0"

APP_ROAMING_DIR = os.path.join(os.getenv('APPDATA'), APP_NAME)
CONFIG_FILENAME = "config_app.ini"
RESOURCE_ICON_DIR = "res/icons/"
RESOURCE_DIR = "res/"

PATH_TO_LAST_REGISTRY = "data/registry/"  # Per track cache: tags, cover, features, lyrics

# region LIBRARY
# Extensions the player can decode. The file dialog, the drop target and the folder
# scanner all read this, so a new format is enabled in one place.
SUPPORTED_AUDIO_EXTENSIONS = (".mp3", ".flac", ".wav", ".wave")
# Images looked for next to an audio file when the tags carry no cover, in this order
COVER_FILE_NAMES = ("cover", "folder", "front", "album", "albumart")
COVER_FILE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp", ".bmp")
PATH_TO_COVER_CACHE = "data/covers/"  # Pre-scaled covers, named after the hash of the source image
COVER_CACHE_SIZES = (160, 480)  # Edge length of the cached copies, the grid picks the nearest
COVER_CACHE_QUALITY = 85  # JPEG quality of the cached copies
COVER_MEMORY_CACHE_KB = 96 * 1024  # QPixmapCache budget for the decoded covers
SCAN_CHUNK_SIZE = 256  # Files read and written per pass, keeps memory flat on a huge library
SCAN_PROGRESS_INTERVAL_MS = 100  # Lower bound between two progress signals of the scanner
# endregion

# region I18N
I18N_DIR = "res/i18n/"  # Compiled .qm catalogs
SOURCE_LANGUAGE = "en"  # Language the literals in the code are written in, needs no catalog
LANGUAGE_NAMES = {
    "en": "English",
    "ru": "Русский",
}
# endregion

# region AI MODULES
GENRE_MODEL_PATH = "models/best_cls_genre_fma_3s_0.0001.onnx"
ONNX_SESS_PROVIDER = "CPUExecutionProvider"  # DmlExecutionProvider, CPUExecutionProvider
PATTERN_SIZE = 3  # Length of one classified fragment, seconds
SAMPLING_RATE_AI = 22050  # Sampling rate the model was trained on
# endregion

LAST_FILE_LIMIT = 60
LAST_FILE_FILENAME = "local_history.bin"

EQ_SLIDER_COUNT = 20

# Genre name per model output index, the order comes from the training dataset
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