from abc import ABC, abstractmethod
from typing import Dict

from istream_player.core.module import ModuleInterface
from istream_player.models import AdaptationSet


class ABRController(ModuleInterface, ABC):
    @abstractmethod
    def update_selection(self, adaptation_sets: Dict[int, AdaptationSet], index: int) -> Dict[int, int]:
        """
        Update the representation selections

        The main difference between this method and ABRController::update_selection is this method accepts an extra
        Parameter `choose_lowest`. When `choose_lowest` is True, return the lowest quality directly.

        Parameters
        ----------
        adaptation_sets:
            The adaptation sets information

        Returns
        -------
        selection:
            A dictionary where the key is the index of an adaptation set, and the
            value is the chosen representation id for that adaptation set.
        """

        self._min_bitrate_representations: Dict[int, int] = {}
        pass

    def update_selection_lowest(self, adaptation_sets: Dict[int, AdaptationSet]):
        results = {}
        for adaptation_set in adaptation_sets.values():
            results[adaptation_set.id] = self._find_representation_id_of_lowest_bitrate(adaptation_set)
        return results

    def _find_representation_id_of_lowest_bitrate(self, adaptation_set: AdaptationSet) -> int:
        """
        Find the representation ID with the lowest bitrate in a given adaptation set
        Parameters
        ----------
        adaptation_set:
            The adaptation set to process

        Returns
        -------
            The representation ID with the lowest bitrate
        """
        if adaptation_set.id in self._min_bitrate_representations:
            return self._min_bitrate_representations[adaptation_set.id]

        representations = list(adaptation_set.representations.values())
        min_id = representations[0].id
        min_bandwidth = representations[0].bandwidth

        for representation in representations:
            if min_bandwidth is None:
                min_bandwidth = representation.bandwidth
                min_id = representation.id
            elif representation.bandwidth < min_bandwidth:
                min_bandwidth = representation.bandwidth
                min_id = representation.id
        self._min_bitrate_representations[adaptation_set.id] = min_id

        return min_id
