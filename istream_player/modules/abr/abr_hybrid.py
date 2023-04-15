from typing import Dict, Optional

from istream_player.config.config import PlayerConfig
from istream_player.core.abr import ABRController
from istream_player.core.buffer import BufferManager
from istream_player.core.module import Module, ModuleOption
from istream_player.models import AdaptationSet
from istream_player.modules.bw_meter.bandwidth import BandwidthMeter


@ModuleOption("hybrid", requires=[BandwidthMeter, BufferManager])
class HybridABRController(Module, ABRController):
    def __init__(self):
        self._last_selections: Optional[Dict[int, int]] = None

    async def setup(
        self,
        config: PlayerConfig,
        bandwidth_meter: BandwidthMeter,
        buffer_manager: BufferManager,
        **kwargs,
    ):
        self.buffer_manager = buffer_manager
        self.panic_buffer = config.panic_buffer_level
        self.safe_buffer = config.safe_buffer_level
        self.bandwidth_meter = bandwidth_meter

    def update_selection(self, adaptation_sets: Dict[int, AdaptationSet], index: int) -> Dict[int, int]:
        # Only use 70% of measured bandwidth
        available_bandwidth = int(self.bandwidth_meter.bandwidth * 0.7)

        # Count the number of video adaptation sets and audio adaptation sets
        num_videos = 0
        num_audios = 0
        for adaptation_set in adaptation_sets.values():
            if adaptation_set.content_type == "video":
                num_videos += 1
            else:
                num_audios += 1

        # Calculate ideal selections
        if num_videos == 0 or num_audios == 0:
            bw_per_adaptation_set = available_bandwidth / (num_videos + num_audios)
            ideal_selection: Dict[int, int] = dict()

            for adaptation_set in adaptation_sets.values():
                ideal_selection[adaptation_set.id] = self.choose_ideal_selection_bandwidth_based(
                    adaptation_set, bw_per_adaptation_set
                )
        else:
            bw_per_video = (available_bandwidth * 0.8) / num_videos
            bw_per_audio = (available_bandwidth * 0.2) / num_audios
            ideal_selection: Dict[int, int] = dict()
            for adaptation_set in adaptation_sets.values():
                if adaptation_set.content_type == "video":
                    ideal_selection[adaptation_set.id] = self.choose_ideal_selection_bandwidth_based(adaptation_set, bw_per_video)
                else:
                    ideal_selection[adaptation_set.id] = self.choose_ideal_selection_bandwidth_based(adaptation_set, bw_per_audio)

        buffer_level = self.buffer_manager.buffer_level
        final_selections = dict()

        # Take the buffer level into considerations

        if self._last_selections is not None:
            for id_, adaptation_set in adaptation_sets.items():
                representations = adaptation_set.representations
                last_repr = representations[self._last_selections.get(id_, 0)]
                ideal_repr = representations[ideal_selection.get(id_, 0)]
                if buffer_level < self.panic_buffer:
                    final_repr_id = last_repr.id if last_repr.bandwidth < ideal_repr.bandwidth else ideal_repr.id
                elif buffer_level > self.safe_buffer:
                    final_repr_id = last_repr.id if last_repr.bandwidth > ideal_repr.bandwidth else ideal_repr.id
                else:
                    final_repr_id = ideal_repr.id
                final_selections[id_] = final_repr_id
        else:
            final_selections = ideal_selection

        self._last_selections = final_selections
        return final_selections

    @staticmethod
    def choose_ideal_selection_bandwidth_based(adaptation_set, bw) -> int:
        """
        Choose the ideal bitrate selection for one adaptation_set without caring about the buffer level or any other things
        Parameters
        ----------
        adaptation_set
            The adaptation_set to choose
        bw
            The bandwidth could be allocated to this adaptation set
        Returns
        -------
        id: int
            The representation id
        """
        representations = sorted(adaptation_set.representations.values(), key=lambda x: x.bandwidth, reverse=True)
        for representation in representations:
            if representation.bandwidth < bw:
                return representation.id
        # If there's no representation whose bitrate is lower than the estimate, return the lowest one
        return representations[-1].id
