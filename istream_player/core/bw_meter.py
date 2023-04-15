from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

from istream_player.core.module import ModuleInterface


@dataclass
class DownloadStats:
    total_bytes: int = 0
    received_bytes: int = 0
    stopped_bytes: int = 0

    start_time: Optional[float] = None
    stop_time: Optional[float] = None

    first_byte_at: Optional[float] = None
    last_byte_at: Optional[float] = None


class BandwidthUpdateListener(ABC):
    async def on_bandwidth_update(self, bw: float) -> None:
        """
        Parameters
        ----------
        bw: int
            The latest bandwidth estimate in bps (bytes per second)
        """
        pass

    # async def on_continuous_bw_update(self, bw: int) -> None:
    #     """
    #     Parameters
    #     ----------
    #     bw: int
    #         The instantaneous latest bandwidth estimate in bps (bytes per second)
    #     update_time: float
    #         The time at which this bandwidth is estimated
    #     """


class BandwidthMeter(ModuleInterface, ABC):
    def __init__(self) -> None:
        self.listeners: list[BandwidthUpdateListener] = []

    def add_listener(self, listener: BandwidthUpdateListener):
        """
        Add a listener to the bandwidth meter

        Parameters
        ----------
        listener
            An instance of BandwidthUpdateListener
        """
        if listener not in self.listeners:
            self.listeners.append(listener)

    @property
    @abstractmethod
    def bandwidth(self) -> float:
        """
        Returns
        -------
        bw: int
            The bandwidth estimate in bps (bytes per second)
        """
        pass

    @abstractmethod
    def get_stats(self, url: str) -> DownloadStats:
        """Return Download stats for the specified url

        Args:
            url (str): URL

        Returns:
            DownloadStats: DownloadStats
        """
