from abc import ABC, abstractmethod
from typing import Optional

from istream_player.core.module import ModuleInterface
from istream_player.models import MPD
from istream_player.models.mpd_objects import Segment


class MPDProvider(ModuleInterface, ABC):
    @property
    @abstractmethod
    def mpd(self) -> Optional[MPD]:
        pass

    @abstractmethod
    async def stop(self):
        """
        Stop the repeated updates if there is one
        """
        pass

    @abstractmethod
    async def update(self):
        """
        Update the MPD file
        """

    @abstractmethod
    async def available(self) -> MPD:
        """Wait till an MPD file is available. If already downloaded returns immediately

        Returns:
            MPD: Latest MPD Object
        """

    @abstractmethod
    def segment_by_url(self, url: str) -> Optional[Segment]:
        """Return Segment by URL if found.
        None if url is an initilization segment.
        Raises Exception otherwise

        Args:
            url (str): URL of segment / init

        Returns:
            Optional[Segment]: Segment if found else None
        """

    # @abstractmethod
    # def repr_to_quality(self, repr):
    #     """Return Quality level from representation ID"""
