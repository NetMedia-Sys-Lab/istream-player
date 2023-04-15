import argparse
import asyncio
import logging
from collections import defaultdict
from pprint import pformat
from typing import Any, Callable, Dict, Optional, Type, TypedDict

from istream_player.config.config import PlayerConfig
from istream_player.core.module import Module, ModuleInterface
from istream_player.modules.abr.abr_bandwidth import BandwidthABRController
from istream_player.modules.abr.abr_buffer import BufferABRController
from istream_player.modules.abr.abr_dash import DashABRController
from istream_player.modules.abr.abr_hybrid import HybridABRController
from istream_player.modules.analyzer.analyzer import PlaybackAnalyzer
from istream_player.modules.analyzer.event_logger import EventLogger
from istream_player.modules.analyzer.file_content_listener import \
    FileContentListener
from istream_player.modules.analyzer.playback import Playback
from istream_player.modules.buffer.buffer_manager import BufferManagerImpl
from istream_player.modules.bw_meter.bandwidth import BandwidthMeterImpl
from istream_player.modules.downloader.local import LocalClient
from istream_player.modules.downloader.quic.client import QuicClientImpl
from istream_player.modules.downloader.tcp import TCPClientImpl
from istream_player.modules.mpd.mpd_provider_impl import MPDProviderImpl
from istream_player.modules.player.player_dash import DASHPlayer
from istream_player.modules.scheduler.scheduler import SchedulerImpl

ModInitFnType = Callable[[str, Any, Any], Dict[str, Module]]


def first_non_none(*args):
    for arg in args:
        if arg is not None:
            return arg
    return None


def get_mod_name(val: str):
    return val.split(":", 1)[0].lower()


def get_mod_props(val: str):
    all_props = val.split(":", 1)
    if len(all_props) == 1:
        return {}

    def prop_key(prop):
        return prop.split("=", 1)[0]

    def prop_val(prop):
        return [*prop.split("=", 1), True][1]

    ret = {prop_key(prop): prop_val(prop) for prop in all_props[1].split(",")}
    # print(all_props[1].split(",")[0].split("=", 1), ret)
    return ret


class PlayerContext:
    log = logging.getLogger("PlayerContext")

    def __init__(self, config: PlayerConfig, modules: Dict[str, Dict[str, Module]], composer) -> None:
        self.modules = modules
        self.config = config
        self.composer = composer

    async def __aenter__(self):
        self.log.info("\tSetting up modules")
        for mod_type, mods in self.modules.items():
            self.log.debug(f"\t\t{mod_type} : {mods}")
        for mod_type, mods in self.modules.items():
            for mod_name, mod in mods.items():
                deps = self.composer.get_deps(mod.__class__.__mod_requires__)
                # print(f"Dependencies for {mod_name}")
                # pprint(deps)
                await mod.setup(self.config, *deps)
        return self

    async def __aexit__(self, *args):
        for mods in self.modules.values():
            for mod in mods.values():
                await mod.cleanup()

    async def run(self):
        tasks = []
        for mods in self.modules.values():
            for mod in mods.values():
                tasks.append(asyncio.create_task(mod.run(), name=f"TASK_MOD_{mod.__mod_name__}_RUN"))

        for task in tasks:
            await task


class ModuleCliConfig(TypedDict):
    help: Optional[str]
    required: Optional[bool]
    default: Optional[list[str] | str]
    # choices: list[str]
    allow_multi: Optional[bool]


