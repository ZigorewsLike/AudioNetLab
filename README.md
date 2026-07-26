# AudioNetLab

Desktop audio player for Windows built with PyQt6. Besides normal playback it classifies the
genre of a track with a neural network and can adjust a 20 band equalizer to the genre
automatically, fragment by fragment.

Audio is decoded into memory, streamed to the output device chunk by chunk in a background
thread, and every chunk passes through an STFT based equalizer before it is written to the
device. That is why the equalizer reacts immediately, without restarting playback.

## Features

* Playback of MP3, FLAC and WAV with a waveform view, a track list and tag display.
* A Library tab: import folders and files, browse the albums as a cover grid, search and sort
  them, and start an album from its tile.
* 20 band equalizer applied live during playback.
* Genre classification with an ONNX model: the track is split into 3 second fragments and each
  fragment gets its own genre.
* Auto EQ mode: the equalizer follows the genre under the playback cursor and interpolates
  between presets so a genre change is not audible as a jump.
* One editable EQ preset per genre, stored on disk.
* Output device switching, streaming buffer size and volume curve settings.
* Lyrics from the file tags with a timeline that follows playback, clicking a line seeks.
* English and Russian interface, switched at runtime without a restart.
* Built in profiler window with draw and math call timings.
* Experimental modules behind a flag, off by default: audio transcription, lyrics translation,
  lyrics summarization and the chat tab. See "Experimental modules" below.

## Requirements

* Windows 10 or newer. The application uses Windows only APIs (DPI detection, Explorer
  integration), it will not run on Linux or macOS as is.
* Python 3.10 (the project is developed and tested on 3.10.7).
* A working audio output device.

## Installation

```bat
git clone <repository-url>
cd AudioNetLab

python -m venv venv
venv\Scripts\activate

pip install -r requirements.txt
```

The genre model is included in the repository under `models/`, nothing needs to be downloaded
separately.

## Running

With the virtual environment activated:

```bat
python main.py
```

Or directly, without activating it:

```bat
venv\Scripts\python.exe main.py
```

On the first start the application creates `data/local/`, `data/registry/` and a `storage.db`
database in the project folder, so run it from the project root.

## First steps

1. On the **Library** tab press **Open file** or **Add folder**, or drag audio files and folders
   onto the window. They are added to the library.
2. Switch to the **Tracks** view and click a track to start playback, or double-click an album
   cover on the **Albums** view. The player panel is pinned to the bottom of the window:
   transport button, position slider, volume, waveform toggle and tag panel toggle.
3. Open the **EQ AI** tab and press **Predict**. The track is analysed and a coloured genre
   timeline appears, together with the genre shares and the final genre.
4. On the same tab the buttons on the left of the equalizer control it:
   * reset the sliders to a flat response,
   * enable or disable the equalizer effect,
   * enable auto EQ, where the sliders follow the detected genre,
   * set the interpolation smoothness (mouse wheel over the button).

The first prediction of a track is slow because the librosa features have to be extracted.
They are cached in the track registry, so a repeated prediction of the same track only runs
the model.

## Configuration

### config_app.ini

Written automatically on exit next to `main.py`. Editing it by hand is optional.

| Section | Key | Meaning |
| --- | --- | --- |
| SystemSettings | form_width, form_height | Window size |
| SystemSettings | form_position | Window position as `x:y` |
| SystemSettings | version | Version that wrote the file |
| SystemSettings | language | Interface language code, empty follows the system locale |
| SystemSettings | last_folder | Folder the open file dialog starts in |
| SystemSettings | open_filename | Last opened track |
| PlayerSettings | volume | Volume slider value, 0..1000 |
| PlayerSettings | auto_play | Reserved |
| PlayerSettings | graph_visible | Waveform panel visibility |

### src/global_constants.py

Developer level switches that are not exposed in the UI:

| Constant | Meaning |
| --- | --- |
| `DEBUG` | Debug logging, and the AI tabs stay enabled without an opened track |
| `PROFILE` | Collect timings for the profiler window (Tools, Profiling) |
| `AI_ENABLED` | Load the genre model at startup, turn it off for a faster start |
| `EXPERIMENTAL_MODULES` | Modules that call an external HTTP service, off by default |
| `CUSTOM_TITLE_BAR` | Frameless window with the custom title bar |
| `LOG_IN_FILE` | Duplicate the console output into `logs/` |
| `GENRE_MODEL_PATH` | Path to the ONNX classifier |
| `ONNX_SESS_PROVIDER` | `CPUExecutionProvider` or `DmlExecutionProvider` for a GPU |
| `PATTERN_SIZE` | Length of one classified fragment in seconds, must match the model |
| `SAMPLING_RATE_AI` | Sampling rate the model was trained on |
| `EQ_SLIDER_COUNT` | Number of equalizer bands |
| `GENRE_DICT` | Model output index to genre name |

