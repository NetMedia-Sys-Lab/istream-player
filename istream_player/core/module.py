from abc import ABC, abstractmethod
from typing import Type

from istream_player.config.config import PlayerConfig


class ModuleInterface(ABC):
    pass


class Module(ABC):
    __mod_name__: str
    __mod_default__: bool
    __mod_requires__: list[Type[ModuleInterface] | str]

    @abstractmethod
    async def setup(self, config: PlayerConfig, *args) -> None:
        """Setup module

        Args:
            modules (ModuleStore): All modules
            config (PlayerConfig): All config
        """

    async def cleanup(self) -> None:
        """Player is closing. Cleaup everything"""
        pass

    async def run(self) -> None:
        pass


def ModuleOption(name: str, default: bool = False, requires: list[Type[ModuleInterface] | str] = []):
    def _decorator(mod_class: Type[Module]):
        mod_class.__mod_name__ = name
        mod_class.__mod_default__ = default
        mod_class.__mod_requires__ = requires
        return mod_class

    return _decorator
