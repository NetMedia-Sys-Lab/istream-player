from abc import ABC, abstractmethod
import asyncio
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple

from istream_player.core.module import ModuleInterface


class DownloadType(Enum):
    SEGMENT = 1
    STREAM_INIT = 2
    MPD = 3


@dataclass
class DownloadRequest:
    url: str
    req_type: DownloadType
    headers: Dict[str, str] = field(default_factory=dict)


class DownloadEventListener(ABC):
    async def on_bytes_transferred(self, length: int, url: str, position: int, size: int, content: bytes) -> None:
        """
        Parameters
        ----------
        length: int
            The length transferred since last call, in bytes
        url: str
            The url of current request
        position: int
            The current position of the stream, in bytes
        size: int
            The size of the content: in bytes
            :param content:

        """
        pass

    async def on_transfer_end(self, size: int, url: str) -> None:
        """
        Parameters
        ----------
        size: int
            The size of the complete transmission
        url: str
            The url of the complete transmission
        """
        pass

    async def on_transfer_start(self, url) -> None:
        """
        Parameters
        ----------
        url: str
            The url of the transmission
        """
        pass

    async def on_transfer_canceled(self, url: str, position: int, size: int) -> None:
        """
        Parameters
        ----------
        url
            The url of the canceled transfer
        position
            The position when the transfer got canceled
        size
            The complete size of the stream
        """
        pass


class DownloadManager(ModuleInterface, ABC):
    def __init__(self) -> None:
        self.listeners: List[DownloadEventListener] = []

    @property
    @abstractmethod
    def is_busy(self):
        """
        If a download session is running, return True. Return False otherwise.
        """
        pass

    @abstractmethod
    async def download(self, req: DownloadRequest, save: bool = False) -> Optional[bytes]:
        """
        Start download

        Parameters
        ----------
        url: str
            The URL of the source to download from
        save: bool
            if save is True, this method return the bytes received. Return None otherwise.

        Returns
        -------
        content: bytes, optional
            None if save is False, the content bytes otherwise.
        """
        pass

    @abstractmethod
    async def close(self):
        """
        Close the download session

        """
        pass

    @abstractmethod
    async def stop(self, url: str):
        """
        Stop one request

        url:
            The full request URL to stop
        """
        pass

    def add_listener(self, listener: DownloadEventListener):
        """
        Dynamically add a listener

        Parameters
        ----------
        listener
            An instance of DownloadEventListener
        """

        if listener not in self.listeners:
            self.listeners.append(listener)

    @abstractmethod
    async def wait_complete(self, url: str) -> Tuple[bytes, int]:
        """
        Wait the stream to complete

        Parameters
        ----------
        url:
            The URL to wait for

        Returns
        -------
            The return value could be None, meaning that the stream got dropped.
            It could be a tuple, the bytes as the first element and size as the second element.
        """
        pass

    @abstractmethod
    def cancel_read_url(self, url: str):
        pass

    @abstractmethod
    async def drop_url(self, url: str):
        """
        Drop the URL downloading process
        """
        pass