class PlayerComposer:
    log = logging.getLogger("PlayerComposer")

    module_cli: Dict[str, ModuleCliConfig]
    module_init_fn: Dict[str, ModInitFnType]
    module_options: Dict[str, Dict[str, Type[Module]]]
    modules: Dict[str, Dict[str, Module]]

    def __init__(self) -> None:
        self.module_options = {}
        self.modules = defaultdict(dict)
        self.module_init_fn = {}
        self.module_cli = defaultdict(lambda: ModuleCliConfig(help="[Module]", allow_multi=False, default="", required=False))

    def get_deps(self, reqs: list[str | Type[ModuleInterface]]):
        deps = []
        for req in reqs:
            dep = {}
            if isinstance(req, str):
                for mods in self.modules.values():
                    for mod_name, mod in mods.items():
                        if mod_name == req:
                            dep[mod_name] = mod
            else:
                for mods in self.modules.values():
                    for mod_name, mod in mods.items():
                        if issubclass(mod.__class__, req):
                            dep[mod_name] = mod
            if len(dep) == 0:
                raise Exception(f"Module dependency not found : {req}")
            else:
                deps.append(dep.values() if len(dep) > 1 else list(dep.values())[0])
        return deps

    def create_arg_parser(self):
        parser = argparse.ArgumentParser(description="IStream DASH Player")

        class ModuleChoices(list[str]):
            # list subclass that uses lower() when testing for 'in'
            def __contains__(self, option: str):
                return super().__contains__(option.split(":", 1)[0].lower())

        parser.add_argument("--config", help="Configure using yaml/json", required=False)
        parser.add_argument("-i", "--input", help="Manifest (MPD) file location", type=str, required=True)
        parser.add_argument("-v", "--verbose", help="Enable debug level output", action="store_true", required=False)
        parser.add_argument("--time_factor", help="Mutiplication factor for time delayd. Use 0-1 for speedup.", type=float)
        parser.add_argument("--run_dir", '-d', help="Run directory", required=False)
        # pprint(self.module_cli)
        for mod_type, mods in self.module_options.items():
            cli_opt = self.module_cli[mod_type]
            parser.add_argument(
                f"--mod_{mod_type}",
                help=cli_opt["help"],
                required=bool(cli_opt["required"]),
                default=cli_opt["default"],
                choices=list(self.module_options[mod_type].keys()),
                action=("append" if cli_opt["allow_multi"] else "store"),
            )

        return parser

    async def run(self, config: PlayerConfig):
        async with self.make_player(config) as player:
            await player.run()

    def register_module(
        self,
        mod_type: str,
        mod_class: Type[Module] | list[Type[Module]],
        init_fn: ModInitFnType | None,
        # Optional
        mod_help: Optional[str] = None,
        mod_required: Optional[bool] = None,
        mod_default: Optional[str | list[str]] = None,
        mod_allow_multi: Optional[bool] = None,
    ):
        # Set or Update init_fn
        if init_fn is not None:
            self.module_init_fn[mod_type] = init_fn

        # Set or update module_cli
        prev_cli = self.module_cli[mod_type]
        new_cli = ModuleCliConfig(help=mod_help, required=mod_required, default=mod_default, allow_multi=mod_allow_multi)
        new_cli["help"] = first_non_none(mod_help, prev_cli["help"])
        new_cli["required"] = first_non_none(mod_required, prev_cli["required"])
        new_cli["default"] = first_non_none(mod_default, prev_cli["default"])
        new_cli["allow_multi"] = first_non_none(mod_allow_multi, prev_cli["allow_multi"])
        prev_cli.update(new_cli)

        if mod_type not in self.module_options:
            self.module_options[mod_type] = {}

        # Can register multiple modules in one call
        if isinstance(mod_class, list):
            for _mod_class in mod_class:
                if _mod_class.__mod_name__ in self.module_options[mod_type]:
                    raise Exception(f"Module with name {_mod_class.__mod_name__} alerady registerd under {mod_type}.")
                self.module_options[mod_type][_mod_class.__mod_name__] = _mod_class
        else:
            if mod_class.__mod_name__ in self.module_options[mod_type]:
                raise Exception(f"Module with name {mod_class.__mod_name__} alerady registerd under {mod_type}.")
            self.module_options[mod_type][mod_class.__mod_name__] = mod_class

    def make_player(self, config: PlayerConfig):
        if config.mod_downloader == "auto":
            if config.input.lower().startswith("http://") or config.input.lower().startswith("https://"):
                config.mod_downloader = "tcp"
            else:
                config.mod_downloader = "local"

        list(map(self.log.debug, pformat(config).splitlines()))

        for attr_name, val in config.__dict__.items():
            # All module config from player_config should start with "mod_"
            if not attr_name.startswith("mod_"):
                continue
            mod_type_name = attr_name[4:]
            if self.module_init_fn.get(mod_type_name) is None:
                raise Exception(f"Module init function not provided for module {mod_type_name}")
            self.modules[mod_type_name].update(self.module_init_fn[mod_type_name](mod_type_name, val, self))
        return PlayerContext(config, self.modules, self)

    def register_core_modules(self):
        self.register_module("mpd", [MPDProviderImpl], single_initializer, "MPD Provider", False, "mpd")
        self.register_module(
            "downloader", [LocalClient, TCPClientImpl, QuicClientImpl], downloader_initializer, "Downloader", False, "local"
        )
        self.register_module("bw", [BandwidthMeterImpl], single_initializer, "Bandwidth Estimation", False, "bw_meter")
        self.register_module(
            "abr",
            [DashABRController, BufferABRController, BandwidthABRController, HybridABRController],
            single_initializer,
            "Adaptive Bitrate Controller",
            False,
            "dash",
        )
        self.register_module("scheduler", [SchedulerImpl], single_initializer, "Segment download scheduler", False, "scheduler")
        self.register_module("buffer", [BufferManagerImpl], single_initializer, "Buffer manager", False, "buffer_manager")
        self.register_module("player", [DASHPlayer], single_initializer, "Headless DASH Streamer", False, "dash")
        self.register_module(
            "analyzer",
            [PlaybackAnalyzer, FileContentListener, Playback, EventLogger],
            multi_initializer,
            "Analyzers",
            False,
            mod_default=[],
            mod_allow_multi=True,
        )


def single_initializer(mod_type, mod_name, composer: PlayerComposer) -> Dict[str, Module]:
    if not isinstance(mod_name, str):
        raise Exception(f"Module type {mod_type} only supports single module. Provided {mod_name}")

    return {get_mod_name(mod_name): composer.module_options[mod_type][get_mod_name(mod_name)](**get_mod_props(mod_name))}


def multi_initializer(mod_type, val, composer: PlayerComposer) -> Dict[str, Module]:
    if isinstance(val, str):
        return single_initializer(mod_type, val, composer)
    elif isinstance(val, list):
        # print(mod_type, [get_mod_name(mod) for mod in val])
        return {get_mod_name(mod): composer.module_options[mod_type][get_mod_name(mod)](**get_mod_props(mod)) for mod in val}
    elif isinstance(val, dict):
        return {
            mod_key: composer.module_options[mod_type][get_mod_name(mod)](**get_mod_props(mod)) for mod_key, mod in val.items()
        }
    else:
        raise Exception(f"Invalid mod value '{val}' received for mod '{mod_type}'")


def downloader_initializer(mod_type, val, composer: PlayerComposer) -> Dict[str, Module]:
    if not isinstance(val, str):
        raise Exception(f"Module type {mod_type} only supports single module. Provided {val}")

    _cl = composer.module_options[mod_type][get_mod_name(val)]
    return {"mpd_downloader": _cl(**get_mod_props(val)), "segment_downloader": _cl(**get_mod_props(val))}

