from enum import Enum
from typing import Optional


class State(Enum):
    IDLE = 0
    BUFFERING = 1
    READY = 2
    END = 3


class SegmentRequest:
    def __init__(self, index: int, url: Optional[str]):
        self.index = index
        self.url = url
        self.first_bytes_received = False
