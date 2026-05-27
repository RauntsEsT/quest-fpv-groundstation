import asyncio
import logging
from vrx_base import VRXBase
from vrx_bands import BANDS_5800, BANDS_1200

log = logging.getLogger("vrx_dummy")


class DummyVRX(VRXBase):
    """No-hardware VRX for testing without physical device."""

    def __init__(self):
        super().__init__()
        self.status.driver = "dummy"
        self.status.connected = True

    def set_channel(self, band: str, channel: int):
        all_bands = {**BANDS_5800, **BANDS_1200}
        band = band.upper()
        self.status.band = band
        self.status.channel = channel
        self.status.frequency_mhz = all_bands.get(band, {i: 0 for i in range(9)}).get(channel - 1, 0) if band in all_bands else 0
        log.info(f"Dummy VRX: {band}{channel} = {self.status.frequency_mhz} MHz")

    async def start(self):
        log.info("Dummy VRX started (no hardware)")
        import random
        while True:
            self.status.rssi_a = random.randint(40, 90)
            self.status.rssi_b = random.randint(35, 85)
            await asyncio.sleep(1)

    async def stop(self):
        pass
