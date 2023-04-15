import asyncio
import logging
from collections import deque
from typing import Callable, Deque, Dict, Optional, Union, AsyncIterator
from urllib.parse import urlparse

import aioquic
import wsproto
import wsproto.events
from aioquic.asyncio.protocol import QuicConnectionProtocol
from aioquic.h0.connection import H0Connection
from aioquic.h3.connection import H3Connection
from aioquic.h3.events import (
    DataReceived,
    H3Event,
    HeadersReceived,
    PushPromiseReceived,
)
from aioquic.quic.events import QuicEvent

logger = logging.getLogger("client")

HttpConnection = Union[H0Connection, H3Connection]

USER_AGENT = "aioquic/" + aioquic.__version__


def encode_variable_length_integer(num: int) -> bytes:
    """
    Encode variable length integer to bytes according to QUIC draft
    """
    if num <= 63:
        return bytes([num])
    elif num <= 16383:
        b = num.to_bytes(2, byteorder='big')
        b[0] |= 0x40
        return b
    elif num <= 1073741823:
        b = num.to_bytes(4, byteorder='big')
        b[0] |= 0x80
        return b
    else:
        b = num.to_bytes(8, byteorder='big')
        b[0] |= 0xC0
        return b


class URL:
    def __init__(self, url: str) -> None:
        parsed = urlparse(url)

        self.authority = parsed.netloc
        self.full_path = parsed.path
        if parsed.query:
            self.full_path += "?" + parsed.query
        self.scheme = parsed.scheme
        self.url = url


class HttpRequest:
    def __init__(
            self, method: str, url: URL, content: bytes = b"", headers=None
    ) -> None:
        if headers is None:
            headers = {}
        self.content = content
        self.headers = headers
        self.method = method
        self.url = url


class WebSocket:
    def __init__(
            self, http: HttpConnection, stream_id: int, transmit: Callable[[], None]
    ) -> None:
        self.http = http
        self.queue: asyncio.Queue[str] = asyncio.Queue()
        self.stream_id = stream_id
        self.subprotocol: Optional[str] = None
        self.transmit = transmit
        self.websocket = wsproto.Connection(wsproto.ConnectionType.CLIENT)

    async def close(self, code=1000, reason="") -> None:
        """
        Perform the closing handshake.
        """
        data = self.websocket.send(
            wsproto.events.CloseConnection(code=code, reason=reason)
        )
        self.http.send_data(stream_id=self.stream_id, data=data, end_stream=True)
        self.transmit()

    async def recv(self) -> str:
        """
        Receive the next message.
        """
        return await self.queue.get()

    async def send(self, message: str) -> None:
        """
        Send a message.
        """
        assert isinstance(message, str)

        data = self.websocket.send(wsproto.events.TextMessage(data=message))
        self.http.send_data(stream_id=self.stream_id, data=data, end_stream=False)
        self.transmit()

    def http_event_received(self, event: H3Event) -> None:
        if isinstance(event, HeadersReceived):
            for header, value in event.headers:
                if header == b"sec-websocket-protocol":
                    self.subprotocol = value.decode()
        elif isinstance(event, DataReceived):
            self.websocket.receive_data(event.data)

        for ws_event in self.websocket.events():
            self.websocket_event_received(ws_event)

    def websocket_event_received(self, event: wsproto.events.Event) -> None:
        if isinstance(event, wsproto.events.TextMessage):
            self.queue.put_nowait(event.data)


