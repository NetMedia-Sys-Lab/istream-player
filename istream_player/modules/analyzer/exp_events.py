import sys

TYPE_MAPPING_CLASS = {}
TYPE_MAPPING_KEYS = {}


class ExpEvent:
    type: str
    time: int
    time_rel: int


class ExpEvent_PlaybackStart(ExpEvent):
    type = "PLAYBACK_START"
    time: int
    extra: str

    def __init__(self, time=0):
        self.type = self.type
        self.time = time


class ExpEvent_State(ExpEvent):
    type = "STATE"
    time: int
    progress: float
    old_state: str
    new_state: str

    def __init__(self, time=0, progress=0.0, old_state="", new_state=""):
        self.type = self.type
        self.time = time
        self.progress = progress
        self.old_state = old_state
        self.new_state = new_state


class ExpEvent_Progress(ExpEvent):
    type = "PROGRESS"
    time: int
    progress: float

    def __init__(self, time=0, progress=0.0):
        self.type = self.type
        self.time = time
        self.progress = progress


class ExpEvent_BwSwitch(ExpEvent):
    type = "BW_SWITCH"
    time: int
    bw: float
    latency: float
    drop: float

    def __init__(self, time=0, bw=0.0, latency=0.0, drop=0.0):
        self.type = self.type
        self.time = time
        self.bw = bw
        self.latency = latency
        self.drop = drop


class ExpEvent_TcStat(ExpEvent):
    type = "TC_STAT"
    time: int
    line: str

    def __init__(self, time=0, line=""):
        self.type = self.type
        self.time = time
        self.line = line


def create_type_mapping():
    global TYPE_MAPPING_CLASS, TYPE_MAPPING_KEYS
    TYPE_MAPPING_CLASS = {}
    TYPE_MAPPING_KEYS = {}
    current_module = sys.modules[__name__]
    for attr in dir(current_module):
        if not attr.startswith("ExpEvent_"):
            continue
        cl = getattr(current_module, attr)
        event_type = cl().type
        TYPE_MAPPING_CLASS[event_type] = cl
        TYPE_MAPPING_KEYS[event_type] = [attr for attr in dir(cl()) if
                                         not callable(getattr(cl(), attr)) and not attr.startswith("__")]
        TYPE_MAPPING_KEYS[event_type].remove("type")
        TYPE_MAPPING_KEYS[event_type].remove("time")
        TYPE_MAPPING_KEYS[event_type].sort()


create_type_mapping()
