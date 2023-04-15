from typing import Dict

from istream_player.config.config import PlayerConfig
from istream_player.core.abr import ABRController
from istream_player.core.module import Module, ModuleOption
from istream_player.models import AdaptationSet
from istream_player.models.mpd_objects import Representation


@ModuleOption("fixed")
class FixedABRController(Module, ABRController):
    def __init__(self, *, quality: str):
        super().__init__()
        self.quality: int = int(quality)

    async def setup(self, config: PlayerConfig, **kwargs):
        pass

    def update_selection(self, adaptation_sets: Dict[int, AdaptationSet], index: int) -> Dict[int, int]:
        final_selections = dict()

        def has_seg_id(rep: Representation):
            for seg_id, _ in rep.segments.items():
                if seg_id == index:
                    return True
            return False

        for adaptation_set in adaptation_sets.values():
            repr = [rep for rep_id, rep in adaptation_set.representations.items() if has_seg_id(rep)]
            if len(repr) == 0:
                final_selections[adaptation_set.id] = None
            else:
                first_repr_id = min(map(lambda r: r.id, repr))
                num_repr = len(repr)
                final_selections[adaptation_set.id] = first_repr_id + (self.quality % num_repr)

        return final_selections
