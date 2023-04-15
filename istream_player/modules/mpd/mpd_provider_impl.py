import logging
import time
from asyncio import Task
from typing import Dict, Optional

from istream_player.config.config import PlayerConfig
from istream_player.core.downloader import (DownloadManager, DownloadRequest,
                                            DownloadType)
from istream_player.core.module import Module, ModuleOption
from istream_player.core.mpd_provider import MPDProvider
from istream_player.models.mpd_objects import MPD, Segment
from istream_player.modules.mpd.parser import DefaultMPDParser
from istream_player.utils.async_utils import AsyncResource, critical_task


@ModuleOption("mpd", default=True, requires=["mpd_downloader"])
class MPDProviderImpl(Module, MPDProvider):
    log = logging.getLogger("MPDProviderImpl")

    def __init__(self):
        self.parser = DefaultMPDParser()
        self.last_updated = 0

        self._mpd_res: AsyncResource[Optional[MPD]] = AsyncResource(None)
        self._segments_by_url: Dict[str, Optional[Segment]] = {}
        self._task: Optional[Task] = None
        # self._repr_quality: Dict[int, int] = {}

    async def setup(self, config: PlayerConfig, mpd_downloader: DownloadManager, **kwargs):
        self.update_interval = config.static.update_interval
        self.download_manager = mpd_downloader
        self.mpd_url = config.input

    @property
    def mpd(self) -> Optional[MPD]:
        return self._mpd_res.value

    # def repr_to_quality(self, repr: int):
    #     return self._repr_quality[repr]

    async def available(self) -> MPD:
        value = await self._mpd_res.value_non_none()
        assert value is not None
        return value

    def segment_by_url(self, url: str) -> Optional[Segment]:
        return self._segments_by_url[url]

    @critical_task()
    async def update(self):
        if self.mpd is not None and (time.time() - self.last_updated) < self.update_interval:
            return
        await self.download_manager.download(DownloadRequest(self.mpd_url, DownloadType.MPD), save=True)
        content, size = await self.download_manager.wait_complete(self.mpd_url)
        text = content.decode("utf-8")
        mpd = self.parser.parse(text, url=self.mpd_url)
        self._mpd_res.value = mpd
        for adap_set in mpd.adaptation_sets.values():
            for repr in adap_set.representations.values():
                for seg in repr.segments.values():
                    self._segments_by_url[seg.url] = seg
                    self._segments_by_url[seg.init_url] = None

        self.last_updated = time.time()

    # @critical_task()
    # async def update_repeatedly(self):
    #     assert self._mpd is not None
    #     while self._mpd.type == "dynamic":
    #         await self.update()
    #         await asyncio.sleep(self.update_interval)
    #     self.log.info(f"MPD file changed from dynamic to {self._mpd.type}")

    async def run(self):
        assert self.mpd_url is not None
        await self.update()
        assert self.mpd is not None

    async def stop(self):
        self.log.info("Stopping MPD Provider")
        if self._task is not None:
            self._task.cancel()
        await self.download_manager.close()
