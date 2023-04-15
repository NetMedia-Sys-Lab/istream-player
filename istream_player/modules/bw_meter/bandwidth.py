import logging
import time
from typing import Dict

from istream_player.config.config import PlayerConfig
from istream_player.core.bw_meter import BandwidthMeter, DownloadStats
from istream_player.core.downloader import DownloadEventListener, DownloadManager
from istream_player.core.module import Module, ModuleOption
from istream_player.core.scheduler import Scheduler, SchedulerEventListener
from istream_player.models.mpd_objects import Segment


@ModuleOption("bw_meter", default=True, requires=["segment_downloader", Scheduler])
class BandwidthMeterImpl(Module, BandwidthMeter, DownloadEventListener, SchedulerEventListener):
    log = logging.getLogger("BandwidthMeterImpl")

    def __init__(self):
        super().__init__()
        self.stats: Dict[str, DownloadStats] = {}
        self.total_bytes = 0
        self.start_time = 0

    async def setup(self, config: PlayerConfig, segment_downloader: DownloadManager, scheduler: Scheduler):
        self._bw = config.static.max_initial_bitrate
        self.smooth_factor = config.static.smoothing_factor
        segment_downloader.add_listener(self)
        scheduler.add_listener(self)

    @property
    def bandwidth(self) -> float:
        return self._bw

    async def on_transfer_start(self, url) -> None:
        if self.start_time == 0:
            self.start_time = time.time()
        self.stats[url] = DownloadStats(start_time=time.time())

    async def on_transfer_end(self, size: int, url: str) -> None:
        stats = self.stats.get(url)
        if stats is None:
            return
        stats.stop_time = time.time()
        if stats.stopped_bytes is not None:
            stats.stopped_bytes = size

    async def on_bytes_transferred(self, length: int, url: str, position: int, size: int, content: bytes) -> None:
        stats = self.stats.get(url)
        if stats is None:
            return
        self.total_bytes += length
        stats.received_bytes += length
        stats.total_bytes = size
        if stats.first_byte_at is None:
            stats.first_byte_at = time.time()
            stats.last_byte_at = stats.first_byte_at
        else:
            stats.last_byte_at = time.time()

    async def on_transfer_canceled(self, url: str, position: int, size: int) -> None:
        stats = self.stats.get(url)
        if stats is None:
            return
        stats.stopped_bytes = stats.received_bytes
        stats.stop_time = time.time()

    def get_stats(self, url: str) -> DownloadStats:
        return self.stats[url]

    async def on_segment_download_complete(self, index: int, segments: Dict[int, Segment], stats: Dict[int, DownloadStats]):
        curr_bw = 8 * self.total_bytes / (time.time() - self.start_time)
        self._bw = self._bw * self.smooth_factor + curr_bw * (1 - self.smooth_factor)
        for listener in self.listeners:
            await listener.on_bandwidth_update(self._bw)

        # Clear last segments
        self.stats.clear()
        self.total_bytes = 0
        self.start_time = 0
