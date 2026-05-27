import asyncio
import logging
import subprocess
from vrx_base import VRXBase, VRXStatus

log = logging.getLogger("vrx_digital")


class DigitalVRXBase(VRXBase):
    """
    Base for digital FPV systems (Walksnail, HDZero, DJI O3).
    Video capture via HDMI capture card → /dev/video0 (or USB direct).
    No frequency/band control — digital link manages this.
    """

    def set_channel(self, band: str, channel: int):
        log.warning("Digital VRX: manual band/channel not applicable")

    def set_frequency(self, freq_mhz: int):
        log.warning("Digital VRX: manual frequency not applicable")

    def get_all_channels(self) -> list[dict]:
        return []


class WalksnailVRX(DigitalVRXBase):
    """
    Walksnail Avatar digital FPV.
    Video: Walksnail goggles HDMI OUT → HDMI capture card → /dev/video0
    """

    def __init__(self, video_device: str = "/dev/video0"):
        super().__init__()
        self.video_device = video_device
        self.status.driver = "walksnail"
        self.status.band = "DIGITAL"
        self.status.frequency_mhz = 0

    async def start(self):
        self.status.connected = True
        log.info(f"Walksnail VRX ready — HDMI capture on {self.video_device}")
        while True:
            await asyncio.sleep(5)

    async def stop(self):
        pass


class HDZeroVRX(DigitalVRXBase):
    """
    HDZero digital FPV.
    Video: HDZero goggles HDMI OUT → HDMI capture card → /dev/video0
    """

    def __init__(self, video_device: str = "/dev/video0"):
        super().__init__()
        self.video_device = video_device
        self.status.driver = "hdzero"
        self.status.band = "DIGITAL"
        self.status.frequency_mhz = 0

    async def start(self):
        self.status.connected = True
        log.info(f"HDZero VRX ready on {self.video_device}")
        while True:
            await asyncio.sleep(5)

    async def stop(self):
        pass


class DJIO3VRX(DigitalVRXBase):
    """
    DJI O3/O3+ digital FPV.
    Video: DJI Goggles 3 USB streaming → /dev/video0
    Or HDMI OUT → HDMI capture card.
    """

    def __init__(self, video_device: str = "/dev/video0"):
        super().__init__()
        self.video_device = video_device
        self.status.driver = "dji_o3"
        self.status.band = "DIGITAL"
        self.status.frequency_mhz = 0

    async def start(self):
        self.status.connected = True
        log.info(f"DJI O3 VRX ready on {self.video_device}")
        while True:
            await asyncio.sleep(5)

    async def stop(self):
        pass
