import logging
import os
from os.path import join
from typing import BinaryIO

from istream_player.config.config import PlayerConfig
from istream_player.core.analyzer import Analyzer
from istream_player.core.downloader import (DownloadEventListener,
                                            DownloadManager)
from istream_player.core.module import Module, ModuleOption
from istream_player.core.player import PlayerEventListener
from istream_player.models import State


@ModuleOption("file_saver", requires=[DownloadManager])
class FileContentListener(Module, Analyzer, DownloadEventListener, PlayerEventListener):
    files: dict[str, BinaryIO]
    log = logging.getLogger("FileContentListener")

    def __init__(self):
        self.files = {}

    async def setup(self, config: PlayerConfig, downloaders: list[DownloadManager], **kwargs):
        assert config.run_dir, "--run-dir is required by file_saver module"

        for dl in downloaders:
            dl.add_listener(self)
            dl.add_listener(self)

        self.download_dir = join(config.run_dir, "downloaded")
        os.makedirs(self.download_dir, exist_ok=True)

    async def on_state_change(self, position: float, old_state: State, new_state: State):
        # self.log.info(f"{new_state}")
        if new_state == State.END:
            for url, file in self.files.items():
                self.log.info(f"{url} : {file.tell()} bytes")
                file.close()
        pass

    async def on_bytes_transferred(self, length: int, url: str, position: int, size: int, content) -> None:
        if url not in self.files:
            self.files[url] = open(join(self.download_dir, url.split("/")[-1]), "wb")
        self.files[url].write(content)
        # self.log.info(f"Saved {size} bytes")
        pass
