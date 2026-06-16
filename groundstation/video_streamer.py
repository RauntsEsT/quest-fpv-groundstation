import asyncio
import io
import logging
import os
import glob
import subprocess
import threading
import queue as _queue
import time
from datetime import datetime

log = logging.getLogger("video_streamer")

SOI = bytes([0xFF, 0xD8])
EOI = bytes([0xFF, 0xD9])

RECORDINGS_DIR = '/home/pi/recordings'


def _make_no_signal_jpeg() -> bytes:
    try:
        from PIL import Image, ImageDraw
        img = Image.new("RGB", (640, 480), color=(20, 20, 20))
        draw = ImageDraw.Draw(img)
        text = "NO SIGNAL"
        bbox = draw.textbbox((0, 0), text)
        w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
        draw.text(((640 - w) // 2, (480 - h) // 2), text, fill=(200, 200, 200))
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=70)
        return buf.getvalue()
    except Exception as e:
        log.warning(f"No-signal frame generation failed: {e}")
        return b""


class MJPEGRecorder:
    """Kirjutab MJPEG kaadrid ffmpeg pipe kaudu MP4 faili (eraldi thread)."""

    def __init__(self, filepath: str, fps: int):
        self._q: _queue.Queue = _queue.Queue(maxsize=150)
        self._start_time = time.time()
        self._proc = subprocess.Popen(
            ['ffmpeg', '-y', '-f', 'mjpeg', '-r', str(fps),
             '-i', 'pipe:0', '-c:v', 'libx264', '-preset', 'ultrafast',
             '-crf', '23', '-movflags', '+faststart', filepath],
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        self._thread = threading.Thread(target=self._writer, daemon=True)
        self._thread.start()

    def write(self, frame: bytes):
        try:
            self._q.put_nowait(frame)
        except _queue.Full:
            pass

    def _writer(self):
        while True:
            frame = self._q.get()
            if frame is None:
                break
            try:
                self._proc.stdin.write(frame)
            except Exception:
                break
        try:
            self._proc.stdin.close()
        except Exception:
            pass
        self._proc.wait()

    def stop(self) -> float:
        self._q.put(None)
        self._thread.join(timeout=20)
        return time.time() - self._start_time

    @property
    def duration(self) -> float:
        return time.time() - self._start_time


class VideoStreamer:
    def __init__(self, device: str = "/dev/video0", port: int = 5006, fps: int = 25):
        self.device = device
        self.port = port
        self.fps = fps
        self._proc: asyncio.subprocess.Process | None = None
        self._latest_frame: bytes = b""
        self._last_frame_time: float = 0.0
        self._no_signal_frame: bytes = _make_no_signal_jpeg()
        self._subs: list[asyncio.Queue] = []
        self._recorder: MJPEGRecorder | None = None
        self._rec_filename: str = ''
        self._frameless_restarts: int = 0

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=3)
        self._subs.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue):
        try:
            self._subs.remove(q)
        except ValueError:
            pass

    def _push_frame(self, frame: bytes):
        for q in self._subs[:]:
            try:
                q.put_nowait(frame)
            except asyncio.QueueFull:
                pass
        if self._recorder:
            self._recorder.write(frame)

    async def _keepalive(self):
        """Send no-signal placeholder at ~2 fps when no real frames arrive."""
        while True:
            await asyncio.sleep(0.5)
            if self._subs and self._no_signal_frame:
                if time.monotonic() - self._last_frame_time > 1.0:
                    self._push_frame(self._no_signal_frame)

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
                self._last_frame_time = time.monotonic()
                self._frameless_restarts = 0
                self._push_frame(frame)

    async def start(self):
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
            "-vf", "yadif=0:-1:0,hqdn3d=3:3:0:0,scale=640:-2,format=yuvj420p",
            "-f", "mjpeg", "-q:v", "3",
            "-flush_packets", "1",
            "pipe:1",
        ]
        log.info(f"Video: {self.device} → MJPEG HTTP /video ({self.fps}fps, yadif)")
        asyncio.ensure_future(self._keepalive())
        asyncio.ensure_future(self._watchdog())
        retry = 0
        while True:
            if not os.path.exists(self.device):
                log.warning(f"{self.device} pole saadaval, ootan 3s...")
                await asyncio.sleep(3)
                continue
            try:
                start_t = asyncio.get_event_loop().time()
                self._proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.DEVNULL,
                )
                self._last_frame_time = time.monotonic()
                retry = 0
                await self._read_frames()
                log.warning("ffmpeg lõpetas — taaskäivitan...")
                if asyncio.get_event_loop().time() - start_t < 3.0:
                    await self._usb_reset()
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

    async def _watchdog(self):
        """Kui ffmpeg jookseb, aga ei toodaja päris kaadreid (signaal puudub/USB
        kapture kinni), taaskäivita ffmpeg ja lähtesta USB. Kasvav ootetsükkel
        väldib pidevat USB resetti, kui VTX on lihtsalt välja lülitatud."""
        while True:
            await asyncio.sleep(2)
            if self._proc is None or self._proc.returncode is not None:
                continue
            threshold = min(8 + 4 * self._frameless_restarts, 30)
            if time.monotonic() - self._last_frame_time > threshold:
                self._frameless_restarts += 1
                log.warning(
                    f"Video: pole reaalseid kaadreid {threshold}s — "
                    f"taaskäivitan ffmpeg + USB reset (#{self._frameless_restarts})"
                )
                try:
                    self._proc.kill()
                except Exception:
                    pass
                await self._usb_reset()

    async def _usb_reset(self):
        import fcntl
        USBDEVFS_RESET = 21780
        known = {('1b71', '3002'), ('eb1a', '2861'), ('eb1a', '284b'), ('05e1', '0408')}
        try:
            for path in glob.glob('/sys/bus/usb/devices/[0-9]*'):
                try:
                    vid = open(f'{path}/idVendor').read().strip()
                    pid = open(f'{path}/idProduct').read().strip()
                    if (vid, pid) in known:
                        bus = int(open(f'{path}/busnum').read())
                        dev = int(open(f'{path}/devnum').read())
                        dev_path = f'/dev/bus/usb/{bus:03d}/{dev:03d}'
                        with open(dev_path, 'wb') as fd:
                            fcntl.ioctl(fd, USBDEVFS_RESET, 0)
                        log.info(f'USB reset: {dev_path}')
                        await asyncio.sleep(2)
                        return
                except Exception:
                    pass
        except Exception as e:
            log.debug(f'USB reset skip: {e}')
        await asyncio.sleep(2)

    async def stop(self):
        if self._proc:
            self._proc.terminate()
            await self._proc.wait()

    # ── Salvestamine ──────────────────────────────────────────────────────

    def start_recording(self) -> str:
        if self._recorder:
            return self._rec_filename
        os.makedirs(RECORDINGS_DIR, exist_ok=True)
        fname = f'rec_{datetime.now().strftime("%Y%m%d_%H%M%S")}.mp4'
        fpath = os.path.join(RECORDINGS_DIR, fname)
        self._recorder = MJPEGRecorder(fpath, self.fps)
        self._rec_filename = fname
        log.info(f'Salvestamine algas: {fpath}')
        return fname

    def stop_recording(self) -> dict:
        if not self._recorder:
            return {'ok': False, 'error': 'Pole salvestamas'}
        rec = self._recorder
        self._recorder = None
        fname = self._rec_filename
        duration = rec.stop()
        fpath = os.path.join(RECORDINGS_DIR, fname)
        size = os.path.getsize(fpath) if os.path.exists(fpath) else 0
        log.info(f'Salvestamine lopetatud: {fname}, {duration:.1f}s, {size // 1024}KB')
        return {'ok': True, 'filename': fname, 'duration': round(duration, 1), 'size': size}

    @property
    def is_recording(self) -> bool:
        return self._recorder is not None

    @property
    def recording_duration(self) -> float:
        return self._recorder.duration if self._recorder else 0.0

    def list_recordings(self) -> list:
        if not os.path.exists(RECORDINGS_DIR):
            return []
        files = sorted(glob.glob(os.path.join(RECORDINGS_DIR, 'rec_*.mp4')), reverse=True)
        result = []
        for f in files[:50]:
            name = os.path.basename(f)
            size = os.path.getsize(f)
            result.append({'name': name, 'size': size, 'url': f'/recordings/{name}'})
        return result

    def delete_recording(self, filename: str) -> bool:
        safe = os.path.basename(filename)
        if not safe.startswith('rec_') or not safe.endswith('.mp4'):
            return False
        fpath = os.path.join(RECORDINGS_DIR, safe)
        if os.path.exists(fpath):
            os.remove(fpath)
            return True
        return False
