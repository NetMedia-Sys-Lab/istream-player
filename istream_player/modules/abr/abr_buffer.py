from collections import OrderedDict
from typing import Dict, Optional

from istream_player.config.config import PlayerConfig
from istream_player.core.abr import ABRController
from istream_player.core.buffer import BufferManager
from istream_player.core.module import Module, ModuleOption
from istream_player.models import AdaptationSet


@ModuleOption("buffer", requires=[BufferManager])
class BufferABRController(Module, ABRController):
    def __init__(self):
        self.rate_map = None

        self.RESERVOIR = 0.1
        self.UPPER_RESERVOIR = 0.9

    async def setup(self, config: PlayerConfig, buffer_manager: BufferManager, **kwargs):
        self.buffer_size = config.buffer_duration
        self.buffer_manager = buffer_manager

    def update_selection(self, adaptation_sets: Dict[int, AdaptationSet], index: int) -> Dict[int, int]:
        final_selections = dict()

        for adaptation_set in adaptation_sets.values():
            final_selections[adaptation_set.id] = self.choose_ideal_selection_buffer_based(adaptation_set)

        return final_selections

    def choose_ideal_selection_buffer_based(self, adaptation_set) -> Optional[int]:
        """
        Module that estimates the next bitrate based on the rate map.
        Rate Map: Buffer Occupancy vs. Bitrates:
            If Buffer Occupancy < RESERVOIR (10%) :
                select the minimum bitrate
            if RESERVOIR < Buffer Occupancy < Cushion(90%) :
                Linear function based on the rate map
            if Buffer Occupancy > Cushion :
                Maximum Bitrate
        Ref. Fig. 6 from [1]
        :param current_buffer_occupancy: Current buffer occupancy in number of segments
        :param bitrates: List of available bitrates [r_min, .... r_max]
        :return:the bitrate for the next segment
        """
        next_bitrate = None

        bitrates = [representation.bandwidth for representation in adaptation_set.representations.values()]
        bitrates.sort()

        # Calculate the current buffer occupancy percentage
        current_buffer_occupancy = self.buffer_manager.buffer_level
        buffer_percentage = current_buffer_occupancy / self.buffer_size

        # Selecting the next bitrate based on the rate map
        if self.rate_map is None:
            self.rate_map = self.get_rate_map(bitrates)

        if buffer_percentage <= self.RESERVOIR:
            next_bitrate = bitrates[0]
        elif buffer_percentage >= self.UPPER_RESERVOIR:
            next_bitrate = bitrates[-1]
        else:
            for marker in reversed(self.rate_map.keys()):
                if marker < buffer_percentage:
                    break
                next_bitrate = self.rate_map[marker]

        representation_id = None
        for representation in adaptation_set.representations.values():
            if representation.bandwidth == next_bitrate:
                representation_id = representation.id

        return representation_id

    def get_rate_map(self, bitrates):
        """
        Module to generate the rate map for the bitrates, reservoir, and cushion
        """
        rate_map = OrderedDict()
        rate_map[self.RESERVOIR] = bitrates[0]
        intermediate_levels = bitrates[1:-1]
        marker_length = (self.UPPER_RESERVOIR - self.RESERVOIR) / (len(intermediate_levels) + 1)
        current_marker = self.RESERVOIR + marker_length
        for bitrate in intermediate_levels:
            rate_map[current_marker] = bitrate
            current_marker += marker_length
        rate_map[self.UPPER_RESERVOIR] = bitrates[-1]
        return rate_map
