import mmap
import sys
from pprint import pprint


def get_min_ref(file_path):
    found = 0
    with open(file_path, "r+b") as f:
        mm = mmap.mmap(f.fileno(), 0)
        while found >= 0:
            found = mm.find(b'\x00\x00\x00\x01', found+1)
            if found != -1:
                yield found, mm[found+4:found+6]



def main():
    if len(sys.argv) < 2:
        raise Exception("At least one argument needed. First argument should be video file path")
    pprint(list(get_min_ref(sys.argv[1])))


if __name__ == "__main__":
    main()
