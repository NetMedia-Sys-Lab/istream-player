import json
import os
from typing import Iterator

from .exp_events import TYPE_MAPPING_CLASS, TYPE_MAPPING_KEYS, ExpEvent


class ExpWriter:
    def __init__(self, file_path: str, log_type: str):
        self.file_path = file_path
        if os.path.exists(file_path):
            pass
        else:
            with open(file_path, "w") as f:
                f.write(f"#TYPE {log_type}\n")

    def write_event(self, event: ExpEvent):
        raise NotImplementedError()


class ExpReader:
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.parser = self.parse_raw
        self.offset = 0

    def parse_raw(self, line: str):
        event_type, time, args = line.split(" ", 2)
        obj = TYPE_MAPPING_CLASS[event_type]()
        obj.time = time
        obj.line = args
        return obj

    def parse_text(self, line: str):
        args = line.split()
        event_type = args[0]
        event_time = args[1]
        obj = TYPE_MAPPING_CLASS[event_type]()
        obj.time = int(event_time)
        for key, value in zip(TYPE_MAPPING_KEYS[event_type], args[2:]):
            attr_type = type(getattr(obj, key))
            setattr(obj, key, attr_type(value))
        return obj

    def parse_json(self, line):
        event_type, args = line.split(" ", 1)
        d = json.loads(args)
        obj = TYPE_MAPPING_CLASS[event_type]()
        for key, value in d.items():
            setattr(obj, key, value)
        return obj

    def read_lines(self):
        with open(self.file_path) as f:
            f.seek(self.offset)
            for line in f:
                yield line
            self.offset = f.tell()

    def read_events(self) -> Iterator[ExpEvent]:
        for line in self.read_lines():
            try:
                if not line:
                    continue
                spi = line.index(" ")
                if spi == -1:
                    continue
                line_type, content = line[:spi], line[spi + 1:]
                if line_type == "#EVENT":
                    yield self.parser(content)
                elif line_type == "#TYPE":
                    self.parser = getattr(self, f"parse_{content.strip()}")
            except ValueError:
                pass


class ExpWriterText(ExpWriter):
    def __init__(self, file_path: str):
        super().__init__(file_path, "text")

    def write_event(self, event: ExpEvent):
        with open(self.file_path, "a") as f:
            f.write(f"#EVENT {event.type} {event.time} ")
            d = vars(event)
            for key in TYPE_MAPPING_KEYS[event.type]:
                f.write(" ")
                f.write(str(d[key]))
            f.write("\n")


class ExpWriterJson(ExpWriter):
    def __init__(self, file_path: str):
        super().__init__(file_path, "json")

    def write_event(self, event: ExpEvent):
        with open(self.file_path, "a") as f:
            f.write(f"#EVENT {event.type} ")
            f.write(json.dumps(vars(event)))
            f.write("\n")
