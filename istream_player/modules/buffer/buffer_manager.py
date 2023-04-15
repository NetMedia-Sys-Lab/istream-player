import asyncio
from typing import Dict, Tuple

from istream_player.config.config import PlayerConfig
from istream_player.core.buffer import BufferManager
from istream_player.core.module import Module, ModuleOption
from istream_player.models.mpd_objects import Segment

# Item1 : Map of adaptation_id and segments, Item2 : Max duration of selected segments
QueueItemType = Tuple[Dict[int, Segment], float]


@ModuleOption("buffer_manager", default=True)
class BufferManagerImpl(Module, BufferManager):
    def __init__(self) -> None:
        super().__init__()
        self._buffer_level: float = 0
        self._segments: asyncio.Queue[QueueItemType] = asyncio.Queue()
        self._buffer_change_cond: asyncio.Condition = asyncio.Condition()

    async def publish_buffer_level(self):
        for listener in self.listeners:
            await listener.on_buffer_level_change(self.buffer_level)

    async def setup(self, config: PlayerConfig):
        pass

    async def run(self) -> None:
        await self.publish_buffer_level()

    async def enqueue_buffer(self, segments: Dict[int, Segment]) -> None:
        async with self._buffer_change_cond:
            max_duration = max(map(lambda s: s[1].duration, segments.items()))
            await self._segments.put((segments, max_duration))
            self._buffer_level += max_duration
            await self.publish_buffer_level()
            self._buffer_change_cond.notify_all()

    def get_next_segment(self) -> QueueItemType:
        return self._segments._queue[0]  # type: ignore

    async def dequeue_buffer(self):
        async with self._buffer_change_cond:
            segments, max_duration = await self._segments.get()
            self._buffer_level -= max_duration
            await self.publish_buffer_level()
            self._buffer_change_cond.notify_all()
            # return segments, max_duration

    @property
    def buffer_level(self):
        return self._buffer_level

    @property
    def buffer_change_cond(self) -> asyncio.Condition:
        return self._buffer_change_cond

    def is_empty(self) -> bool:
        return self._segments.empty()
