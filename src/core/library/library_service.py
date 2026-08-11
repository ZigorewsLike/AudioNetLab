import os
import shutil
from typing import List, NamedTuple, Optional, Sequence, Set, Tuple

from src.api.db import library_repo
from src.api.db.db_handler import create_session, session_scope
from src.core.file_system.FileMetaController_class import FileMetaController
from src.core.library.cover_cache import CoverCache
from src.core.log_system import print_d, print_e
from src.global_constants import COVER_CACHE_SIZES, PATH_TO_COVER_CACHE, PATH_TO_LAST_REGISTRY


class DeletionResult(NamedTuple):
    """What one delete removed, for the caller to report and to refresh from."""
    track_ids: List[int]  # The tracks that were asked for, whether or not they existed
    tracks: int
    albums: int
    artists: int
    covers: int
    bytes_freed: int


_EMPTY_RESULT = DeletionResult(track_ids=[], tracks=0, albums=0, artists=0, covers=0, bytes_freed=0)


def delete_tracks(track_ids: Sequence[int], meta_controller: FileMetaController) -> DeletionResult:
    """Remove tracks from the library, with their registry folders and cover files.

    The database commits first and the files go after, so a file that cannot be removed
    leaves the library consistent and only leaves garbage on disk. The audio files
    themselves are never touched, only the path is forgotten.

    :param track_ids: Tracks to remove.
    :param meta_controller: Registry controller, owns the data/registry folders.
    :returns: DeletionResult - What was removed.
    """
    ids = list(dict.fromkeys(int(track_id) for track_id in track_ids))
    if not ids:
        return _EMPTY_RESULT

    with session_scope() as session:
        stats = library_repo.delete_tracks(session, ids)
    return _remove_files(ids, stats, meta_controller)


def delete_album(album_id: int, meta_controller: FileMetaController) -> DeletionResult:
    """Remove an album and every track on it.

    :param album_id: Album id.
    :param meta_controller: Registry controller, owns the data/registry folders.
    :returns: DeletionResult - What was removed.
    """
    session = create_session()
    try:
        ids = library_repo.get_album_track_ids(session, album_id)
    finally:
        session.close()

    with session_scope() as session:
        stats = library_repo.delete_album(session, album_id)
    return _remove_files(ids, stats, meta_controller)


class MaintenanceResult(NamedTuple):
    """What a whole-library sweep threw away."""
    albums: int
    artists: int
    covers: int            # Cover rows the database no longer needed
    cover_files: int
    registry_folders: int
    bytes_freed: int


def run_maintenance() -> MaintenanceResult:
    """Drop the rows, cached covers and registry folders the library has no use for.

    Runs off the library as it is now rather than off what a delete reported, so it also
    picks up what an earlier version left behind and what a failed delete could not
    remove. Safe to call at any time, but not while a scan is writing.

    :returns: MaintenanceResult - What was removed.
    """
    with session_scope() as session:
        # Albums first: an album that goes may take the last reference to a cover with it
        albums, artists = library_repo.delete_unused_albums(session)
        unused_hashes = library_repo.delete_unused_covers(session)
    discarded = [CoverCache.discard(cover_hash) for cover_hash in unused_hashes]
    discarded_files = sum(files for files, _ in discarded)
    bytes_freed = sum(size for _, size in discarded)

    session = create_session()
    try:
        known_hashes = library_repo.get_cover_hashes(session)
        known_tracks = library_repo.get_track_ids(session)
    finally:
        session.close()

    cover_files, cover_bytes = _sweep_cover_files(known_hashes)
    folders, registry_bytes = _sweep_registry(known_tracks)

    result = MaintenanceResult(albums=albums,
                               artists=artists,
                               covers=len(unused_hashes),
                               cover_files=cover_files + discarded_files,
                               registry_folders=folders,
                               bytes_freed=bytes_freed + cover_bytes + registry_bytes)
    print_d(f"Maintenance removed {result.albums} albums, {result.artists} artists, "
            f"{result.covers} covers, {result.cover_files} cover files, "
            f"{result.registry_folders} registry folders ({result.bytes_freed // 1024} KB)")
    return result


