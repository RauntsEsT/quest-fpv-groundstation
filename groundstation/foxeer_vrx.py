import asyncio
import logging
import subprocess
from dataclasses import dataclass, field

log = logging.getLogger("foxeer_vrx")

# 5.8GHz FPV band/channel frequency table
BANDS = {
    "A": [5865, 5845, 5825, 5805, 5785, 5765, 5745, 5725],
    "B": [5733, 5752, 5771, 5790, 5809, 5828, 5847, 5866],
    "E": [5705, 5685, 5665, 5645, 5885, 5905, 5925, 5945],
    "F": [5740, 5760, 5780, 5800, 5820, 5840, 5860, 5880],
    "R": [5658, 5695, 5732, 5769, 5806, 5843, 5880, 5917],
}


@dataclass
class VRXStatus:
    band: str = "F"
    channel: int = 2
    frequency_mhz: int = 5760
    rssi_a: int = 0
    rssi_b: int = 0
    active_antenna: str = "A"
    recording: bool = False


class FoxeerVRX:
    """
    Foxeer Wildfire 5.8GHz diversity receiver.
    Video is captured via CVBS USB converter (/dev/video0).
    The Foxeer itself is controlled via its physical buttons;
    this class manages video capture state and virtual channel tracking.
    """

    def __init__(self, video_device: str = "/dev/video0"):
        self.device = video_device
        self.status = VRXStatus()
        self._capture_proc: subprocess.Popen | None = None
        self._rssi_callbacks: list = []

    def set_channel(self, band: str, channel: int):
        band = band.upper()
        if band not in BANDS or not 1 <= channel <= 8:
            raise ValueError(f"Invalid band/channel: {band}{channel}")
        self.status.band = band
        self.status.channel = channel
        self.status.frequency_mhz = BANDS[band][channel - 1]
        log.info(f"VRX channel set to {band}{channel} ({self.status.frequency_mhz} MHz)")

    def set_frequency(self, freq_mhz: int):
        for band, freqs in BANDS.items():
            if freq_mhz in freqs:
                self.status.band = band
                self.status.channel = freqs.index(freq_mhz) + 1
                self.status.frequency_mhz = freq_mhz
                log.info(f"VRX frequency set to {freq_mhz} MHz ({band}{self.status.channel})")
                return
        raise ValueError(f"Frequency {freq_mhz} MHz not in any known band")

    def get_all_channels(self) -> list[dict]:
        channels = []
        for band, freqs in BANDS.items():
            for i, freq in enumerate(freqs):
                channels.append({"band": band, "channel": i + 1, "freq": freq})
        return channels

    async def start(self):
        log.info(f"Foxeer VRX ready on {self.device}")
        # Continuously check device availability
        while True:
            await asyncio.sleep(5)
