from typing import List, Optional


class PlayQueue:
    """Ordered list of track ids with a cursor on the current one.

    Pure data, no Qt: the playback controller owns one of these and drives it, and the
    queue view reads and edits it. "Context" is the set of tracks a play action started
    from, an album or the visible track list, so next and previous walk exactly what the
    user was looking at.
    """

    def __init__(self):
        """Create an empty queue.

        :returns: None.
        """
        self._items: List[int] = []
        self._index: int = -1  # -1 when the queue is empty

    def set_context(self, track_ids: List[int], start_index: int = 0) -> Optional[int]:
        """Replace the queue with a new context and place the cursor.

        :param track_ids: Track ids in play order.
        :param start_index: Position of the track to start on.
        :returns: int - The track the cursor landed on, None when the context is empty.
        """
        self._items = list(track_ids)
        if not self._items:
            self._index = -1
        else:
            self._index = min(max(start_index, 0), len(self._items) - 1)
        return self.current()

    def set_context_on_track(self, track_ids: List[int], track_id: int) -> Optional[int]:
        """Replace the queue with a context and place the cursor on a given track.

        :param track_ids: Track ids in play order.
        :param track_id: Track the cursor should start on.
        :returns: int - The track the cursor landed on, None when the context is empty.
        """
        try:
            start = list(track_ids).index(track_id)
        except ValueError:
            start = 0
        return self.set_context(track_ids, start)

    def current(self) -> Optional[int]:
        """Track under the cursor.

        :returns: int - Current track id, None when the queue is empty.
        """
        if 0 <= self._index < len(self._items):
            return self._items[self._index]
        return None

    @property
    def index(self) -> int:
        """Cursor position.

        :returns: int - Index of the current track, -1 when empty.
        """
        return self._index

    @property
    def items(self) -> List[int]:
        """The queued track ids in order.

        :returns: List[int] - A copy of the queue.
        """
        return list(self._items)

    def upcoming(self) -> List[int]:
        """Track ids after the current one.

        :returns: List[int] - The tail of the queue, empty when the current is last.
        """
        if self._index < 0:
            return []
        return self._items[self._index + 1:]

    def has_next(self) -> bool:
        """Whether there is a track after the current one.

        :returns: bool - True when go_next would move.
        """
        return 0 <= self._index < len(self._items) - 1

    def has_prev(self) -> bool:
        """Whether there is a track before the current one.

        :returns: bool - True when go_prev would move.
        """
        return self._index > 0

    def go_next(self) -> Optional[int]:
        """Advance the cursor by one.

        :returns: int - The new current track, None when already at the end.
        """
        if not self.has_next():
            return None
        self._index += 1
        return self.current()

    def go_prev(self) -> Optional[int]:
        """Move the cursor back by one.

        :returns: int - The new current track, None when already at the start.
        """
        if not self.has_prev():
            return None
        self._index -= 1
        return self.current()

    def jump_to_index(self, index: int) -> Optional[int]:
        """Move the cursor to a position.

        :param index: Target position.
        :returns: int - The track there, None when the position is out of range.
        """
        if 0 <= index < len(self._items):
            self._index = index
            return self.current()
        return None

    def jump_to_track(self, track_id: int) -> Optional[int]:
        """Move the cursor to the first occurrence of a track.

        :param track_id: Track to move to.
        :returns: int - The track when found, None when it is not queued.
        """
        try:
            return self.jump_to_index(self._items.index(track_id))
        except ValueError:
            return None

    def append(self, track_id: int) -> None:
        """Add a track to the end of the queue.

        :param track_id: Track to add.
        :returns: None.
        """
        self._items.append(track_id)
        if self._index < 0:
            self._index = 0

    def remove_at(self, index: int) -> None:
        """Remove a track from the queue, keeping the cursor on the same track.

        :param index: Position to remove.
        :returns: None.
        """
        if not (0 <= index < len(self._items)):
            return
        del self._items[index]
        if index < self._index:
            self._index -= 1  # The current track shifted left
        elif index == self._index:
            # The current track was removed; clamp so the cursor stays in range
            self._index = min(self._index, len(self._items) - 1)

    def remove_ids(self, track_ids: List[int]) -> bool:
        """Drop every occurrence of a set of tracks, for tracks deleted from the library.

        The cursor follows the track it was on when that track survives. When it was one
        of the removed ones it lands on whatever took its place, the same way remove_at
        clamps, so next and previous still make sense afterwards.

        :param track_ids: Tracks to remove.
        :returns: bool - True when the queue changed.
        """
        targets = set(track_ids)
        if not targets:
            return False
        kept = [(position, item) for position, item in enumerate(self._items) if item not in targets]
        if len(kept) == len(self._items):
            return False

        survivors_before = sum(1 for position, _ in kept if position < self._index)
        self._items = [item for _, item in kept]
        if not self._items:
            self._index = -1
        else:
            self._index = min(survivors_before, len(self._items) - 1)
        return True

    def move(self, from_index: int, to_index: int) -> None:
        """Reorder a track, following the current one so it stays selected.

        :param from_index: Position to move from.
        :param to_index: Position to move to.
        :returns: None.
        """
        if not (0 <= from_index < len(self._items)) or not (0 <= to_index < len(self._items)):
            return
        current_id = self.current()
        item = self._items.pop(from_index)
        self._items.insert(to_index, item)
        if current_id is not None:
            self._index = self._items.index(current_id)

    def clear(self) -> None:
        """Empty the queue.

        :returns: None.
        """
        self._items = []
        self._index = -1

    def __len__(self) -> int:
        """Number of queued tracks.

        :returns: int - Queue length.
        """
        return len(self._items)
