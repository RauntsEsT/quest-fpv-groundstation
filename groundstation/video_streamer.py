import asyncio
import logging

log = logging.getLogger("video_streamer")


class VideoStreamer:
    """
    Captures analog FPV video from Foxeer Wildfire via CVBS USB converter,
    encodes with ffmpeg, and streams via UDP to Meta Quest 3.
    Quest connects to: udp://<groundstation-ip>:5006
    """

    def __init__(self, device: str = "/dev/video0", port: int = 5006,
                 width: int = 720, height: int = 576, fps: int = 30):
        self.device = device
        self.port = port
        self.width = width
        self.height = height
        self.fps = fps
        self._proc: asyncio.subprocess.Process | None = None

    async def start(self):
        cmd = [
            "ffmpeg", "-y",
            "-f", "v4l2",
            "-input_format", "mjpeg",
            "-video_size", f"{self.width}x{self.height}",
            "-framerate", str(self.fps),
            "-i", self.device,
            "-vf", "format=yuv420p",
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-tune", "zerolatency",
            "-b:v", "2M",
            "-f", "mpegts",
            f"udp://0.0.0.0:{self.port}?pkt_size=1316",
        ]
        log.info(f"Video stream: {self.device} → UDP:{self.port}")
        self._proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await self._proc.communicate()
        if self._proc.returncode != 0:
            log.error(f"ffmpeg error: {stderr.decode()[-500:]}")

    async def stop(self):
        if self._proc:
            self._proc.terminate()
            await self._proc.wait()
