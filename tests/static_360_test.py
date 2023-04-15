# test_with_pytest.py


from dataclasses import dataclass
from pathlib import Path, PosixPath
from stat import S_IFDIR, S_IFREG
from typing import Literal
import unittest
from random import randbytes
from unittest.mock import patch

from istream_player.config.config import PlayerConfig
from istream_player.core.module_composer import PlayerComposer
from istream_player.modules.downloader.local import LocalClient

MOCK_FILE_CONTEN = randbytes(20_000)


def mock_request_read():
    async def _mock(self: LocalClient, url: str):
        # print("Mock request called", url)
        if not url.endswith(".mpd"):
            await self.transfer_queue.put((url, bytes(MOCK_FILE_CONTEN)))
            await self.transfer_queue.put((url, None))
        else:
            with open(url, "rb") as f:
                while True:
                    data = f.read(self.max_packet_size)
                    # print(f"Putting {len(data)} bytes for {url}")
                    await self.transfer_queue.put((url, data))
                    if not data:
                        break

    return _mock


def mock_path_stat():

    @dataclass
    class MockStat():
        st_size = len(MOCK_FILE_CONTEN)
        st_mode: int = S_IFREG

    def _mock(path: PosixPath, *args, **kwargs):
        if str(path).endswith('.mpd') or str(path).endswith('.m4s'):
            return MockStat()
        else:
            return MockStat(st_mode=S_IFDIR)

    return _mock


class StaticTest(unittest.IsolatedAsyncioTestCase):
    def make_config(self):
        config = PlayerConfig(
            input="./tests/resources/static_360.mpd",
            # input="./dataset/360-sonali/18/final.mpd",
            # input="./dataset/videos/av1-1sec/Aspen/output.mpd",
            run_dir="./runs/test",
            # mod_abr="fixed:quality=0",
            mod_analyzer=["data_collector:plots_dir=./runs/test/plots"],
            mod_downloader="local:bw=500_000",
            time_factor=1,
            select_as="-",
        )
        config.static.max_initial_bitrate = 100_000
        return config

    @patch("istream_player.modules.downloader.local.LocalClient.request_read", new_callable=mock_request_read)
    @patch("pathlib.Path.stat", new_callable=mock_path_stat)
    @patch("istream_player.modules.analyzer.analyzer.PlaybackAnalyzer.save_file")
    async def test_static_local360(self, p_save_file, p_stat, p_request_read):
        composer = PlayerComposer()
        composer.register_core_modules()
        async with composer.make_player(self.make_config()) as player:
            await player.run()

        p_save_file.assert_called_once()
        [path, data] = p_save_file.call_args.args
        # print(json.dumps(data, indent=4))

        NUM_AS = 25
        NUM_SEG = 30
        assert len(data["segments"]) == NUM_AS * NUM_SEG


if __name__ == "__main__":
    unittest.main()
