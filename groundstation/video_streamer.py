import asyncio
import logging

log = logging.getLogger("video_streamer")


class VideoStreamer:
    """
    Captures analog FPV video from USB capture card via v4l2,
    encodes with ffmpeg, and streams via UDP to Meta Quest.
    Quest app connects to udp://groundstation-ip:5006
    """

    def __init__(self, device: str, port: int, width: int = 720, height: int = 576, fps: int = 30):
        self.device = device
        self.port = port
        self.width = width
        self.height = height
        self.fps = fps

    async def start(self):
        cmd = [
            "ffmpeg",
            "-f", "v4l2",
            "-input_format", "mjpeg",
            "-video_size", f"{self.width}x{self.height}",
            "-framerate", str(self.fps),
            "-i", self.device,
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-tune", "zerolatency",
            "-b:v", "2M",
            "-f", "mpegts",
            f"udp://0.0.0.0:{self.port}?pkt_size=1316",
        ]
        log.info(f"Starting video stream from {self.device} on UDP port {self.port}")
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()
        if proc.returncode != 0:
            log.error(f"ffmpeg exited: {stderr.decode()[-500:]}")
