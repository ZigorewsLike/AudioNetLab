import hashlib
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Optional, Set, Tuple

from PyQt6 import QtCore
from PyQt6.QtCore import QBuffer, QByteArray, QIODevice, QObject, Qt
from PyQt6.QtGui import QImage, QPixmap, QPixmapCache

from src.core.log_system import print_e
from src.global_constants import (COVER_CACHE_QUALITY, COVER_CACHE_SIZES, COVER_MEMORY_CACHE_KB,
                                  PATH_TO_COVER_CACHE)

_cache_limit_applied = False
_store_lock = threading.Lock()


def _apply_memory_budget() -> None:
    """Raise the QPixmapCache budget once, the default is far too small for a grid.

    :returns: None.
    """
    global _cache_limit_applied
    if not _cache_limit_applied:
        QPixmapCache.setCacheLimit(COVER_MEMORY_CACHE_KB)
        _cache_limit_applied = True


class CoverCache:
    """Covers on disk, named after the hash of the image they were made from.

    Naming a cover after its content means an album shared by fifteen tracks is
    decoded and written once, and two albums that ship the same artwork share one
    file. Every copy is pre-scaled, so showing a grid is a JPEG read of a few
    kilobytes instead of a full size decode.

    The methods that only touch QImage are safe to call from a worker thread. The
    ones returning a QPixmap are not, QPixmap belongs to the GUI thread.
    """

    @staticmethod
    def nearest_size(requested: int) -> int:
        """Pick the cached size to read for a requested edge length.

        :param requested: Edge length the caller wants to draw at.
        :returns: int - Size that is cached on disk.
        """
        for size in sorted(COVER_CACHE_SIZES):
            if size >= requested:
                return size
        return max(COVER_CACHE_SIZES)

    @staticmethod
    def path_for(cover_hash: str, size: int) -> str:
        """Build the path of one cached copy.

        The first two characters of the hash become a subfolder, so a library with
        thousands of covers never puts thousands of files in one directory.

        :param cover_hash: Hash of the source image.
        :param size: Cached size, one of COVER_CACHE_SIZES.
        :returns: str - Path of the cached file.
        """
        return os.path.join(PATH_TO_COVER_CACHE, cover_hash[:2], f"{cover_hash}_{size}.jpg")

    @staticmethod
    def exists(cover_hash: str) -> bool:
        """Whether every size of a cover is already on disk.

        :param cover_hash: Hash of the source image.
        :returns: bool - True when nothing has to be decoded.
        """
        return all(os.path.exists(CoverCache.path_for(cover_hash, size)) for size in COVER_CACHE_SIZES)

    @staticmethod
    def hash_bytes(image_bytes: bytes) -> str:
        """Hash the encoded image the cover is made from.

        :param image_bytes: Encoded image as it sits in the tags or on disk.
        :returns: str - Hex digest naming the cover.
        """
        return hashlib.md5(image_bytes).hexdigest()

    @staticmethod
    def store(image_bytes: bytes) -> Optional[Tuple[str, int, int]]:
        """Decode an image once and write every cached size of it.

        Safe to call from a worker thread. Returns immediately when the cover is
        already cached, which is what makes a rescan cheap.

        :param image_bytes: Encoded image as it sits in the tags or on disk.
        :returns: Tuple[str, int, int] - Hash, source width and height, None on failure.
        """
        if not image_bytes:
            return None
        cover_hash = CoverCache.hash_bytes(image_bytes)

        image: Optional[QImage] = None
        if not CoverCache.exists(cover_hash):
            image = QImage()
            if not image.loadFromData(image_bytes):
                print_e(f"Cover decode error, hash {cover_hash}")
                return None
            if image.isNull():
                return None
            # JPEG has no alpha channel, converting up front avoids a surprise on save
            image = image.convertToFormat(QImage.Format.Format_RGB32)

            folder = os.path.dirname(CoverCache.path_for(cover_hash, COVER_CACHE_SIZES[0]))
            with _store_lock:  # Two threads can meet on the same album folder
                os.makedirs(folder, exist_ok=True)

            for size in COVER_CACHE_SIZES:
                target = CoverCache.path_for(cover_hash, size)
                if os.path.exists(target):
                    continue
                # Keep the aspect ratio; the view letterboxes rather than crops the artwork
                scaled = image.scaled(size, size,
                                      Qt.AspectRatioMode.KeepAspectRatio,
                                      Qt.TransformationMode.SmoothTransformation)
                if not scaled.save(target, "JPG", COVER_CACHE_QUALITY):
                    print_e(f"Cover write error: {target}")
                    return None

        if image is not None:
            return cover_hash, image.width(), image.height()
        # Already cached, report the size of the largest copy instead of decoding again
        cached = QImage(CoverCache.path_for(cover_hash, max(COVER_CACHE_SIZES)))
        return cover_hash, cached.width(), cached.height()

    @staticmethod
    def discard(cover_hash: str) -> int:
        """Delete every cached copy of a cover and forget it in memory.

        A copy that cannot be removed is left where it is rather than raising.

        :param cover_hash: Hash of the source image.
        :returns: int - Bytes freed on disk.
        """
        if not cover_hash:
            return 0
        _apply_memory_budget()
        freed = 0
        folder: Optional[str] = None
        for size in COVER_CACHE_SIZES:
            path = CoverCache.path_for(cover_hash, size)
            folder = os.path.dirname(path)
            try:
                freed += os.path.getsize(path)
                os.remove(path)
            except OSError:
                pass
            QPixmapCache.remove(cache_key(cover_hash, size))
        if folder:
            try:
                os.rmdir(folder)  # Only succeeds once the prefix holds no other cover
            except OSError:
                pass
        return freed

    @staticmethod
    def load_image(cover_hash: str, size: int) -> Optional[QImage]:
        """Read one cached copy of a cover.

        Safe to call from a worker thread.

        :param cover_hash: Hash of the source image.
        :param size: Requested edge length, rounded up to a cached size.
        :returns: QImage - The cover, None when it is not cached.
        """
        if not cover_hash:
            return None
        path = CoverCache.path_for(cover_hash, CoverCache.nearest_size(size))
        if not os.path.exists(path):
            return None
        image = QImage(path)
        return None if image.isNull() else image

    @staticmethod
    def load_pixmap(cover_hash: str, size: int) -> Optional[QPixmap]:
        """Read a cover as a pixmap, going through the in memory cache.

        GUI thread only.

        :param cover_hash: Hash of the source image.
        :param size: Requested edge length, rounded up to a cached size.
        :returns: QPixmap - The cover, None when it is not cached.
        """
        if not cover_hash:
            return None
        _apply_memory_budget()
        key = cache_key(cover_hash, size)
        pixmap = QPixmapCache.find(key)
        if pixmap is not None:
            return pixmap
        image = CoverCache.load_image(cover_hash, size)
        if image is None:
            return None
        pixmap = QPixmap.fromImage(image)
        QPixmapCache.insert(key, pixmap)
        return pixmap

    @staticmethod
    def put_pixmap(cover_hash: str, size: int, image: QImage) -> QPixmap:
        """Turn a loaded image into a cached pixmap.

        GUI thread only, used by the loader when a background read comes back.

        :param cover_hash: Hash of the source image.
        :param size: Requested edge length.
        :param image: Image read in the background.
        :returns: QPixmap - The cached pixmap.
        """
        _apply_memory_budget()
        pixmap = QPixmap.fromImage(image)
        QPixmapCache.insert(cache_key(cover_hash, size), pixmap)
        return pixmap

    @staticmethod
    def encode_image(image: QImage) -> Optional[bytes]:
        """Encode an image so it can be stored, for callers holding a QImage already.

        :param image: Image to encode.
        :returns: bytes - PNG encoded image, None when the image is empty.
        """
        if image is None or image.isNull():
            return None
        buffer_data = QByteArray()
        buffer = QBuffer(buffer_data)
        buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        image.save(buffer, "PNG")
        buffer.close()
        return bytes(buffer_data)


