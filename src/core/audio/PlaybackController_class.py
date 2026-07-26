import os
from typing import List, Optional, TYPE_CHECKING

from PyQt6 import QtCore
from PyQt6.QtCore import QObject

from src.api.db.db_handler import create_session
from src.api.db.models import Track
from src.core.audio.PlayQueue_class import PlayQueue
from src.core.log_system import print_d
from src.enums import PlayerState

if TYPE_CHECKING:
    from src.forms import MainForm

# No track id, sent when playback has nothing loaded
NO_TRACK = -1


class PlaybackController(QObject):
    """Owns the play queue and the notion of what is playing.

    Every view that shows a playing indicator, the album page, the track list and the
    queue panel, reads it from here rather than tracking its own guess, so a track that
    starts, pauses or auto-advances is reflected the same everywhere. The controller
    resolves a track id to a file and hands it to the main form to decode and play; it
    does not touch the audio device itself.

    :signals: currentTrackChanged (int) - id of the track now loaded, NO_TRACK for none,
              playbackStateChanged (object) - the PlayerState of the current track,
              queueChanged () - the queue contents or cursor moved
    """
    currentTrackChanged = QtCore.pyqtSignal(int)
    playbackStateChanged = QtCore.pyqtSignal(object)
    queueChanged = QtCore.pyqtSignal()

    def __init__(self, mf: "MainForm", *args, **kwargs):
        """Create the controller.

        :param mf: Main form, used to open a resolved file.
        :returns: None.
        """
        super().__init__(*args, **kwargs)
        self.mf = mf
        self.queue = PlayQueue()
        self._current_track_id: int = NO_TRACK
        self._state: PlayerState = PlayerState.NONE

    # region state
    @property
    def current_track_id(self) -> int:
        """Track currently loaded.

        :returns: int - Track id, NO_TRACK when nothing is loaded.
        """
        return self._current_track_id

    @property
    def state(self) -> PlayerState:
        """Playback state of the current track.

        :returns: PlayerState - The state.
        """
        return self._state

    def is_playing(self, track_id: int) -> bool:
        """Whether a track is the one loaded and not stopped.

        :param track_id: Track id to test.
        :returns: bool - True when the track is the current one.
        """
        return track_id == self._current_track_id and self._current_track_id != NO_TRACK
    # endregion

    # region commands
    def play_context(self, track_ids: List[int], start_index: int = 0) -> None:
        """Play a list of tracks, starting at a position.

        :param track_ids: Track ids in play order, an album or a visible list.
        :param start_index: Index of the track to start on.
        :returns: None.
        """
        if self.queue.set_context(track_ids, start_index) is None:
            return
        self.queueChanged.emit()
        self._open_current()

    def play_track(self, track_ids: List[int], track_id: int) -> None:
        """Play one track and queue the rest of its context after it.

        :param track_ids: Track ids of the context in play order.
        :param track_id: Track to start on.
        :returns: None.
        """
        if self.queue.set_context_on_track(track_ids, track_id) is None:
            return
        self.queueChanged.emit()
        self._open_current()

    def play_next(self, auto: bool = False) -> None:
        """Advance to the next track.

        At the end of the queue it simply stops; autoplay does not wrap around.

        :param auto: True when called by the end-of-track autoplay.
        :returns: None.
        """
        if self.queue.go_next() is None:
            if auto:
                print_d("Queue finished")
            return
        self.queueChanged.emit()
        self._open_current()

    def play_prev(self) -> None:
        """Move to the previous track.

        :returns: None.
        """
        if self.queue.go_prev() is None:
            return
        self.queueChanged.emit()
        self._open_current()

    def jump_to(self, track_id: int) -> None:
        """Play a track already in the queue.

        :param track_id: Track to jump to.
        :returns: None.
        """
        if self.queue.jump_to_track(track_id) is None:
            return
        self.queueChanged.emit()
        self._open_current()

    def has_next(self) -> bool:
        """Whether a next track exists.

        :returns: bool - True when play_next would move.
        """
        return self.queue.has_next()

    def has_prev(self) -> bool:
        """Whether a previous track exists.

        :returns: bool - True when play_prev would move.
        """
        return self.queue.has_prev()
    # endregion

    # region streamer feedback
    @QtCore.pyqtSlot()
    def on_track_ended(self) -> None:
        """Advance the queue when a track played to its end. GUI thread.

        :returns: None.
        """
        self.play_next(auto=True)

    def on_streamer_state(self, state: PlayerState) -> None:
        """Mirror the streamer state so the views can show play or pause. GUI thread.

        :param state: New streamer state.
        :returns: None.
        """
        # The STOP the streamer fires the instant a track ends is immediately followed by
        # the next track opening, so it is not broadcast as a real stop during autoplay
        if state is PlayerState.STOP and self._state is PlayerState.PLAY and self.queue.has_next():
            return
        self._state = state
        self.playbackStateChanged.emit(state)
    # endregion

    # region internal
    def _open_current(self) -> None:
        """Open the track under the cursor, skipping any whose file is gone.

        :returns: None.
        """
        track_id = self.queue.current()
        path = self._resolve_path(track_id) if track_id is not None else None

        # Skip forward over tracks whose file has disappeared
        while track_id is not None and (path is None or not os.path.exists(path)):
            if not self.queue.has_next():
                print_d("No playable file left in the queue")
                return
            track_id = self.queue.go_next()
            path = self._resolve_path(track_id) if track_id is not None else None
            self.queueChanged.emit()

        if track_id is None or path is None:
            return
        self._current_track_id = track_id
        self.currentTrackChanged.emit(track_id)
        self.mf.open_file(path, track_id)

    @staticmethod
    def _resolve_path(track_id: int) -> Optional[str]:
        """Read the file path of a track from the database.

        :param track_id: Track id.
        :returns: str - Path, None when the track is gone.
        """
        session = create_session()
        try:
            track = session.get(Track, track_id)
            return track.path if track is not None else None
        finally:
            session.close()
    # endregion