def _sweep_cover_files(known_hashes: Set[str]) -> Tuple[int, int]:
    """Delete cached cover files no cover row claims, and the stale sizes of the rest.

    Only files named the way the cache names them are considered, anything else in the
    folder is left alone.

    :param known_hashes: Hashes the library still references.
    :returns: Tuple[int, int] - Files removed and bytes freed.
    """
    if not os.path.isdir(PATH_TO_COVER_CACHE):
        return 0, 0
    removed = 0
    freed = 0
    for prefix in os.listdir(PATH_TO_COVER_CACHE):
        folder = os.path.join(PATH_TO_COVER_CACHE, prefix)
        if not os.path.isdir(folder):
            continue
        for name in os.listdir(folder):
            cover_hash, size = _parse_cover_name(name)
            if cover_hash is None:
                continue
            if cover_hash in known_hashes and size in COVER_CACHE_SIZES:
                continue
            path = os.path.join(folder, name)
            try:
                file_size = os.path.getsize(path)
                os.remove(path)
            except OSError as e:
                print_e(f"Cover cleanup error: {path}", e)
                continue
            removed += 1
            freed += file_size
        try:
            os.rmdir(folder)
        except OSError:
            pass  # Still holds covers
    return removed, freed


def _parse_cover_name(name: str) -> Tuple[Optional[str], Optional[int]]:
    """Split a cached cover file name into the hash and the size it was written for.

    :param name: File name inside a cover cache folder.
    :returns: Tuple[str, int] - Hash and size, both None when the name is not one of ours.
    """
    stem, extension = os.path.splitext(name)
    if extension.lower() != ".jpg" or "_" not in stem:
        return None, None
    cover_hash, _, size = stem.rpartition("_")
    if not cover_hash or not size.isdigit():
        return None, None
    return cover_hash, int(size)


def _sweep_registry(known_tracks: Set[int]) -> Tuple[int, int]:
    """Delete the registry folders of tracks that are not in the library any more.

    :param known_tracks: Track ids the library still holds.
    :returns: Tuple[int, int] - Folders removed and bytes freed.
    """
    if not os.path.isdir(PATH_TO_LAST_REGISTRY):
        return 0, 0
    removed = 0
    freed = 0
    for name in os.listdir(PATH_TO_LAST_REGISTRY):
        folder = os.path.join(PATH_TO_LAST_REGISTRY, name)
        # A folder is named after a track id; anything else in there is not ours to touch
        if not name.isdigit() or not os.path.isdir(folder):
            continue
        if int(name) in known_tracks:
            continue
        folder_size = _folder_size(folder)
        shutil.rmtree(folder, ignore_errors=True)
        if os.path.isdir(folder):
            print_e(f"Registry cleanup could not remove {folder}")
            continue
        removed += 1
        freed += folder_size
    return removed, freed


def _folder_size(folder: str) -> int:
    """Add up the size of every file in a folder.

    :param folder: Folder to measure.
    :returns: int - Total size in bytes.
    """
    total = 0
    for root, _, files in os.walk(folder):
        for name in files:
            try:
                total += os.path.getsize(os.path.join(root, name))
            except OSError:
                pass
    return total


def _remove_files(track_ids: List[int], stats: library_repo.DeleteStats,
                  meta_controller: FileMetaController) -> DeletionResult:
    """Drop the per-track registry folders and the cover files a delete left unused.

    :param track_ids: Tracks that were removed from the database.
    :param stats: What the database delete reported.
    :param meta_controller: Registry controller, owns the data/registry folders.
    :returns: DeletionResult - The database counts with the freed bytes filled in.
    """
    for track_id in track_ids:
        meta_controller.delete_track(track_id)
    bytes_freed = sum(CoverCache.discard(cover_hash)[1] for cover_hash in stats.cover_hashes)

    result = DeletionResult(track_ids=track_ids,
                            tracks=stats.tracks,
                            albums=stats.albums,
                            artists=stats.artists,
                            covers=len(stats.cover_hashes),
                            bytes_freed=bytes_freed)
    print_d(f"Deleted {result.tracks} tracks, {result.albums} albums, {result.artists} artists, "
            f"{result.covers} covers ({result.bytes_freed // 1024} KB)")
    return result