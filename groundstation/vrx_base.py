from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class VRXStatus:
    band: str = "F"
    channel: int = 2
    frequency_mhz: int = 5760
    rssi_a: int = 0
    rssi_b: int = 0
    active_antenna: str = "A"
    connected: bool = False
    driver: str = "none"


class VRXBase(ABC):
    """Abstract base class for all VRX drivers."""

    def __init__(self):
        self.status = VRXStatus()

    @abstractmethod
    async def start(self): ...

    @abstractmethod
    async def stop(self): ...

    @abstractmethod
    def set_channel(self, band: str, channel: int): ...

    def set_frequency(self, freq_mhz: int):
        from vrx_bands import BANDS_5800, BANDS_1200
        for bands in (BANDS_5800, BANDS_1200):
            for band, freqs in bands.items():
                if freq_mhz in freqs:
                    self.status.band = band
                    self.status.channel = freqs.index(freq_mhz) + 1
                    self.status.frequency_mhz = freq_mhz
                    return
        raise ValueError(f"Frequency {freq_mhz} MHz not in any known band")

    def get_all_channels(self) -> list[dict]:
        from vrx_bands import BANDS_5800, BANDS_1200
        result = []
        for bands, ghz in ((BANDS_5800, 5.8), (BANDS_1200, 1.2)):
            for band, freqs in bands.items():
                for i, freq in enumerate(freqs):
                    result.append({"band": band, "channel": i + 1,
                                   "freq": freq, "ghz": ghz})
        return result
