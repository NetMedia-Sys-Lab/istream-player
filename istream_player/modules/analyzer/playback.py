import asyncio
import logging
import sys
from asyncio import create_subprocess_exec
from asyncio.subprocess import PIPE
from typing import Dict

from istream_player.config.config import PlayerConfig
from istream_player.core.analyzer import Analyzer
from istream_player.core.downloader import (DownloadEventListener,
                                            DownloadManager)
from istream_player.core.module import Module, ModuleOption
from istream_player.core.mpd_provider import MPDProvider
from istream_player.core.player import Player, PlayerEventListener
from istream_player.models import Segment, State


class Decoder:
    log = logging.getLogger("FfmpegDecoder")

    def __init__(self, decoded: Dict[str, bytearray]) -> None:
        self.decoded = decoded
        self.decode_queue = asyncio.Queue()
        pass

    async def start(self):
        self._proc = await create_subprocess_exec(
            # "ffplay", "-", "-loglevel", "quiet", stdin=PIPE
            "ffmpeg",
            "-f",
            "mp4",
            "-i",
            "-",
            "-pix_fmt",
            "rgb32",
            "-f",
            "rawvideo",
            "-loglevel",
            "error",
            "-",
            # "-y",
            # "/tmp/test.y4m",
            stdin=PIPE,
            stdout=PIPE,
            stderr=sys.stderr,
        )
        self._reader = asyncio.Task(self.read())
        self.total_sent = 0

    # async def stdout_read(self, n: int, buff: bytearray):
    #     count = 0
    #     while count < n:
    #         b = self._proc.stdout.read(n)
    #         bytearray.append()

    async def read(self):
        assert self._proc.stdout is not None
        while True:
            url = await self.decode_queue.get()
            self.log.debug(f"Reading decoded bytes for url : {url}")
            frame_size = 1024 * 576 * 4
            frame_index = 0
            # buff = self.decoded[url]
            while True:
                count = 0
                while count < frame_size:
                    b = await self._proc.stdout.read(frame_size)
                    if not b:
                        raise Exception("Debugger process stdout closed")
                    # buff.extend(b)
                    count += len(b)
                frame_index += 1
                self.log.info(f"***************** Frame decoded: {frame_index}")

    def stop(self):
        assert self._proc.stdin is not None
        try:
            self._reader.cancel()
            self._proc.stdin.close()
            self._proc.terminate()
        except ProcessLookupError:
            pass

    def send(self, buff):
        self._proc.stdin.write(buff)  # type: ignore
        self.total_sent += len(buff)
        self.log.debug(f"Sent bytes: {self.total_sent=}")

    async def schedule_decode(self, url):
        self.log.debug("--------------- Schedulign deode")
        self.decoded[url] = bytearray()
        await self.decode_queue.put(url)


@ModuleOption("playback", requires=[Player, "segment_downloader", MPDProvider])
class Playback(Module, Analyzer, PlayerEventListener, DownloadEventListener):
    log = logging.getLogger("Playback")

    def __init__(self) -> None:
        super().__init__()
        self.file_content: dict[str, bytearray] = {}
        # self.ffplay = Popen(['ffplay'], stdout=PIPE, stdin=PIPE, stderr=PIPE)
        # self.ffplay = None
        self.decoders: Dict[str, Decoder] = {}
        self.encoded_buffer = {}
        self.decoded_buffer = {}

    async def setup(self, config: PlayerConfig, player: Player, segment_downloader: DownloadManager, mpd_provider: MPDProvider):
        self.mpd_provider = mpd_provider
        player.add_listener(self)
        segment_downloader.add_listener(self)

    async def on_transfer_start(self, url) -> None:
        segment = self.mpd_provider.segment_by_url(url)
        if segment is None:
            # Init URL, Start new decoder process
            if url not in self.decoders:
                self.log.debug(f"Opening subprocess for stream - {url}")
                decoder = Decoder(self.decoded_buffer)
                self.decoders[url] = decoder
                await decoder.start()
        else:
            # Segment
            pass

    async def on_bytes_transferred(self, length: int, url: str, position: int, size: int, content) -> None:
        segment = self.mpd_provider.segment_by_url(url)
        # self.log.debug(f"{self.decoders=}")
        if segment is None:
            self.decoders[url].send(content)
        else:
            decoder = self.decoders[segment.init_url]
            decoder.send(content)
            if url not in self.decoded_buffer:
                await decoder.schedule_decode(url)
        pass

    async def on_state_change(self, position: float, old_state: State, new_state: State):
        if new_state == State.END:
            for decoder in self.decoders.values():
                decoder.stop()

    async def on_segment_playback_start(self, segments: Dict[int, Segment]):
        """Callback executed when a segment is played by the player

        Args:
            segment (Segment): The playback segment
        """
        # seg_name = segment.url.split("/")[-1]
        # init_name = 'init-' + seg_name.split('-')[1] + ".m4s"
        # seg_path = join(self.run_dir, "downloaded", seg_name)
        # init_path = join(self.run_dir, "downloaded", init_name)
        # self.log.info(f"{init_path} {seg_path}")

        # cat_ps = Popen(['cat', init_path, seg_path], stdout=PIPE)
        # assert self.ffplay is not None and self.ffplay.stdin is not None
        # self.log.info(segment.init_url, len(self.file_content[segment.init_url]))
        # self.log.info(f"{segment.url}, {list(self.file_content.keys())}")
        # self.ffplay.stdin.write(self.file_content[segment.init_url])
        # self.log.info(f"{len(self.file_content[segment.url])=}")
        # Thread(target=self.ffplay.stdin.write, args=[self.file_content[segment.url]]).start()
        # del


