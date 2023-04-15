from dataclasses import dataclass
from typing import Dict, Literal, Optional


class MPD(object):
    def __init__(
        self,
        content: str,
        url: str,
        type_: Literal["static", "dynamic"],
        media_presentation_duration: float,
        max_segment_duration: float,
        min_buffer_time: float,
        adaptation_sets: Dict[int, "AdaptationSet"],
        attrib: Dict[str, str]
    ):
        self.content = content
        """
        The raw content of the MPD file
        """

        self.url = url
        """
        The URL of the MPD file
        """

        self.type: Literal["static", "dynamic"] = type_
        """
        If this source is VOD ("static") or Live ("dynamic")
        """

        self.media_presentation_duration = media_presentation_duration
        """
        The media presentation duration in seconds
        """

        self.min_buffer_time = min_buffer_time
        """
        The recommended minimum buffer time in seconds
        """

        self.max_segment_duration = max_segment_duration
        """
        The maximum segment duration in seconds
        """

        self.adaptation_sets: Dict[int, AdaptationSet] = adaptation_sets
        """
        All the adaptation sets
        """

        self.attrib = attrib
        """
        All attributes from XML
        """


class AdaptationSet(object):
    def __init__(
        self,
        adaptation_set_id: int,
        content_type: Literal["video", "audio"],
        frame_rate: Optional[str],
        max_width: int,
        max_height: int,
        par: Optional[str],
        representations: Dict[int, "Representation"],
        attrib: Dict[str, str]
    ):
        self.id = adaptation_set_id
        """
        The adaptation set id
        """

        self.content_type: str = content_type
        """
        The content type of the adaptation set. It could only be "video" or "audio"
        """

        self.frame_rate: Optional[str] = frame_rate
        """
        The frame rate string
        """

        self.max_width: int = max_width
        """
        The maximum width
        """

        self.max_height: int = max_height
        """
        The maximum height
        """

        self.par: Optional[str] = par
        """
        The ratio of width / height
        """

        self.representations: Dict[int, Representation] = representations
        """
        All the representations under the adaptation set
        """

        self.attrib = attrib
        """
        All attributes from XML
        """


class Representation(object):
    def __init__(
        self,
        id_: int,
        mime_type: str,
        codecs: str,
        bandwidth: int,
        width: int,
        height: int,
        initialization: str,
        segments: Dict[int, "Segment"],
        attrib: Dict[str, str]
    ):
        self.id = id_
        """
        The id of the representation
        """

        self.mime_type = mime_type
        """
        The mime type of the representation
        """

        self.codecs: str = codecs
        """
        The codec string of the representation
        """

        self.bandwidth: int = bandwidth
        """
        Average bitrate of this stream in bps
        """

        self.width = width
        """
        Width of picture
        """

        self.height = height
        """
        Height of picture
        """

        self.initialization: str = initialization
        """
        The initialization URL
        """

        self.segments: Dict[int, Segment] = segments
        """
        The video segments
        """

        self.attrib = attrib
        """
        All attributes from XML
        """


@dataclass
class Segment(object):
    # Segment URL
    url: str

    # Stream Initilalization URL
    init_url: str

    # Segment play duration in seconds
    duration: float

    # Segment play start time
    start_time: float

    # Adaptation Set ID
    as_id: int

    # Representation ID
    repr_id: int
