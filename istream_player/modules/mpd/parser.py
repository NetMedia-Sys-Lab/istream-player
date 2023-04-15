import logging
import os
import re
from abc import ABC, abstractmethod
from math import ceil
from typing import Dict, Optional
from xml.etree import ElementTree
from xml.etree.ElementTree import Element

from istream_player.models.mpd_objects import MPD, AdaptationSet, Representation, Segment


class MPDParsingException(BaseException):
    pass


class MPDParser(ABC):
    @abstractmethod
    def parse(self, content: str, url: str) -> MPD:
        pass


class DefaultMPDParser(MPDParser):
    log = logging.getLogger("DefaultMPDParser")

    @staticmethod
    def parse_iso8601_time(duration: Optional[str]) -> float:
        """
        Parse the ISO8601 time string to the number of seconds
        """
        if duration is None or duration == "":
            return 0
        pattern = r"^PT(?:(\d+(?:.\d+)?)H)?(?:(\d+(?:.\d+)?)M)?(?:(\d+(?:.\d+)?)S)?$"
        results = re.match(pattern, duration)
        if results is not None:
            dur = [float(i) if i is not None else 0 for i in results.group(1, 2, 3)]
            dur = 3600 * dur[0] + 60 * dur[1] + dur[2]
            return dur
        else:
            return 0

    @staticmethod
    def remove_namespace_from_content(content):
        """
        Remove the namespace string from XML string
        """
        content = re.sub('xmlns="[^"]+"', "", content, count=1)
        return content

    def parse(self, content: str, url: str) -> MPD:
        content = self.remove_namespace_from_content(content)
        root = ElementTree.fromstring(content)

        type_ = root.attrib["type"]
        assert type_ == "static" or type_ == "dynamic"

        # media presentation duration
        media_presentation_duration = self.parse_iso8601_time(root.attrib.get("mediaPresentationDuration", ""))
        self.log.info(f"{media_presentation_duration=}")

        # min buffer duration
        min_buffer_time = self.parse_iso8601_time(root.attrib.get("minBufferTime", ""))
        self.log.info(f"{min_buffer_time=}")

        # max segment duration
        max_segment_duration = self.parse_iso8601_time(root.attrib.get("maxSegmentDuration", ""))
        self.log.info(f"{max_segment_duration=}")

        period = root.find("Period")

        if period is None:
            raise MPDParsingException('Cannot find "Period" tag')

        adaptation_sets: Dict[int, AdaptationSet] = {}

        base_url = os.path.dirname(url) + "/"

        for index, adaptation_set_xml in enumerate(period):
            if adaptation_set_xml.attrib.get("contentType", "video").lower() == "video":
                adaptation_set: AdaptationSet = self.parse_adaptation_set(
                    adaptation_set_xml, base_url, index, media_presentation_duration
                )
                adaptation_sets[adaptation_set.id] = adaptation_set

        return MPD(content, url, type_, media_presentation_duration, max_segment_duration, min_buffer_time, adaptation_sets, root.attrib)

    def parse_adaptation_set(
        self, tree: Element, base_url, index: Optional[int], media_presentation_duration: float
    ) -> AdaptationSet:
        id_ = int(tree.attrib.get("id", str(index)))
        content_type = tree.attrib.get("contentType", "video")
        assert (
            content_type == "video" or content_type == "audio"
        ), f"Only 'video' or 'audio' content_type is supported, Got {content_type}"

        frame_rate = tree.attrib.get("frameRate")
        max_width = int(tree.attrib.get("maxWidth", 0))
        max_height = int(tree.attrib.get("maxHeight", 0))
        par = tree.attrib.get("par")
        self.log.debug(f"{frame_rate=}, {max_width=}, {max_height=}, {par=}")

        representations = {}
        # GPAC MPD has segment template inside adaptation set
        segment_template: Optional[Element] = tree.find("SegmentTemplate")

        for representation_tree in tree.findall("Representation"):
            representation = self.parse_representation(
                representation_tree, id_, base_url, segment_template, media_presentation_duration
            )
            representations[representation.id] = representation
        return AdaptationSet(int(id_), content_type, frame_rate, max_width, max_height, par, representations, tree.attrib)

    def parse_representation(
        self, tree: Element, as_id: int, base_url, segment_template: Optional[Element], media_presentation_duration: float
    ) -> Representation:
        segment_template = tree.find("SegmentTemplate") or segment_template
        if segment_template is not None:
            return self.parse_representation_with_segment_template(
                tree, as_id, base_url, segment_template, media_presentation_duration
            )
        else:
            raise MPDParsingException("The MPD support is not complete yet")

    def parse_representation_with_segment_template(
        self, tree: Element, as_id: int, base_url, segment_template: Element, media_presentation_duration: float
    ) -> Representation:
        id_ = tree.attrib["id"]
        mime = tree.attrib["mimeType"]
        codec = tree.attrib["codecs"]
        bandwidth = int(tree.attrib["bandwidth"])
        width = int(tree.attrib["width"])
        height = int(tree.attrib["height"])

        assert segment_template is not None, "Segment Template not found in representation"

        initialization = segment_template.attrib["initialization"]
        initialization = initialization.replace("$RepresentationID$", id_)
        initialization = base_url + initialization
        segments: Dict[int, Segment] = {}

        timescale = int(segment_template.attrib["timescale"])
        media = segment_template.attrib["media"].replace("$RepresentationID$", id_)
        start_number = int(segment_template.attrib["startNumber"])

        segment_timeline = segment_template.find("SegmentTimeline")
        if segment_timeline is not None:
            num = start_number
            start_time = 0
            for segment in segment_timeline:
                duration = float(segment.attrib["d"]) / timescale
                url = base_url + re.sub(r"\$Number(%\d+d)\$", r"\1", media) % num
                if "t" in segment.attrib:
                    start_time = float(segment.attrib["t"]) / timescale
                segments[num] = Segment(url, initialization, duration, start_time, as_id, int(id_))
                num += 1
                start_time += duration

                if "r" in segment.attrib:  # repeat
                    for _ in range(int(segment.attrib["r"])):
                        url = base_url + self.var_repl(media, {"Number": num})
                        segments[num] = Segment(url, initialization, duration, start_time, as_id, int(id_))
                        num += 1
                        start_time += duration
        else:
            # GPAC DASH format
            num = start_number
            start_time = 0
            num_segments = ceil((media_presentation_duration * timescale) / int(segment_template.attrib["duration"]))
            duration = float(segment_template.attrib["duration"]) / timescale
            self.log.debug(f"{num_segments=}, {duration=}")
            for _ in range(num_segments):
                url = base_url + self.var_repl(media, {"Number": num})
                segments[num] = Segment(url, initialization, duration, start_time, as_id, int(id_))
                num += 1
                start_time += duration
            # self.log.debug(segments)

        return Representation(int(id_), mime, codec, bandwidth, width, height, initialization, segments, tree.attrib)

    @staticmethod
    def var_repl(s: str, vars: Dict[str, int | str]):
        def _repl(m) -> str:
            m = m.group()[1:-1]
            if m in vars:
                return str(vars[m])
            elif "%" in m:
                v, p = m.split("%", 1)
                return f"%{p}" % vars[v]
            else:
                raise Exception(f"Cannot replace {m} in {s}")

        return re.sub(r"\$.*\$", _repl, s)
