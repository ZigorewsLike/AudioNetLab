# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.win32.versioninfo import (
    VSVersionInfo, FixedFileInfo, StringFileInfo, StringTable,
    StringStruct, VarFileInfo, VarStruct,
)

# Version resource so the exe carries proper metadata (name, version, git hash).
_v = ($VERSION_TUPLE)
version_info = VSVersionInfo(
    ffi=FixedFileInfo(filevers=_v, prodvers=_v, mask=0x3f, flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0),
    kids=[
        StringFileInfo([StringTable('040904B0', [
            StringStruct('CompanyName', '$APP_AUTHOR'),
            StringStruct('FileDescription', '$APP_NAME'),
            StringStruct('FileVersion', '$VERSION'),
            StringStruct('ProductName', '$APP_NAME'),
            StringStruct('ProductVersion', '$VERSION_FULL'),
            StringStruct('LegalCopyright', '$COPYRIGHT'),
        ])]),
        VarFileInfo([VarStruct('Translation', [1033, 1200])]),
    ],
)

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('res/icons/*.png', 'res/icons'),
        ('res/i18n/*.qm', 'res/i18n'),
        ('res/presets.pickle', 'res'),
        ('$GENRE_MODEL_PATH', 'models'),
    ],
    hiddenimports=['src._version'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Heavy deps that are not imported at runtime (only via converters/dev tooling)
        'torch', 'PySide6', 'shiboken6',
        'onnx', 'sympy',  # sklearn is required transitively by librosa.decompose/effects
        # Build/dev tooling that must not ship in prod
        'pip', 'tkinter', 'IPython', 'pytest',
        # Only used by EXPERIMENTAL_MODULES (off in prod)
        'requests', 'urllib3', 'certifi', 'charset_normalizer', 'idna',
        # Unused Qt modules (app uses only QtCore/QtGui/QtWidgets/QtOpenGLWidgets)
        'PyQt6.QtWebEngineCore', 'PyQt6.QtWebEngineWidgets', 'PyQt6.QtQml',
        'PyQt6.QtQuick', 'PyQt6.QtQuick3D', 'PyQt6.QtMultimedia', 'PyQt6.QtNetwork',
        'PyQt6.QtBluetooth', 'PyQt6.QtNfc', 'PyQt6.QtPositioning', 'PyQt6.QtSensors',
        'PyQt6.QtCharts', 'PyQt6.QtDataVisualization', 'PyQt6.Qt3DCore',
        'PyQt6.QtPdf', 'PyQt6.QtSql', 'PyQt6.QtTest', 'PyQt6.QtDesigner',
        'PyQt6.QtSvg', 'PyQt6.QtHelp', 'PyQt6.QtDBus',
    ],
    noarchive=False,
)
pyz = PYZ(a.pure)

# Large native libraries are left uncompressed: UPX on these slows startup and is a
# frequent Windows Defender / SmartScreen false-positive trigger.
_upx_exclude = [
    'onnxruntime*.dll', 'DirectML.dll', 'onnxruntime_providers_*.dll',
    'Qt6Core.dll', 'Qt6Gui.dll', 'Qt6Widgets.dll', 'Qt6OpenGL.dll',
    'vcruntime*.dll', 'msvcp*.dll',
]

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='$APP_NAME',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=_upx_exclude,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    contents_directory='$CONTENT_DIR',
    version=version_info,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=_upx_exclude,
    name='$BUILD_PATH',
)
