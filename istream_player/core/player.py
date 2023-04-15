from abc import ABC, abstractmethod
from typing import Dict

from istream_player.core.module import ModuleInterface
from istream_player.models.mpd_objects import Segment
from istream_player.models.player_objects import State


class PlayerEventListener(ABC):
    async def on_state_change(self, position: float, old_state: State, new_state: State):
        pass

    async def on_position_change(self, position):
        pass

    async def on_segment_playback_start(self, segments: Dict[int, Segment]):
        """Callback executed when a segment is played by the player

        Args:
            segment (Segment): The playback segment
        """


class Player(ModuleInterface, ABC):
    def __init__(self) -> None:
        self.listeners: list[PlayerEventListener] = []

    def add_listener(self, listener: PlayerEventListener):
        if listener not in self.listeners:
            self.listeners.append(listener)

    @property
    @abstractmethod
    def state(self) -> State:
        """
        Get current state

        Returns
        -------
        state: State
            The current state
        """
        pass

    @abstractmethod
    def stop(self) -> None:
        """
        Stop the playback and reset everything
        """
        pass

    @abstractmethod
    def pause(self) -> None:
        """
        Pause the playback
        """
        pass