def cache_key(cover_hash: str, size: int) -> str:
    """Build the QPixmapCache key of one cover copy.

    :param cover_hash: Hash of the source image.
    :param size: Requested edge length.
    :returns: str - Cache key.
    """
    return f"cover:{cover_hash}:{CoverCache.nearest_size(size)}"


class CoverLoader(QObject):
    """Reads covers off the GUI thread and hands them back as pixmaps.

    A view asks for a cover while painting and gets whatever is already in memory. A
    miss is queued here, decoded in a small pool and delivered by signal, so scrolling
    never waits on the disk. The pool is deliberately small: more threads would only
    queue up work for covers that scrolled out of sight before they were decoded.

    :signals: coverReady (str, int) - hash and size of a cover now in the pixmap cache
    """
    coverReady = QtCore.pyqtSignal(str, int)
    _imageLoaded = QtCore.pyqtSignal(str, int, QImage)

    def __init__(self, max_workers: int = 2, *args, **kwargs):
        """Start the loader pool.

        :param max_workers: Number of decoding threads.
        :returns: None.
        """
        super().__init__(*args, **kwargs)
        self._pool = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="cover")
        self._pending: Set[Tuple[str, int]] = set()
        self._lock = threading.Lock()
        self._closed = False
        # Queued by default across threads, the slot runs on the GUI thread
        self._imageLoaded.connect(self._on_image_loaded)

    def request(self, cover_hash: str, size: int) -> Optional[QPixmap]:
        """Ask for a cover, returning it right away when it is already in memory.

        :param cover_hash: Hash of the source image.
        :param size: Requested edge length.
        :returns: QPixmap - The cover when it was cached, None when it is being read.
        """
        if not cover_hash or self._closed:
            return None
        _apply_memory_budget()
        pixmap = QPixmapCache.find(cache_key(cover_hash, size))
        if pixmap is not None:
            return pixmap

        key = (cover_hash, CoverCache.nearest_size(size))
        with self._lock:
            if key in self._pending:
                return None
            self._pending.add(key)
        self._pool.submit(self._load, key[0], key[1])
        return None

    def drop_pending(self) -> None:
        """Forget the queued requests, for a view that scrolled far away.

        The tasks already running finish, their result is simply not awaited by
        anything. It only stops the queue from growing during a fast scroll.

        :returns: None.
        """
        with self._lock:
            self._pending.clear()

    def shutdown(self) -> None:
        """Stop accepting requests and wait for the running reads.

        :returns: None.
        """
        self._closed = True
        self._pool.shutdown(wait=False)

    def _load(self, cover_hash: str, size: int) -> None:
        """Read one cover in the pool. Runs on a worker thread.

        :param cover_hash: Hash of the source image.
        :param size: Cached size to read.
        :returns: None.
        """
        try:
            image = CoverCache.load_image(cover_hash, size)
            if image is not None:
                self._imageLoaded.emit(cover_hash, size, image)
                return
        except Exception as e:
            print_e(f"Cover load error, hash {cover_hash}", e)
        with self._lock:
            self._pending.discard((cover_hash, size))

    @QtCore.pyqtSlot(str, int, QImage)
    def _on_image_loaded(self, cover_hash: str, size: int, image: QImage) -> None:
        """Put a background read into the pixmap cache. Runs on the GUI thread.

        :param cover_hash: Hash of the source image.
        :param size: Cached size that was read.
        :param image: The decoded cover.
        :returns: None.
        """
        with self._lock:
            self._pending.discard((cover_hash, size))
        CoverCache.put_pixmap(cover_hash, size, image)
        self.coverReady.emit(cover_hash, size)
