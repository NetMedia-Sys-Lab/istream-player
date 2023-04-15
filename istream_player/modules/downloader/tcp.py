import asyncio
import logging
import ssl
from typing import Optional, Tuple

import aiohttp

from istream_player.config.config import PlayerConfig
from istream_player.core.downloader import DownloadManager, DownloadRequest
from istream_player.core.module import Module, ModuleOption
from istream_player.utils.async_utils import critical_task


@ModuleOption("tcp")
class TCPClientImpl(Module, DownloadManager):
    log = logging.getLogger("TCPClientImpl")

    def __init__(self):
        super().__init__()
        self._download_queue: asyncio.Queue[DownloadRequest] = asyncio.Queue()
        self._session = None
        self._session_close_event = asyncio.Event()
        self._is_busy = False
        self._downloading_task = None  # type: Optional[asyncio.Task]
        self._downloading_task_resp = None

        self._completed_urls = set()
        self._partially_accepted_urls = set()
        self._cancelled_urls = set()

        self._headers = {}
        self._content = {}

        self._waiting_urls = {}

    async def setup(self, config: PlayerConfig, **kwargs):
        self.ssl_keylog_file = config.ssl_keylog_file

    async def cleanup(self) -> None:
        await self.close()

    async def wait_complete(self, url: str) -> Optional[Tuple[bytes, int]]:
        # If url is in partially accepted set, return read bytes and length
        if url in self._partially_accepted_urls:
            content = self._content[url]
            return bytes(content), int(self._headers[url]["CONTENT-LENGTH"])
        # If the url has been dropped, return None
        if url in self._cancelled_urls:
            return None
        # Wait the url to be completed
        if url not in self._completed_urls:
            self._waiting_urls[url] = asyncio.Event()
            await self._waiting_urls[url].wait()
            del self._waiting_urls[url]
        # If the url has been canceled, return None
        if url in self._cancelled_urls:
            self._cancelled_urls.remove(url)
            return None
        if url in self._completed_urls:
            self._completed_urls.remove(url)
        content = self._content[url]
        size = int(self._headers[url]["Content-Length"])
        return bytes(content), size

    def cancel_read_url(self, url: str):
        return

    async def drop_url(self, url: str):
        await self.stop(url)

    @property
    def is_busy(self):
        return self._is_busy

    async def download(self, request: DownloadRequest, save: bool = False) -> Optional[bytes]:
        url = request.url
        self._waiting_urls[url] = asyncio.Event()
        self._content[url] = bytearray()
        if self._session is None:
            session_start_event = asyncio.Event()
            asyncio.create_task(self._create_session(session_start_event))
            await session_start_event.wait()

        for listener in self.listeners:
            await listener.on_transfer_start(url)
        await self._download_queue.put(request)
        return None

    @critical_task()
    async def _download_inner(self, request: DownloadRequest):
        assert self._session is not None
        url = request.url
        async with self._session.get(url, headers=request.headers) as resp:
            self._downloading_task_resp = resp
            self._headers[url] = dict(resp.headers)
            try:
                size = int(resp.headers["CONTENT-LENGTH"])
            except KeyError:
                self.log.info(resp.headers)
                self.log.info(await resp.content.read())
                exit(1)
            async for chunk in resp.content.iter_any():
                self._content[url] += bytearray(chunk)
                self.log.info(
                    f"Bytes transferred: length: {len(chunk)}, position: {len(self._content[url])}, size: {size}, url: {url}"
                )
                for listener in self.listeners:
                    await listener.on_bytes_transferred(len(chunk), url, len(self._content[url]), size, chunk)
        self.log.info(f"Transfer ends: {len(self._content[url])}")
        self._completed_urls.add(url)
        self._waiting_urls[url].set()
        for listener in self.listeners:
            await listener.on_transfer_end(len(self._content[url]), url)

    async def _download_task(self):
        while True:
            self._is_busy = False
            req_url = await self._download_queue.get()
            self._is_busy = True

            self._downloading_task = asyncio.create_task(self._download_inner(req_url))

    async def _create_session(self, session_start_event):
        ssl_context = ssl.SSLContext(protocol=ssl.PROTOCOL_TLS_SERVER, verify_mode=ssl.CERT_NONE)
        ssl_context.verify_mode = ssl.CERT_NONE
        # ssl_context.keylog_filename = self.ssl_keylog_file
        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=ssl_context)) as session:
            self._session = session
            session_start_event.set()
            task = asyncio.create_task(self._download_task())
            await self._session_close_event.wait()
            task.cancel()

    async def close(self):
        if self._session_close_event is not None:
            self._session_close_event.set()

    async def stop(self, url: str):
        self.log.info("STOP DOWNLOADING: " + url)
        if self._downloading_task is not None:
            self._downloading_task.cancel()
            if (
                self._downloading_task_resp is not None
                and self._downloading_task_resp.connection is not None
                and self._downloading_task_resp.connection.transport is not None
            ):
                self._downloading_task_resp.connection.transport.abort()
        self._partially_accepted_urls.add(url)
        self._waiting_urls[url].set()
        for listener in self.listeners:
            await listener.on_transfer_end(len(self._content), url)
