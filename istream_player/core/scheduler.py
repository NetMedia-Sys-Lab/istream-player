from abc import ABC, abstractmethod
from typing import Dict
from istream_player.core.bw_meter import DownloadStats

from istream_player.core.module import ModuleInterface
from istream_player.models.mpd_objects import Segment


class SchedulerEventListener(ABC):
    async def on_segment_download_start(self, index: int, adap_bw: Dict[int, float], segments: Dict[int, Segment]):
        """
        Callback when one segment is started to be downloaded

        Parameters
        ----------
        index: int
            The index of the downloading segment
        selections: Dict[int, int]
            The selection of representation for each adaptation set.
            The key is the adaptation set ID, and the value is the selected representation ID.
        """
        pass

    async def on_segment_download_complete(self, index: int, segments: Dict[int, Segment], stats: Dict[int, DownloadStats]):
        """
        Callback when one segment is completely downloaded

        Parameters
        ----------
        index: int
            The index of the downloading segment
        """
        pass


class Scheduler(ModuleInterface, ABC):
    def __init__(self) -> None:
        self.listeners: list[SchedulerEventListener] = []

    def add_listener(self, listener: SchedulerEventListener):
        if listener not in self.listeners:
            self.listeners.append(listener)

    @abstractmethod
    async def stop(self):
        pass

    @property
    @abstractmethod
    def is_end(self):
        pass

    @abstractmethod
    async def cancel_task(self, index):
        pass

    @abstractmethod
    async def drop_index(self, index):
        pass
