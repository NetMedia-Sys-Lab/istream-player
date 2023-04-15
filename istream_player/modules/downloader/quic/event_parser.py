import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Set, Tuple, cast

from aioquic.h3.events import DataReceived, H3Event, HeadersReceived

from istream_player.core.downloader import DownloadEventListener


class H3EventParser(ABC):
    @abstractmethod
    async def wait_complete(self, url: str) -> Optional[Tuple[bytes, int]]:
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
    async def parse(self, url: str, event: H3Event):
        pass

    @abstractmethod
    def add_listener(self, listener: DownloadEventListener):
        pass

    @abstractmethod
    async def close_stream(self, url: str):
        """
        Cancel waiting for streams.
        wait_complete will return the bytes and size it has been read
        """
        pass

    @abstractmethod
    async def drop_stream(self, url: str):
        """
        Drop the stream and stop reading immediately.
        wait_complete will return None when this method got invoked
        """
        pass


class H3EventParserImpl(H3EventParser):
    log = logging.getLogger("H3EventParserImpl")

    def __init__(self, listeners: List[DownloadEventListener]):
        self.listeners = listeners if listeners is not None else []

        self._completed_urls = set()
        self._waiting_urls: Dict[str, asyncio.Event] = dict()
        self._content_lengths: Dict[str, int] = dict()
        self._contents: Dict[str, bytearray] = dict()
        self._partially_accepted_urls: Set[str] = set()
        self._canceled_urls: Set[str] = set()

    @staticmethod
    def parse_headers(headers: List[Tuple[bytes, bytes]]) -> Dict[str, str]:
        result = dict()
        for header in headers:
            key, value = header
            result[key.decode('utf-8')] = value.decode('utf-8')
        return result

    async def wait_complete(self, url: str) -> Optional[Tuple[bytes, int]]:
        # If url is in partially accepted set, return read bytes and length
        if url in self._partially_accepted_urls:
            content = self._contents[url]
            return bytes(content), self._content_lengths[url]
        # If the url has been dropped, return None
        if url in self._canceled_urls:
            return None
        # Wait the url to be completed
        if url not in self._completed_urls:
            self._waiting_urls[url] = asyncio.Event()
            await self._waiting_urls[url].wait()
            del self._waiting_urls[url]
        # If the url has been canceled, return None
        if url in self._canceled_urls:
            self._canceled_urls.remove(url)
            return None
        if url in self._completed_urls:
            self._completed_urls.remove(url)
        content = self._contents[url]
        size = self._content_lengths[url]
        return bytes(content), size

    async def parse(self, url: str, event: H3Event):
        self.log.info(f"Event {event.__class__.__name__} received for {url}")
        if isinstance(event, HeadersReceived):
            headers = self.parse_headers(event.headers)
            size = int(headers.get("content-length", 0))
            self._content_lengths[url] = size
        else:
            event = cast(DataReceived, event)
            size = self._content_lengths[url]

            if url not in self._contents:
                self._contents[url] = bytearray()

            self._contents[url].extend(event.data)
            position = len(self._contents[url])

            for listener in self.listeners:
                await listener.on_bytes_transferred(len(event.data), url, position, size, event.data)

            if url in self._partially_accepted_urls:
                return

            if size == position:
                self._completed_urls.add(url)
                if url in self._waiting_urls:
                    self._waiting_urls[url].set()
                for listener in self.listeners:
                    await listener.on_transfer_end(size, url)

    def add_listener(self, listener: DownloadEventListener):
        self.listeners.append(listener)

    async def close_stream(self, url: str):
        self._partially_accepted_urls.add(url)
        if url in self._waiting_urls:
            self._waiting_urls[url].set()
        for listener in self.listeners:
            await listener.on_transfer_end(len(self._contents[url]), url)

    async def drop_stream(self, url: str):
        self._canceled_urls.add(url)
        if url in self._waiting_urls:
            self._waiting_urls[url].set()
        for listener in self.listeners:
            await listener.on_transfer_canceled(url, len(self._contents[url]), self._content_lengths[url])
