import datetime
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Sequence, Set, Tuple

from sqlalchemy import insert, select, update
from sqlalchemy.orm import Session

from src.api.db import library_repo
from src.api.db.models import (Album, Artist, Cover, LibraryFolder, Track,
                               make_album_key, make_sort_name, normalize_key, normalize_path)
from src.core.library.cover_cache import CoverCache
from src.core.file_system.tag_reader import (TrackTags, iter_audio_files, read_embedded_cover,
                                             read_folder_cover, read_tags, title_from_path)
from src.core.log_system import print_d, print_e, print_traceback
from src.enums import ScanStage
from src.global_constants import SCAN_CHUNK_SIZE, SUPPORTED_AUDIO_EXTENSIONS

# Marks an album whose cover was searched and not found, so later chunks skip it
_NO_COVER = 0

# Ids per statement when the finalize pass updates rows by primary key
_ID_CHUNK = 500


@dataclass
class ScanStats:
    """What one scan did, shown when it finishes."""
    files_seen: int = 0
    tracks_added: int = 0
    tracks_updated: int = 0
    tracks_unchanged: int = 0
    tracks_missing: int = 0
    tracks_recovered: int = 0
    albums_added: int = 0
    artists_added: int = 0
    covers_added: int = 0
    errors: int = 0
    cancelled: bool = False
    elapsed: float = 0.0

    @property
    def changed(self) -> bool:
        """Whether the scan touched the library at all.

        :returns: bool - True when a view has to be rebuilt.
        """
        return bool(self.tracks_added or self.tracks_updated
                    or self.tracks_missing or self.tracks_recovered)


@dataclass
class _ParsedFile:
    """One file after its tags were read, before it is written."""
    path: str
    size: int
    mtime: float
    tags: TrackTags
    artist_key: str
    album_key: str


ProgressCallback = Callable[[ScanStage, int, int], None]


