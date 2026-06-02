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
        import os
        cmd = [
            "ffmpeg", "-y",
            "-fflags", "nobuffer",
            "-flags", "low_delay",
            "-probesize", "32",
            "-analyzeduration", "0",
            "-f", "v4l2",
            "-input_format", "yuyv422",
            "-standard", "PAL",
            "-framerate", str(self.fps),
            "-thread_queue_size", "2",
            "-i", self.device,
            "-vf", "scale=640:-2,format=yuvj420p",
            "-f", "mjpeg", "-q:v", "7",
            "-flush_packets", "1",
            "pipe:1",
        ]
        log.info(f"Video: {self.device} → MJPEG HTTP /video ({self.fps}fps)")
        retry = 0
        while True:
            if not os.path.exists(self.device):
                log.warning(f"{self.device} pole saadaval, ootan 3s...")
                await asyncio.sleep(3)
                continue
            try:
                self._proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.DEVNULL,
                )
                retry = 0
                await self._read_frames()
                log.warning("ffmpeg lõpetas — taaskäivitan...")
            except Exception as e:
                log.error(f"Video viga: {e}")
            finally:
                if self._proc:
                    try:
                        self._proc.terminate()
                    except Exception:
                        pass
                    self._proc = None
            retry += 1
            wait = min(2 * retry, 10)
            log.info(f"Video restart #{retry}, ootan {wait}s...")
            await asyncio.sleep(wait)

    async def stop(self):
        if self._proc:
            self._proc.terminate()
            await self._proc.wait()
