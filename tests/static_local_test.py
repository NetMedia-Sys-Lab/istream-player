# test_with_pytest.py


import json
import unittest
from unittest.mock import patch

from parameterized import parameterized

from istream_player.config.config import PlayerConfig
from istream_player.core.module_composer import PlayerComposer


class StaticTest(unittest.IsolatedAsyncioTestCase):
    def make_config(self, abr: str):
        config = PlayerConfig(
            input="./tests/resources/static_1as_5repr_4seg.mpd",
            run_dir="./runs/test",
            mod_abr=abr,
            mod_analyzer=["data_collector:plots_dir=./runs/test/plots"],
            mod_downloader="local:bw=100_000",
            time_factor=1
        )
        config.static.max_initial_bitrate = 100_000
        return config

    @parameterized.expand([["dash"]])
    async def test_static(self, abr: str):
        save_file_patcher = patch("istream_player.modules.analyzer.analyzer.PlaybackAnalyzer.save_file")
        save_file_mock = save_file_patcher.start()

        composer = PlayerComposer()
        composer.register_core_modules()

        async with composer.make_player(self.make_config(abr)) as player:
            await player.run()

        save_file_patcher.stop()
        save_file_mock.assert_called_once()
        [path, data] = save_file_mock.call_args.args
        print(json.dumps(data, indent=4))
        assert len(data["segments"]) == 4


if __name__ == "__main__":
    unittest.main()
