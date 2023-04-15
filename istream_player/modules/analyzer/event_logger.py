import logging
import time
from typing import Dict

from istream_player.config.config import PlayerConfig
from istream_player.core.analyzer import Analyzer
from istream_player.core.module import Module, ModuleOption
from istream_player.core.mpd_provider import MPDProvider
from istream_player.core.player import Player, PlayerEventListener
from istream_player.core.scheduler import Scheduler, SchedulerEventListener
from istream_player.models import State
from istream_player.models.mpd_objects import Segment
from istream_player.modules.analyzer.exp_events import ExpEvent_Progress, ExpEvent_State
from istream_player.modules.analyzer.exp_recorder import ExpWriterJson


@ModuleOption("progress_logger", requires=[MPDProvider, Scheduler, Player])
class EventLogger(Module, Analyzer, SchedulerEventListener, PlayerEventListener):
    log = logging.getLogger("EventLogger")

    def __init__(
        self,
    ):
        """
        Log events to console and events file
        Parameters
        ----------
        dump_events: file path to write events
        """
        super().__init__()
        self._total_duration = None

    async def setup(self, config: PlayerConfig, mpd_provider: MPDProvider, scheduler: Scheduler, player: Player, **kwargs):
        assert config.live_log is not None, "live_logger need the live_log path"
        self.mpd_provider = mpd_provider
        self.recorder = ExpWriterJson(config.live_log)

        scheduler.add_listener(self)
        player.add_listener(self)

    @property
    def total_duration(self):
        assert self.mpd_provider.mpd is not None
        if self._total_duration is None:
            self._total_duration = self.mpd_provider.mpd.max_segment_duration * len(
                self.mpd_provider.mpd.adaptation_sets[0].representations[0].segments
            )
        return self._total_duration

    async def on_buffer_level_change(self, buffer_level):
        self.log.debug(f"Buffer level: {buffer_level:.3f}")

    async def on_position_change(self, position):
        progress = position / self.total_duration
        self.recorder.write_event(ExpEvent_Progress(round(time.time() * 1000), progress))

    async def on_state_change(self, position: float, old_state: State, new_state: State):
        self.log.info("Switch state. pos: %.3f, from %s to %s" % (position, old_state, new_state))
        progress = position / self.total_duration
        self.recorder.write_event(ExpEvent_State(round(time.time() * 1000), progress, str(old_state), str(new_state)))

    async def on_segment_download_start(self, index: int, adap_bw: Dict[int, float], segments: Dict[int, Segment]):
        self.log.info(
            "Download start. Index: %d, Selections: %s" % (index, str({as_id: seg.repr_id for as_id, seg in segments.items()}))
        )

    async def on_segment_download_complete(self, index: int, *args, **kwargs):
        self.log.info("Download complete. Index: %d" % index)