class LibraryScanner:
    """Imports folders and files into the library.

    The work is done in chunks: a chunk of files is read by a thread pool, its covers
    are extracted, and the rows are written in one transaction before the next chunk
    starts. That keeps the memory flat no matter how large the library is, makes the
    progress smooth, and means a cancelled scan keeps everything it already imported.

    Two things carry the cost of a large import. Files whose modification time did not
    change are never opened, so a rescan is a directory walk. And a cover is decoded
    once per album rather than once per track, which on a normal library is a twelfth
    of the work.

    The instance runs on one thread and owns its session, it is not shared.
    """

    def __init__(self,
                 session: Session,
                 progress_callback: Optional[ProgressCallback] = None,
                 cancel_event: Optional[threading.Event] = None,
                 max_workers: Optional[int] = None,
                 extensions: Sequence[str] = SUPPORTED_AUDIO_EXTENSIONS):
        """Prepare a scanner.

        :param session: Session owned by the calling thread.
        :param progress_callback: Called with the stage, the done count and the total.
        :param cancel_event: Checked between chunks, a set event stops the scan.
        :param max_workers: Size of the tag reading pool, defaults to the cpu count.
        :param extensions: Lowercase extensions to import, including the dot.
        :returns: None.
        """
        self.session = session
        self.progress_callback = progress_callback
        self.cancel_event = cancel_event or threading.Event()
        self.extensions = [extension.lower() for extension in extensions]
        # Tag reads are disk-bound, so more threads than cores still helps, up to a point
        self.max_workers = max_workers or min(8, (os.cpu_count() or 2) + 2)

        self.stats = ScanStats()

        self._artist_ids: Dict[str, int] = {}          # name_key -> artist id
        self._album_ids: Dict[str, int] = {}           # match_key -> album id
        self._album_years: Dict[str, Optional[int]] = {}
        self._album_covers: Dict[str, int] = {}        # match_key -> cover id, _NO_COVER when none
        self._cover_ids: Dict[str, int] = {}           # image hash -> cover id
        self._folder_covers: Dict[str, Optional[bytes]] = {}  # folder -> image bytes read from disk
        self._folder_lock = threading.Lock()  # Pool threads meet on the folder cover cache

    # region public
    def scan(self, paths: Sequence[str]) -> ScanStats:
        """Import every file and folder in the list.

        :param paths: Files and folders to import, in any mix.
        :returns: ScanStats - What the scan did.
        """
        started = time.monotonic()
        try:
            folders, files = self._split_paths(paths)
            found = self._collect(folders, files)
            if self._cancelled():
                return self._finish(started)

            path_index = library_repo.get_path_index(self.session)
            todo, unchanged, recovered = self._diff(found, path_index)
            self.stats.files_seen = len(found)
            self.stats.tracks_unchanged = len(unchanged)

            self._process(todo, path_index)
            if not self._cancelled():
                self._finalize(folders, found, path_index, recovered)
        except Exception as e:
            print_traceback()
            print_e("Library scan failed", e)
            self.session.rollback()
            self.stats.errors += 1
        return self._finish(started)
    # endregion

    # region collect
    @staticmethod
    def _split_paths(paths: Sequence[str]) -> Tuple[List[str], List[str]]:
        """Sort the requested paths into folders and single files.

        :param paths: Files and folders in any mix.
        :returns: Tuple[List[str], List[str]] - Folders and files.
        """
        folders: List[str] = []
        files: List[str] = []
        for raw in paths:
            path = normalize_path(raw)
            if os.path.isdir(path):
                folders.append(path)
            elif os.path.isfile(path):
                files.append(path)
        return folders, files

    def _collect(self, folders: Sequence[str], files: Sequence[str]) -> Dict[str, Tuple[int, float]]:
        """Walk the folders and stat the single files.

        :param folders: Folders to walk.
        :param files: Single files to include.
        :returns: Dict[str, Tuple[int, float]] - Size and modification time per path.
        """
        found: Dict[str, Tuple[int, float]] = {}
        self._report(ScanStage.WALK, 0, 0)
        for folder in folders:
            for path, size, mtime in iter_audio_files(folder, self.extensions):
                found[normalize_path(path)] = (size, mtime)
                if len(found) % 500 == 0:
                    self._report(ScanStage.WALK, len(found), 0)
                    if self._cancelled():
                        return found
        for path in files:
            if os.path.splitext(path)[1].lower() not in self.extensions:
                continue
            try:
                stat = os.stat(path)
            except OSError:
                continue
            found[path] = (stat.st_size, stat.st_mtime)
        self._report(ScanStage.WALK, len(found), len(found))
        return found

    @staticmethod
    def _diff(found: Dict[str, Tuple[int, float]],
              path_index: Dict[str, library_repo.PathEntry]
              ) -> Tuple[List[Tuple[str, int, float]], List[str], List[int]]:
        """Split the found files into the ones that need reading and the ones that do not.

        A file is read again only when its modification time moved. This is what makes
        a rescan of an unchanged library cost a directory walk and nothing else.

        :param found: Size and modification time per found path.
        :param path_index: State of the paths already in the library.
        :returns: Tuple - Files to read, unchanged paths, ids of files that came back.
        """
        todo: List[Tuple[str, int, float]] = []
        unchanged: List[str] = []
        recovered: List[int] = []
        for path, (size, mtime) in found.items():
            entry = path_index.get(path)
            if entry is None:
                todo.append((path, size, mtime))
                continue
            if abs(entry.mtime - mtime) > 1e-6:
                todo.append((path, size, mtime))
                continue
            unchanged.append(path)
            if entry.is_missing:
                recovered.append(entry.track_id)  # The file is back where it was
        return todo, unchanged, recovered
    # endregion

    # region process
    def _process(self, todo: List[Tuple[str, int, float]],
                 path_index: Dict[str, library_repo.PathEntry]) -> None:
        """Read and write the files that changed, one chunk at a time.

        :param todo: Files to read as (path, size, mtime).
        :param path_index: State of the paths already in the library.
        :returns: None.
        """
        total = len(todo)
        done = 0
        self._report(ScanStage.READ, 0, total)
        if not total:
            return

        with ThreadPoolExecutor(max_workers=self.max_workers, thread_name_prefix="scan") as pool:
            for start in range(0, total, SCAN_CHUNK_SIZE):
                if self._cancelled():
                    return
                chunk = todo[start:start + SCAN_CHUNK_SIZE]
                parsed = self._read_chunk(pool, chunk)
                loose_covers = self._resolve_covers(pool, parsed)
                self._write_chunk(parsed, path_index, loose_covers)
                done += len(chunk)
                self._report(ScanStage.READ, done, total)

    def _read_chunk(self, pool: ThreadPoolExecutor,
                    chunk: List[Tuple[str, int, float]]) -> List[_ParsedFile]:
        """Read the tags of one chunk in parallel.

        :param pool: Pool to read on.
        :param chunk: Files as (path, size, mtime).
        :returns: List[_ParsedFile] - Files that could be parsed.
        """
        results = list(pool.map(self._read_one, chunk))
        parsed = [item for item in results if item is not None]
        self.stats.errors += len(results) - len(parsed)
        return parsed

    def _read_one(self, item: Tuple[str, int, float]) -> Optional[_ParsedFile]:
        """Read one file. Runs on a pool thread.

        :param item: File as (path, size, mtime).
        :returns: _ParsedFile - The parsed file, None when it could not be read.
        """
        path, size, mtime = item
        try:
            tags = read_tags(path, file_size=size)
        except Exception as e:
            print_e(f"Tag read error: {path}", e)
            return None
        if tags is None:
            return None
        # Album artist keys the album (track artist as fallback), else a compilation splits per track
        artist_key = normalize_key(tags.artist)
        album_artist_key = normalize_key(tags.album_artist) or artist_key
        album_key = make_album_key(album_artist_key, tags.album) if tags.album else ""
        return _ParsedFile(path=path, size=size, mtime=mtime, tags=tags,
                           artist_key=artist_key, album_key=album_key)

    def _resolve_covers(self, pool: ThreadPoolExecutor, parsed: List[_ParsedFile]) -> Dict[str, int]:
        """Extract and cache the cover of every album seen for the first time.

        One representative file per album is opened, not every file of it. Files that
        carry no album tag have no album to hang a cover on, so they are handled one
        by one, which is affordable because a tagged library has very few of them.

        :param pool: Pool to decode on.
        :param parsed: Files of the current chunk.
        :returns: Dict[str, int] - Cover id per path, for the files without an album.
        """
        album_jobs: List[Tuple[str, str]] = []      # (album key, representative path)
        loose_jobs: List[str] = []                  # paths of files without an album
        seen_albums: Set[str] = set()
        for item in parsed:
            if not item.album_key:
                loose_jobs.append(item.path)
                continue
            if item.album_key in self._album_covers or item.album_key in seen_albums:
                continue
            seen_albums.add(item.album_key)
            album_jobs.append((item.album_key, item.path))

        loose_covers: Dict[str, int] = {}
        if not album_jobs and not loose_jobs:
            return loose_covers

        paths = [path for _, path in album_jobs] + loose_jobs
        results = list(pool.map(self._extract_cover, paths))

        for (album_key, _), result in zip(album_jobs, results):
            if result is None:
                self._album_covers[album_key] = _NO_COVER
                continue
            self._album_covers[album_key] = self._cover_id(*result)
        for path, result in zip(loose_jobs, results[len(album_jobs):]):
            if result is not None:
                loose_covers[path] = self._cover_id(*result)
        return loose_covers

    def _extract_cover(self, path: str) -> Optional[Tuple[str, int, int]]:
        """Read the cover of one album and write it to the cover cache.

        Runs on a pool thread. The tags win, an image lying next to the audio is the
        fallback, and that image is read once per folder however many albums use it.

        :param path: Representative file of the album.
        :returns: Tuple[str, int, int] - Hash, width and height, None when there is no cover.
        """
        try:
            image_bytes = read_embedded_cover(path)
            if not image_bytes:
                folder = os.path.dirname(path)
                with self._folder_lock:
                    if folder not in self._folder_covers:
                        self._folder_covers[folder] = read_folder_cover(folder)
                    image_bytes = self._folder_covers[folder]
            if not image_bytes:
                return None
            return CoverCache.store(image_bytes)
        except Exception as e:
            print_e(f"Cover resolve error: {path}", e)
            return None
    # endregion

    # region write
    def _write_chunk(self, parsed: List[_ParsedFile],
                     path_index: Dict[str, library_repo.PathEntry],
                     loose_covers: Dict[str, int]) -> None:
        """Write one chunk of files in a single transaction.

        Every row of a batch carries the same keys, an executemany cannot mix shapes.

        :param parsed: Files of the current chunk.
        :param path_index: State of the paths already in the library.
        :param loose_covers: Cover id per path, for the files without an album.
        :returns: None.
        """
        inserts: List[dict] = []
        updates: List[dict] = []
        now = datetime.datetime.now()

        for item in parsed:
            tags = item.tags
            artist_id = self._artist_id(tags.artist) if tags.artist else None
            album_id = self._album_id(item, artist_id)
            title = tags.title or title_from_path(item.path)

            row = {
                "title": title,
                "title_key": normalize_key(title),
                "artist_id": artist_id,
                "album_id": album_id,
                # Only a loose track owns a cover; an album track inherits the album's
                "cover_id": loose_covers.get(item.path) if album_id is None else None,
                "track_no": tags.track_no,
                "disc_no": tags.disc_no,
                "year": tags.year,
                "genre": tags.genre,
                "duration": tags.duration,
                "bitrate": tags.bitrate,
                "sample_rate": tags.sample_rate,
                "channels": tags.channels,
                "bits_per_sample": tags.bits_per_sample,
                "file_size": item.size,
                "file_mtime": item.mtime,
                "is_missing": False,
            }

            entry = path_index.get(item.path)
            if entry is None:
                row["path"] = item.path
                row["dt_create"] = now
                row["dt_last_opened"] = None
                row["play_count"] = 0
                inserts.append(row)
            else:
                row["id"] = entry.track_id
                updates.append(row)

        if inserts:
            self.session.execute(insert(Track), inserts)
            self.stats.tracks_added += len(inserts)
        if updates:
            self.session.execute(update(Track), updates)
            self.stats.tracks_updated += len(updates)
        self.session.commit()

    def _artist_id(self, name: str) -> Optional[int]:
        """Find or create the artist of a name, caching the lookup.

        :param name: Artist name as written in the tags.
        :returns: int - Artist id, None when the name is empty.
        """
        name_key = normalize_key(name)
        if not name_key:
            return None
        cached = self._artist_ids.get(name_key)
        if cached is not None:
            return cached

        artist_id = self.session.scalar(select(Artist.id).where(Artist.name_key == name_key))
        if artist_id is None:
            artist_id = self.session.execute(
                insert(Artist).values(name=name.strip(), name_key=name_key,
                                      sort_name=make_sort_name(name))
            ).inserted_primary_key[0]
            self.stats.artists_added += 1
        self._artist_ids[name_key] = artist_id
        return artist_id

    def _album_id(self, item: _ParsedFile, track_artist_id: Optional[int]) -> Optional[int]:
        """Find or create the album of a file, caching the lookup.

        :param item: Parsed file.
        :param track_artist_id: Artist of the track, used when there is no album artist.
        :returns: int - Album id, None when the file carries no album tag.
        """
        if not item.album_key:
            return None
        cached = self._album_ids.get(item.album_key)
        if cached is not None:
            self._patch_album_year(cached, item)
            return cached

        row = self.session.execute(
            select(Album.id, Album.year).where(Album.match_key == item.album_key)
        ).first()
        if row is not None:
            album_id, year = row
            self._album_ids[item.album_key] = album_id
            self._album_years[item.album_key] = year
            self._patch_album_year(album_id, item)
            return album_id

        album_artist_id = (self._artist_id(item.tags.album_artist)
                           if item.tags.album_artist else track_artist_id)
        album_id = self.session.execute(
            insert(Album).values(title=item.tags.album.strip(),
                                 match_key=item.album_key,
                                 artist_id=album_artist_id,
                                 cover_id=self._album_covers.get(item.album_key) or None,
                                 year=item.tags.year,
                                 dt_added=datetime.datetime.now())
        ).inserted_primary_key[0]
        self._album_ids[item.album_key] = album_id
        self._album_years[item.album_key] = item.tags.year
        self.stats.albums_added += 1
        return album_id

    def _patch_album_year(self, album_id: int, item: _ParsedFile) -> None:
        """Fill in the year of an album whose first track did not carry one.

        :param album_id: Album id.
        :param item: Parsed file that may know the year.
        :returns: None.
        """
        if item.tags.year is None:
            return
        if self._album_years.get(item.album_key) is not None:
            return
        self.session.execute(update(Album).where(Album.id == album_id).values(year=item.tags.year))
        self._album_years[item.album_key] = item.tags.year

    def _cover_id(self, cover_hash: str, width: int, height: int) -> int:
        """Find or create the cover row of a cached image.

        :param cover_hash: Hash naming the cached cover.
        :param width: Width of the source image.
        :param height: Height of the source image.
        :returns: int - Cover id.
        """
        cached = self._cover_ids.get(cover_hash)
        if cached is not None:
            return cached
        cover_id = self.session.scalar(select(Cover.id).where(Cover.hash == cover_hash))
        if cover_id is None:
            cover_id = self.session.execute(
                insert(Cover).values(hash=cover_hash, width=width, height=height, source="tag")
            ).inserted_primary_key[0]
            self.stats.covers_added += 1
        self._cover_ids[cover_hash] = cover_id
        return cover_id
    # endregion

    # region finalize
    def _finalize(self, folders: Sequence[str],
                  found: Dict[str, Tuple[int, float]],
                  path_index: Dict[str, library_repo.PathEntry],
                  recovered: List[int]) -> None:
        """Mark what disappeared, clear the flag on what came back, stamp the folders.

        Files that vanished are flagged rather than deleted: an unplugged drive would
        otherwise wipe half the library, together with the play counts.

        :param folders: Folders that were scanned.
        :param found: Paths seen during this scan.
        :param path_index: State of the paths before the scan.
        :param recovered: Ids of unchanged files that were flagged missing before.
        :returns: None.
        """
        self._report(ScanStage.FINALIZE, 0, 0)

        missing_ids: List[int] = []
        for folder in folders:
            prefix = folder.rstrip('/') + '/'
            for path, entry in path_index.items():
                if entry.is_missing or path in found or not path.startswith(prefix):
                    continue
                missing_ids.append(entry.track_id)

        self._set_missing(missing_ids, True)
        self._set_missing(recovered, False)
        self.stats.tracks_missing = len(missing_ids)
        self.stats.tracks_recovered = len(recovered)

        now = datetime.datetime.now()
        for folder in folders:
            known = self.session.scalar(select(LibraryFolder.id).where(LibraryFolder.path == folder))
            if known is None:
                self.session.execute(insert(LibraryFolder).values(path=folder, recursive=True,
                                                                  dt_last_scan=now))
            else:
                self.session.execute(update(LibraryFolder).where(LibraryFolder.id == known)
                                     .values(dt_last_scan=now))
        self.session.commit()

    def _set_missing(self, track_ids: List[int], missing: bool) -> None:
        """Flip the missing flag on a list of tracks.

        :param track_ids: Ids to update.
        :param missing: Value of the flag.
        :returns: None.
        """
        for start in range(0, len(track_ids), _ID_CHUNK):
            batch = track_ids[start:start + _ID_CHUNK]
            self.session.execute(update(Track).where(Track.id.in_(batch)).values(is_missing=missing))
    # endregion

    # region helpers
    def _cancelled(self) -> bool:
        """Whether the scan was asked to stop.

        :returns: bool - True when it should return.
        """
        if self.cancel_event.is_set():
            self.stats.cancelled = True
            return True
        return False

    def _report(self, stage: ScanStage, done: int, total: int) -> None:
        """Hand the progress to the caller.

        :param stage: Current stage.
        :param done: Items handled.
        :param total: Items in total, 0 while it is still unknown.
        :returns: None.
        """
        if self.progress_callback is not None:
            self.progress_callback(stage, done, total)

    def _finish(self, started: float) -> ScanStats:
        """Close the scan and log what it did.

        :param started: Monotonic time the scan began at.
        :returns: ScanStats - What the scan did.
        """
        self.stats.elapsed = time.monotonic() - started
        self._report(ScanStage.DONE, self.stats.files_seen, self.stats.files_seen)
        print_d(f"Library scan: {self.stats.files_seen} files, "
                f"+{self.stats.tracks_added} tracks, ~{self.stats.tracks_updated} updated, "
                f"{self.stats.tracks_unchanged} unchanged, +{self.stats.albums_added} albums, "
                f"+{self.stats.covers_added} covers, {self.stats.errors} errors, "
                f"{self.stats.elapsed:.1f}s"
                + (" (cancelled)" if self.stats.cancelled else ""))
        return self.stats
    # endregion
