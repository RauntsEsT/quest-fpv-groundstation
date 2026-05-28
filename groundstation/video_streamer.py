import asyncio
import logging

log = logging.getLogger("video_streamer")

SOI = bytes([0xFF, 0xD8])
EOI = bytes([0xFF, 0xD9])


class VideoStreamer:
    """
    Captures analog FPV video via CVBS USB capture card.
    Runs one ffmpeg MJPEG process and distributes frames to all HTTP /video clients.
    """

    def __init__(self, device: str = "/dev/video0", port: int = 5006, fps: int = 25):
        self.device = device
        self.port = port  # kept for API compat
        self.fps = fps
        self._proc: asyncio.subprocess.Process | None = None
        self._latest_frame: bytes = b""
        self._subs: list[asyncio.Queue] = []

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=3)
        self._subs.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue):
        try:
            self._subs.remove(q)
        except ValueError:
            pass

    async def _read_frames(self):
        buf = b""
        while True:
            chunk = await self._proc.stdout.read(32768)
            if not chunk:
                log.warning("ffmpeg stdout closed")
                break
            buf += chunk
            while True:
                s = buf.find(SOI)
                if s == -1:
                    buf = b""
                    break
                e = buf.find(EOI, s + 2)
                if e == -1:
                    buf = buf[s:]
                    break
                frame = buf[s:e + 2]
                buf = buf[e + 2:]
                self._latest_frame = frame
                for q in self._subs[:]:
                    try:
                        q.put_nowait(frame)
                    except asyncio.QueueFull:
                        pass

    async def start(self):
        cmd = [
            "ffmpeg", "-y",
            "-f", "v4l2",
            "-input_format", "yuyv422",
            "-standard", "PAL",
            "-framerate", str(self.fps),
            "-i", self.device,
            "-vf", "scale=640:-2,format=yuvj420p",
            "-f", "mjpeg", "-q:v", "5",
            "pipe:1",
        ]
        log.info(f"Video: {self.device} → MJPEG HTTP /video ({self.fps}fps)")
        self._proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await self._read_frames()

    async def stop(self):
        if self._proc:
            self._proc.terminate()
            await self._proc.wait()
