import asyncio
from abc import ABC, abstractmethod
from typing import Dict, Tuple

from istream_player.core.module import ModuleInterface
from istream_player.models.mpd_objects import Segment


class BufferEventListener(ABC):
    async def on_buffer_level_change(self, buffer_level: float):
        pass


# TODO: Add multiple adaptation support segment. Multiple segments per iteration
class BufferManager(ModuleInterface, ABC):
    def __init__(self) -> None:
        super().__init__()
        self.listeners: list[BufferEventListener] = []

    def add_listener(self, listener: BufferEventListener):
        if listener not in self.listeners:
            self.listeners.append(listener)

    @property
    @abstractmethod
    def buffer_level(self) -> float:
        """
        Returns
        -------
        buffer_level: float
            Current buffer level in seconds
        """
        pass

    @property
    @abstractmethod
    def buffer_change_cond(self) -> asyncio.Condition:
        """
        Returns
        -------
        buffer_change_cond: asyncio.Condition
            async condition to wait for buffer event
        """

    @abstractmethod
    async def enqueue_buffer(self, segments: Dict[int, Segment]) -> None:
        """
        Enqueue some buffers into the buffer manager

        Parameters
        ----------
        segments: Dict[int, Segment]
            The map of adaptation_id to downloaded segment
        """
        pass

    @abstractmethod
    def get_next_segment(self) -> Tuple[Dict[int, Segment], float]:
        """Return the next segment from the buffer immediately. Raise exception if no item

        Returns:
            Tuple[Dict[int, Segment], float]: Map of adaptation_id and segment, Max duration of segment
        """

    @abstractmethod
    async def dequeue_buffer(self):
        """Remove last segment from buffer"""

    @abstractmethod
    def is_empty(self) -> bool:
        """
        Returns if True there are no segments in buffer
        """
        pass