`PATTERN_SIZE`, `SAMPLING_RATE_AI` and `GENRE_DICT` describe the bundled model. Changing them
without changing the model will produce wrong results.

### Audio settings

The **Settings** tab, section "Настройки аудио":

* **Устройство**: output device, press "Переключить" to apply. Playback keeps running.
* **Размер кеша**: streaming buffer size in samples, 256 to 4096. Larger values are safer
  against dropouts on a slow machine, smaller values reduce latency.
* **Логарифмический регулятор громкости**: makes the volume slider feel linear to the ear.

### Interface language

The **Settings** tab, section "Interface". English and Russian are available, the choice is
applied immediately and stored in `config_app.ini`. On the first start the language follows the
system locale and falls back to English when the locale has no catalog.

### Equalizer presets

The **Settings** tab, section "Пресеты эквалайзера": pick a genre, move the sliders, press
**Save preset**. Presets are stored in `res/presets.pickle` and are picked up by auto EQ right
after saving.

## Data on disk

| Path | Content |
| --- | --- |
| `storage.db` | SQLite database with the library: tracks, artists, albums, covers, scanned folders |
| `data/registry/<track_id>/` | Per track cache: tags, feature vectors, lyrics |
| `data/covers/` | Pre-scaled covers, named after the hash of the source image |
| `res/presets.pickle` | EQ presets per genre |
| `res/i18n/` | Translation catalogs, `.ts` sources and compiled `.qm` |
| `res/icons/` | Interface icons |
| `models/` | ONNX and h5 genre models |
| `config_app.ini` | Application settings |
| `error_log.txt` | Uncaught exceptions |

Deleting a track from the list also deletes its registry folder, if it has one: a track
imported by the scanner keeps its tags in the database and only gets a registry folder once it
is opened. The audio file itself is never touched, the application only stores its path.

### Importing into the library

Drop any number of files and whole folders on the window, use **File, Open file** for a
multiple selection, or **File, Add folder to the library** for a folder. A single dropped
file is registered immediately; anything larger goes to the scanner, which runs on its own
thread and reports on a strip above the player with a cancel button. The window stays usable
while it works, and a cancelled scan keeps everything it had already imported.

Two things keep a large import affordable:

* A file whose modification time did not change is never opened again, so a rescan of an
  unchanged collection costs a directory walk. On a collection of 3663 tracks that is 0.1 s.
* FLAC tags are read by a small parser that seeks past the artwork instead of loading it,
  because mutagen reads every metadata block and a FLAC with a cover carries a few hundred
  kilobytes of it. That is 0.6 KB read per track instead of 306 KB. The cover itself is
  decoded once per album, not once per track, and cached under `data/covers/` named after
  the hash of the image, so albums sharing artwork share one file.

Files that disappear are flagged, never deleted: an unplugged drive would otherwise wipe the
library along with its play counts. They are listed as missing and unflag themselves when the
drive comes back.

### The Library tab

The **Library** tab is the home of everything imported. It has two views, switched at the top
left: **Albums**, a grid of covers, and **Tracks**, the flat list of every track. The open file
and add folder buttons sit in the same top bar, so nothing needs a separate home page.

The album view is sorted by artist, title, year or add date, with a search box over the album
and artist names and a slider for the tile size. Double-clicking a cover opens the album page:
its cover, title and totals with a play button and a reveal-in-file-manager button, and below
that the track list with each track's own number, format (codec, sample rate, bit depth,
bitrate) and length. Playing an album queues the whole album, so it plays through and the next
and previous walk it; the track that is playing is marked in the list and the mark follows an
autoplay to the next one. The track view lists every track newest first and plays one on click,
the same as the old recent-track list.

The grid is a `QListView` with a `QStyledItemDelegate`, not a widget per album, so it paints
only the tiles on screen and stays smooth on a library of thousands of albums. Covers are read
off the interface thread through a small loader: a tile shows whatever is already in memory and
a placeholder otherwise, and the finished image repaints just that tile when it arrives.

Deleting the last track of an album removes the album and, if it also empties out, the artist,
so the grid never shows a tile that has nothing behind it. A database from before this rule is
cleaned once by the schema migration.

### Database schema

`storage.db` carries its schema version in `PRAGMA user_version`, and `src/api/db/migrations.py`
upgrades it on the first connection of a run. There is no Alembic: each version is one function
in `MIGRATION_STEPS`, run in its own transaction, so a failed upgrade leaves the file on the
previous version. To change the schema, edit the models, append a step and bump
`CURRENT_SCHEMA_VERSION`.