class HttpProtocol(QuicConnectionProtocol):
    log = logging.getLogger("HttpProtocol")

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        self.pushes: Dict[int, Deque[H3Event]] = {}
        self._http: Optional[HttpConnection] = None
        self._request_events: Dict[int, asyncio.Queue[H3Event]] = {}
        self._websockets: Dict[int, WebSocket] = {}
        self._url_stream_id: Dict[str, int] = {}
        self._requests_tasks: Dict[str, asyncio.Task] = {}

        if self._quic.configuration.alpn_protocols[0].startswith("hq-"):
            self._http = H0Connection(self._quic)
        else:
            self._http = H3Connection(self._quic)

    async def get(self, url: str, headers=None) -> AsyncIterator[H3Event]:
        """
        Perform a GET request.
        """
        if headers is None:
            headers = {}
        async for event in self._request(HttpRequest(method="GET", url=URL(url), headers=headers)):
            yield event

    async def post(self, url: str, data: bytes, headers=None) -> Deque[H3Event]:
        """
        Perform a POST request.
        """
        if headers is None:
            headers = {}
        async for event in self._request(HttpRequest(method="POST", url=URL(url), content=data, headers=headers)):
            yield event

    async def websocket(self, url: str, subprotocols=None) -> WebSocket:
        """
        Open a WebSocket.
        """
        if subprotocols is None:
            subprotocols = []
        request = HttpRequest(method="CONNECT", url=URL(url))
        stream_id = self._quic.get_next_available_stream_id()
        websocket = WebSocket(
            http=self._http, stream_id=stream_id, transmit=self.transmit
        )

        self._websockets[stream_id] = websocket

        headers = [
            (b":method", b"CONNECT"),
            (b":scheme", b"https"),
            (b":authority", request.url.authority.encode()),
            (b":path", request.url.full_path.encode()),
            (b":protocol", b"websocket"),
            (b"user-agent", USER_AGENT.encode()),
            (b"sec-websocket-version", b"13"),
        ]
        if subprotocols:
            headers.append(
                (b"sec-websocket-protocol", ", ".join(subprotocols).encode())
            )
        self._http.send_headers(stream_id=stream_id, headers=headers)

        self.transmit()

        return websocket

    def http_event_received(self, event: H3Event) -> None:
        if isinstance(event, (HeadersReceived, DataReceived)):
            stream_id = event.stream_id
            if stream_id in self._request_events:
                # http
                asyncio.ensure_future(self._request_events[event.stream_id].put(event))
            elif stream_id in self._websockets:
                # websocket
                websocket = self._websockets[stream_id]
                websocket.http_event_received(event)

            elif event.push_id in self.pushes:
                # push
                self.pushes[event.push_id].append(event)

        elif isinstance(event, PushPromiseReceived):
            self.pushes[event.push_id] = deque()
            self.pushes[event.push_id].append(event)

    def quic_event_received(self, event: QuicEvent) -> None:
        #  pass event to the HTTP layer
        if self._http is not None:
            for http_event in self._http.handle_event(event):
                self.http_event_received(http_event)

    async def _request(self, request: HttpRequest) -> AsyncIterator[H3Event]:
        stream_id = self._quic.get_next_available_stream_id()
        self._url_stream_id[request.url.url] = stream_id
        self.log.info(f"Use stream id {stream_id} for url {request.url.url}")
        self._http.send_headers(
            stream_id=stream_id,
            headers=[
                        (b":method", request.method.encode()),
                        (b":scheme", request.url.scheme.encode()),
                        (b":authority", request.url.authority.encode()),
                        (b":path", request.url.full_path.encode()),
                        (b"user-agent", USER_AGENT.encode()),
                    ] + [(k.encode(), v.encode()) for (k, v) in request.headers.items()],
        )
        self._http.send_data(stream_id=stream_id, data=request.content, end_stream=True)

        queue = asyncio.Queue()
        self._request_events[stream_id] = queue
        self.transmit()

        while True:
            task = asyncio.create_task(queue.get())
            self._requests_tasks[request.url.url] = task
            try:
                event = await task
                yield event
                if isinstance(event, DataReceived):
                    if event.stream_ended:
                        return
            except asyncio.CancelledError:
                self.log.info(f"Cancel Reading {request.url.url}")
                return

    async def close_stream_of_url(self, url):
        stream_id = self._url_stream_id.get(url, None)
        assert stream_id is not None
        self.log.info(f"Send STOP_SENDING, stream id: {stream_id}, URL: {url}")
        print(aioquic.__file__)
        self._quic.stop_stream(stream_id, 0)

    def cancel_read(self, url):
        self.log.info(f"cancel_read: {url}")
        self._requests_tasks[url].cancel()
