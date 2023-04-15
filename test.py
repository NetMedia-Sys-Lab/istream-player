import asyncio
import sys
from asyncio.subprocess import PIPE
from queue import Queue
from threading import Thread

import cv2
import numpy as np

width, height = 1024, 576


font = cv2.FONT_HERSHEY_PLAIN
bottomLeftCornerOfText = (10, 500)
fontScale = 1
fontColor = (255, 255, 255)
thickness = 1
lineType = 2


class PlayerGUI(Thread):
    def __init__(self):
        super().__init__(target=self.loop)
        self.buffer: Queue[cv2.Mat] = Queue()
        self.delay = 1 / 30

    def loop(self):
        while True:
            frame = self.buffer.get()
            # yuv = np.frombuffer(buff, dtype=np.uint8).reshape((height * 3 // 2, width))
            # bgr = cv2.cvtColor(yuv, cv2.COLOR_YUV2BGR_I420)
            # print(len(bgr), len(bgr[0]), len(bgr[0][0]))
            cv2.imshow("image", frame)
            cv2.waitKey(int(1000 * self.delay))


async def main():
    proc = await asyncio.create_subprocess_exec(
        # "ffplay", "-", "-loglevel", "quiet", stdin=PIPE
        "ffmpeg",
        "-fflags", "+flush_packets+discardcorrupt",
        "-err_detect", "-ignore_err",
        "-f",
        "mp4",
        "-i",
        "-",
        "-pix_fmt",
        "yuv420p",
        # "-blocksize", "32", "-flush_packets", "1",
        "-f",
        "rawvideo",
        "-loglevel",
        "error",
        # "-max_muxing_queue_size", "1",
        "-",
        # "-y",
        # "/tmp/test.y4m",
        stdin=PIPE,
        stdout=PIPE,
        stderr=sys.stderr,
    )
    gui = PlayerGUI()
    gui.start()

    async def reader():
        print("Reading decoded bytes")
        frame_size = (width * height * 3) // 2
        frame_index = 0
        # buff = self.decoded[url]
        while True:
            count = 0
            buff = bytearray()
            while count < frame_size:
                b = await proc.stdout.read(frame_size - count)  # type: ignore
                if not b:
                    raise Exception("Debugger process stdout closed")
                buff.extend(b)
                count += len(b)
            frame_index += 1
            print(f"***************** Frame decoded: {frame_index} : {len(buff)} bytes")

            yuv = np.frombuffer(buff, dtype=np.uint8).reshape((height * 3 // 2, width))
            bgr = cv2.cvtColor(yuv, cv2.COLOR_YUV2BGR_I420)

            cv2.putText(bgr, f"Frame: {frame_index}", bottomLeftCornerOfText, font, fontScale, fontColor, thickness, lineType)

            gui.buffer.put(bgr)
            # await asyncio.sleep(0.01)

    async def writer():
        assert proc.stdin is not None
        with open("/home/akram/ucalgary/research/istream-player/dataset/videos/av1-1sec/Aspen/init-stream4.m4s", "rb") as f:
            proc.stdin.write(f.read())
        with open(
            "/home/akram/ucalgary/research/istream-player/dataset/videos/av1-1sec/Aspen/chunk-stream4-00003.m4s", "rb"
        ) as f:
            proc.stdin.write(f.read())
        await proc.stdin.drain()
        await asyncio.sleep(4)

        with open(
            "/home/akram/ucalgary/research/istream-player/dataset/videos/av1-1sec/Aspen/chunk-stream4-00005.m4s", "rb"
        ) as f:
            proc.stdin.write(f.read())

    asyncio.create_task(reader())
    asyncio.create_task(writer())

    await asyncio.sleep(10)


if __name__ == "__main__":
    asyncio.run(main())
