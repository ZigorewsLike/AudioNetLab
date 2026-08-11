from typing import List, NamedTuple, Sequence

from src.api.db import library_repo
from src.api.db.db_handler import create_session, session_scope
from src.core.file_system.FileMetaController_class import FileMetaController
from src.core.library.cover_cache import CoverCache
from src.core.log_system import print_d


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

    The single place a delete happens, whatever asked for it. The database goes first
    and commits on its own, then the files are removed: a file that cannot be deleted
    then leaves the library consistent and only leaves garbage on disk, where a failure
    the other way round would leave a cover row pointing at nothing.

    The audio files themselves are never touched, only the path is forgotten.

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


def _remove_files(track_ids: List[int], stats: library_repo.DeleteStats,
                  meta_controller: FileMetaController) -> DeletionResult:
    """Drop the per-track registry folders and the orphaned cover files of a delete.

    :param track_ids: Tracks that were removed from the database.
    :param stats: What the database delete reported.
    :param meta_controller: Registry controller, owns the data/registry folders.
    :returns: DeletionResult - The database counts with the freed bytes filled in.
    """
    for track_id in track_ids:
        meta_controller.delete_track(track_id)
    bytes_freed = sum(CoverCache.discard(cover_hash) for cover_hash in stats.cover_hashes)

    result = DeletionResult(track_ids=track_ids,
                            tracks=stats.tracks,
                            albums=stats.albums,
                            artists=stats.artists,
                            covers=len(stats.cover_hashes),
                            bytes_freed=bytes_freed)
    print_d(f"Deleted {result.tracks} tracks, {result.albums} albums, {result.artists} artists, "
            f"{result.covers} covers ({result.bytes_freed // 1024} KB)")
    return result