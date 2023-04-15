# test_with_pytest.py


import pathlib
import unittest
from unittest.mock import patch

from aiohttp import web

from istream_player.config.config import PlayerConfig
from istream_player.core.module_composer import PlayerComposer


# @unittest.skip("Cannot bind to port inside test")
class StaticTest(unittest.IsolatedAsyncioTestCase):
    def make_config(self):
        config = PlayerConfig(
            input="http://localhost:8080/resources/static_1as_5repr_4seg.mpd",
            run_dir="./runs/test",
            mod_abr='dash',
            mod_downloader="tcp",
            mod_analyzer=["data_collector"],
            time_factor=0
        )
        config.static.max_initial_bitrate = 100_000
        return config

    async def asyncSetUp(self):
        app = web.Application()
        app.router.add_static("/", pathlib.Path(__file__).parent, show_index=True)

        self.runner = web.AppRunner(app)
        await self.runner.setup()
        site = web.TCPSite(self.runner, "localhost", 8080)
        await site.start()

    async def asyncTearDown(self) -> None:
        await self.runner.shutdown()

    async def test_static_tcp(self):
        save_file_patcher = patch("istream_player.modules.analyzer.analyzer.PlaybackAnalyzer.save_file")
        save_file_mock = save_file_patcher.start()

        composer = PlayerComposer()
        composer.register_core_modules()
        async with composer.make_player(self.make_config()) as player:
            await player.run()

        save_file_patcher.stop()
        save_file_mock.assert_called_once()
        [path, data] = save_file_mock.call_args.args
        # print(json.dumps(data, indent=4))
        assert len(data["segments"]) == 4


if __name__ == "__main__":
    unittest.main()

