import asyncio
import logging
import config_manager
from vrx_base import VRXBase
from vrx_bands import BANDS_5800, BANDS_1200

log = logging.getLogger("vrx_rtc6715")

REG_SYNTH_A = 0x01

PIN_CLK  = 11  # GPIO11 SCLK  -- Foxeer Wildfire Pin 8 (Chan2)
PIN_MOSI = 10  # GPIO10 MOSI  -- Foxeer Wildfire Pin 9 (Chan1)
PIN_CS   = 8   # GPIO8  CE0   -- Foxeer Wildfire Pin 7 (Chan3)

_FREQ_TABLE: dict[int, int] = {}

def _build_freq_table():
    for bands in (BANDS_5800, BANDS_1200):
        for freqs in bands.values():
            for f in freqs:
                _FREQ_TABLE[f] = _freq_to_rtc6715(f)

def _freq_to_rtc6715(freq_mhz: int) -> int:
    # Betaflight formula: n = (freq_kHz - 479000) * 64 / 16000
    n = (freq_mhz * 1000 - 479000) * 64 // 16000
    a = n // 64   # 9-bit integer part
    b = n % 64    # 6-bit fractional part
    return (a & 0x1FF) | ((b & 0x3F) << 9)


class RTC6715VRX(VRXBase):
    def __init__(self):
        super().__init__()
        self.status.driver = "rtc6715_spi"
        self._h = None
        _build_freq_table()

    def _init_gpio(self):
        try:
            import lgpio
            h = lgpio.gpiochip_open(0)
            lgpio.gpio_claim_output(h, PIN_CLK,  0)
            lgpio.gpio_claim_output(h, PIN_MOSI, 0)
            lgpio.gpio_claim_output(h, PIN_CS,   1)
            self._h = h
            self._lgpio = lgpio
            log.info("RTC6715 SPI GPIO init OK (lgpio)")
        except Exception as e:
            log.warning(f"lgpio GPIO init failed: {e} -- SPI channel control disabled")

    def _spi_write(self, reg: int, data: int):
        if self._h is None:
            return
        lg = self._lgpio
        h  = self._h
        # RTC6715: 25-bit word sent LSB first
        # bits[3:0]=reg addr, bit[4]=1(write), bits[24:5]=20-bit data
        word = (reg & 0x0F) | (1 << 4) | ((data & 0xFFFFF) << 5)
        lg.gpio_write(h, PIN_CS, 0)
        for _ in range(25):
            lg.gpio_write(h, PIN_MOSI, word & 1)
            lg.gpio_write(h, PIN_CLK, 1)
            lg.gpio_write(h, PIN_CLK, 0)
            word >>= 1
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
        reg_val = _FREQ_TABLE.get(freq, _freq_to_rtc6715(freq))
        self._spi_write(REG_SYNTH_A, reg_val)
        log.info(f"RTC6715: {band}{channel} = {freq} MHz")
        # Persist selected channel so it survives restart
        cfg = config_manager.load()
        cfg["vrx"]["band"] = band
        cfg["vrx"]["channel"] = channel
        config_manager.save(cfg)

    async def _read_rssi(self):
        try:
            import smbus2
            bus = smbus2.SMBus(1)
            ADS1115_ADDR = 0x48
            bus.write_word_data(ADS1115_ADDR, 0x01, 0xC1E3)
            await asyncio.sleep(0.01)
            raw_a = bus.read_word_data(ADS1115_ADDR, 0x00)
            bus.write_word_data(ADS1115_ADDR, 0x01, 0xD1E3)
            await asyncio.sleep(0.01)
            raw_b = bus.read_word_data(ADS1115_ADDR, 0x00)
            self.status.rssi_a = min(100, max(0, (raw_a >> 8) & 0xFF))
            self.status.rssi_b = min(100, max(0, (raw_b >> 8) & 0xFF))
        except Exception as e:
            log.debug(f"RSSI read failed: {e}")

    async def start(self):
        self._init_gpio()
        self.status.connected = True
        log.info(f"RTC6715 VRX ready -- {self.status.frequency_mhz} MHz")
        while True:
            await self._read_rssi()
            await asyncio.sleep(0.5)

    async def stop(self):
        if self._h is not None:
            self._lgpio.gpiochip_close(self._h)
