import asyncio
import logging
import ssl
from typing import AsyncIterator, Optional, Set, Tuple, cast
from urllib.parse import urlparse

from aioquic.asyncio.client import connect
from aioquic.h3.connection import H3_ALPN
from aioquic.h3.events import H3Event
from aioquic.quic.configuration import QuicConfiguration
from aioquic.tls import SessionTicket

from istream_player.config.config import PlayerConfig
from istream_player.core.downloader import (DownloadEventListener,
                                            DownloadManager, DownloadRequest)
from istream_player.core.module import Module, ModuleOption
from istream_player.modules.downloader.quic.event_parser import \
    H3EventParserImpl
from istream_player.modules.downloader.quic.protocol import HttpProtocol


@ModuleOption("quic")
class QuicClientImpl(Module, DownloadManager):
    """
    QuickClientImpl will use only one thread, but be multiplexing by tuning a queue
    """

    log = logging.getLogger("QuicClientImpl")

    def __init__(self):
        super().__init__()
        self._client: Optional[HttpProtocol] = None

        self._close_event: Optional[asyncio.Event] = None
        self.event_parser = H3EventParserImpl(listeners=[])
        """
        When this _close_event got set, the client will stop the connection completely.
        """

        self._canceled_urls: Set[str] = set()
        self._event_queue: Optional[asyncio.Queue[Tuple[H3Event, str]]] = None
        self._download_queue: asyncio.Queue[DownloadRequest] = asyncio.Queue()

    async def setup(self, *, config: PlayerConfig, **kwargs) -> None:
        secrets_log_file = open(config.ssl_keylog_file, "a") if config.ssl_keylog_file is not None else None

        self.quic_configuration = QuicConfiguration(
            alpn_protocols=H3_ALPN, is_client=True, verify_mode=ssl.CERT_NONE, **{"secrets_log_file": secrets_log_file}
        )

    def add_listener(self, listener: DownloadEventListener):
        super().add_listener(listener)
        self.event_parser.add_listener(listener)

    @property
    def is_busy(self):
        """
        QUIC supports multiple streams in the same connection.
        It will be never busy because you can add a new request at any moment.

        Returns
        -------
        is_busy: bool
            False
        """
        return False

    async def wait_complete(self, url) -> Optional[Tuple[bytes, int]]:
        return await self.event_parser.wait_complete(url)

    async def close(self):
        # This is to close the whole connection
        if self._close_event is not None:
            self._close_event.set()

    async def stop(self, url: str):
        # This is to stop only one stream
        if self._client is not None:
            await self._client.close_stream_of_url(url)
            await self.event_parser.close_stream(url)

    def save_session_ticket(self, ticket: SessionTicket) -> None:
        """
        Callback which is invoked by the TLS engine when a new session ticket
        is received.
        """
        self.log.info("New session ticket received from server: " + ticket.server_name)
        self.quic_configuration.session_ticket = ticket

    async def _download_internal(self, request: DownloadRequest) -> AsyncIterator[Tuple[H3Event, str]]:
        url = request.url
        self.log.info(f"Downloading Internal: {url}")
        assert self._client is not None
        async for event in self._client.get(url, headers=request.headers):
            yield event, url

    # @critical_task()
    async def _download_loop(self):
        queue = asyncio.Queue()

        async def drain(iterator: AsyncIterator):
            async for i in iterator:
                await queue.put(i)

        async def read_new_request():
            while True:
                req = await self._download_queue.get()
                it = self._download_internal(req)
                asyncio.create_task(drain(it))

        asyncio.create_task(read_new_request())
        while True:
            event, url = await queue.get()
            await self.event_parser.parse(url, event)

    async def start(self, host, port, client_up_event=None):
        """
        Start the QUIC Client

        Parameters
        ----------
        host: str
            The hostname of the remote endpoint
        port: int
            The UDP port to connect to the remote endpoint
        client_up_event: asyncio.Event, optional
            If event is not None, set the event when the client is up
        """

        self._close_event = asyncio.Event()
        self._event_queue = asyncio.Queue()

        async with connect(
            host,
            port,
            configuration=self.quic_configuration,
            create_protocol=HttpProtocol,
            session_ticket_handler=self.save_session_ticket,
            local_port=0,
            wait_connected=False,
        ) as client:
            self._client = cast(HttpProtocol, client)
            task = asyncio.create_task(self._download_loop())
            if client_up_event is not None:
                client_up_event.set()
            await self._close_event.wait()
            task.cancel()

        self._client = None
        self._close_event = None
        self._event_queue = None

    async def download(self, request: DownloadRequest, save=False) -> Optional[bytes]:
        url = request.url
        # Client hasn't been started. Start the client.
        if self._client is None:
            parsed = urlparse(url)
            host = parsed.hostname
            if parsed.port is not None:
                port = parsed.port
            else:
                port = 443
            event = asyncio.Event()
            asyncio.create_task(self.start(host, port, client_up_event=event))
            await event.wait()

        for listener in self.listeners:
            await listener.on_transfer_start(url)
        await self._download_queue.put(request)
        return None

    def cancel_read_url(self, url: str):
        if self._client is not None:
            self._client.cancel_read(url)

    async def drop_url(self, url: str):
        if self._client is not None:
            await self._client.close_stream_of_url(url)
        await self.event_parser.drop_stream(url)


