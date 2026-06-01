import asyncio
import logging
import time
import config_manager
from vrx_base import VRXBase
from vrx_bands import BANDS_5800, BANDS_1200

log = logging.getLogger("vrx_akk331")

REG_SYNTH_A = 0x01

# AKK 331 9-pin connector:
#   Pin 1 (CH1) = CS/NSS  → GPIO27
#   Pin 2 (CH2) = CLK     → GPIO22
#   Pin 3 (CH3) = DATA    → GPIO17
PIN_CS   = 27  # GPIO27 → AKK pin 1 (CS/NSS)
PIN_CLK  = 22  # GPIO22 → AKK pin 2 (CLK)
PIN_MOSI = 17  # GPIO17 → AKK pin 3 (DATA/MOSI)


def _freq_to_rtc6715(freq_mhz: int) -> int:
    n = (freq_mhz * 1000 - 479000) * 64 // 16000
    a = n // 64
    b = n % 64
    return (a & 0x1FF) | ((b & 0x3F) << 9)


class AKK331VRX(VRXBase):
    def __init__(self):
        super().__init__()
        self.status.driver = "akk331"
        self._h = None
        self._lgpio = None

    def _init_gpio(self):
        try:
            import lgpio
            h = lgpio.gpiochip_open(0)
            lgpio.gpio_claim_output(h, PIN_CLK,  0)
            lgpio.gpio_claim_output(h, PIN_MOSI, 0)
            lgpio.gpio_claim_output(h, PIN_CS,   1)
            self._h = h
            self._lgpio = lgpio
            log.info("AKK331 GPIO init OK (lgpio)")
        except Exception as e:
            log.warning(f"lgpio init failed: {e} — channel control disabled")

    def _spi_write(self, reg: int, data: int):
        if self._h is None:
            return
        lg = self._lgpio
        h  = self._h
        # RTC6715: 25-bit word, LSB first
        # bits[3:0]=reg addr, bit[4]=1(write), bits[24:5]=20-bit data
        word = (reg & 0x0F) | (1 << 4) | ((data & 0xFFFFF) << 5)
        lg.gpio_write(h, PIN_CS, 0)
        time.sleep(0.00002)
        for _ in range(25):
            lg.gpio_write(h, PIN_MOSI, word & 1)
            time.sleep(0.000005)
            lg.gpio_write(h, PIN_CLK, 1)
            time.sleep(0.000005)
            lg.gpio_write(h, PIN_CLK, 0)
            time.sleep(0.000005)
            word >>= 1
        time.sleep(0.00002)
        lg.gpio_write(h, PIN_CS, 1)

    def set_channel(self, band: str, channel: int):
        band = band.upper()
        all_bands = {**BANDS_5800, **BANDS_1200}
        if band not in all_bands or not 1 <= channel <= 8:
            raise ValueError(f"Invalid band/channel: {band}{channel}")
        freq = all_bands[band][channel - 1]
        self.status.band = band
        self.status.channel = channel
        self.status.frequency_mhz = freq
        reg_val = _freq_to_rtc6715(freq)
        self._spi_write(REG_SYNTH_A, reg_val)
        log.info(f"AKK331: {band}{channel} = {freq} MHz")
        cfg = config_manager.load()
        cfg["vrx"]["band"] = band
        cfg["vrx"]["channel"] = channel
        config_manager.save(cfg)

    async def start(self):
        self._init_gpio()
        self.status.connected = True
        log.info(f"AKK331 VRX ready — {self.status.frequency_mhz} MHz")
        while True:
            await asyncio.sleep(1)

    async def stop(self):
        if self._h is not None:
            self._lgpio.gpiochip_close(self._h)