Artists and albums are deduplicated on a key column that is casefolded in Python rather than by
`COLLATE NOCASE`, because SQLite only folds ASCII and would file "Ария" and "ария" as two
artists. The same keys are what the library search matches against. Tracks are grouped into an
album by album artist and title, taking the `ALBUMARTIST` tag when the file has one, otherwise a
compilation would break up into one album per track.

## Project structure

```
main.py                     Entry point: logging, DPI, main window
src/
  forms/                    MainForm, the main window and the module wiring
  core/
    library/                Folder scanner, cover cache, the Library tab and album grid
    i18n/                   Translation manager, loads and switches the catalogs
    audio/                  AudioStreamer (streaming thread), AudioPlayer (player panel)
    render/graphics_system/ OpenGL waveform panels
    qt_widgets/             Shared widgets: sliders, equalizer, title bar, overlays
    file_system/            Tag reader, track registry and the recent track list
    settings/               Settings object and the settings pages
    workers/                Background workers: file opening, genre prediction, library scan
    log_system/             Logging and the profiler
    point_system/           Point helper type
  ai_module/
    genre_classification/   The EQ AI tab: prediction, timeline, auto EQ
    transcription/          Experimental lyrics modules
  api/db/                   SQLAlchemy models, schema migrations, library queries
  function_lib/             Audio features, the equalizer, ONNX loading, math helpers
  enums/                    Enumerations
  global_constants.py       Switches and paths
installer/                  PyInstaller build script
tools/                      Development scripts, translation catalog rebuild
models/                     Genre models
res/                        Icons, EQ presets, translation catalogs
```

## Experimental modules

Everything that talks to an external HTTP service sits behind `EXPERIMENTAL_MODULES` in
`src/global_constants.py` and is **off by default**, so a copy of the application runs fully
offline and needs nothing beyond `requirements.txt`.

Off (the default):

* No Chat tab.
* The Lyrics tab keeps working: lyrics are read from the file tags, the timeline follows
  playback, clicking a line seeks the track, the timestamp toggle and the extraction button
  stay in place.
* The right side panel of the Lyrics tab shows only the "Common" page, without the
  transcription, translation and summarization sections.
* The `requests` package is never imported, so it does not have to be installed.

On:

```python
EXPERIMENTAL_MODULES = True
```

Then install the development requirements, they add `requests`:

```bat
pip install -r requirements-dev.txt
```

These modules expect an HTTP service on `http://127.0.0.1:13000` with the endpoints
`audio/transcription/process`, `text/translate/process` and `text/summary/process`. The service
is not part of this repository, without it the buttons will fail on a connection error.

## Working with translations

Translations use the Qt Linguist toolchain. The literals in the code are English and are
wrapped in `self.tr(...)`, or in `QCoreApplication.translate("Context", ...)` in classes that
are not widgets. Every other language lives in a catalog under `res/i18n/`.

The tooling is a development dependency:

```bat
pip install -r requirements-dev.txt
```

After adding or changing a `tr()` string, rebuild the catalogs:

```bat
venv\Scripts\python.exe tools/update_translations.py
```

The script scans the sources with `pylupdate6`, refreshes `res/i18n/audionetlab_ru.ts` keeping
the existing translations, and compiles the `.qm` the application loads. New strings appear as
unfinished, translate them in the Qt Linguist editor and run the script again:

```bat
venv\Scripts\pyside6-linguist.exe res/i18n/audionetlab_ru.ts
```

To add a language, put its code into `LANGUAGES` in `tools/update_translations.py` and into
`LANGUAGE_NAMES` in `src/global_constants.py`, then run the script. The new language shows up
in the settings automatically.

Two rules matter when writing new UI code:

* A widget applies its texts in a `retranslate_ui()` method and calls it both from `__init__`
  and from `changeEvent` on `QEvent.Type.LanguageChange`. Without that its texts will not follow
  a language switch.
* Standard dialog buttons come from the Qt catalog bundled with PyQt6 and need no work.

## Building a standalone executable

```bat
venv\Scripts\activate
python installer/PyInstaller_running.py
```

The script fills `main_template.spec` with the current name, version and model path, writes
`main_generate.spec` and runs PyInstaller. The result appears in `dist/AudioNetLab v<version>/`.
It reads the active virtual environment from `VIRTUAL_ENV`, so the environment must be
activated.

## Troubleshooting

* **Playback stutters**: raise "Размер кеша" in the audio settings.
* **The device cannot be switched**: the device rejected the format of the current track,
  the application falls back to the system default and shows a message.
* **Prediction is slow on a long track**: expected on the first run, the features are cached
  afterwards. A GPU can be used by setting `ONNX_SESS_PROVIDER` to `DmlExecutionProvider`.
* **The window opens off screen**: delete `config_app.ini`, the geometry will be reset.
* **Crash dialog with a traceback**: the same text is appended to `error_log.txt`.