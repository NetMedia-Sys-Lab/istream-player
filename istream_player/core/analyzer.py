

from abc import ABC

from istream_player.core.module import ModuleInterface


class Analyzer(ModuleInterface, ABC):
    """Only analyzes the playback
    """