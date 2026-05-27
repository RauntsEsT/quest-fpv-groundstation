import asyncio
import logging
from vrx_base import VRXBase
from vrx_bands import BANDS_5800, BANDS_1200

log = logging.getLogger("vrx_rtc6715")

# RTC6715 SPI register addresses
REG_SYNTH_A = 0x01

# RPi5 GPIO pins for SPI (bit-banging, works when hw SPI busy with other device)
PIN_CLK  = 11  # GPIO11 SCLK
PIN_MOSI = 10  # GPIO10 MOSI
PIN_CS   = 8   # GPIO8  CE0

# Frequency lookup for RTC6715 register values
# Formula: F = (A + B*2) * 8MHz, where A = integer, B = fractional
_FREQ_TABLE: dict[int, int] = {}

def _build_freq_table():
    for bands in (BANDS_5800, BANDS_1200):
        for freqs in bands.values():
            for f in freqs:
                # N = (f * 20 + 112) // 64, simplified for RTC6715
                # Using documented lookup approach
                _FREQ_TABLE[f] = _freq_to_rtc6715(f)

def _freq_to_rtc6715(freq_mhz: int) -> int:
    """Convert MHz to RTC6715 A/B register value."""
    # RTC6715: freq = (A + B/64) * 8, A 9-bit, B 6-bit → packed as 25-bit
    f_ref = 8  # MHz
    n = freq_mhz / f_ref
    a = int(n)
    b = round((n - a) * 64)
    return (a & 0x1FF) | ((b & 0x3F) << 9)


class RTC6715VRX(VRXBase):
    """
    Generic analog VRX driver using RTC6715 SPI protocol.
    Supports any VRX with exposed CLK/DATA/CS pads.
    Works for 5.8GHz and 1.2GHz modules using RTC6715/compatible chip.

    Wiring:
        RPi GPIO11 (CLK)  → VRX CLK pad
        RPi GPIO10 (MOSI) → VRX DATA pad
        RPi GPIO8  (CS)   → VRX CS pad
        RPi GPIO2/3 (I2C) → ADS1115 → RSSI_A / RSSI_B
    """

    def __init__(self):
        super().__init__()
        self.status.driver = "rtc6715_spi"
        self._gpio = None
        self._adc = None
        _build_freq_table()

    def _init_gpio(self):
        try:
            import RPi.GPIO as GPIO
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(PIN_CLK,  GPIO.OUT)
            GPIO.setup(PIN_MOSI, GPIO.OUT)
            GPIO.setup(PIN_CS,   GPIO.OUT)
            GPIO.output(PIN_CS, GPIO.HIGH)
            self._gpio = GPIO
            log.info("RTC6715 SPI GPIO init OK")
        except ImportError:
            log.warning("RPi.GPIO not available — SPI channel control disabled")

    def _spi_write(self, reg: int, data: int):
        """Write 25-bit value to RTC6715 register via bit-bang SPI."""
        if not self._gpio:
            return
        GPIO = self._gpio
        word = ((data & 0xFFFFFF) << 1) | (reg & 0x0F)  # 25 bits
        GPIO.output(PIN_CS, GPIO.LOW)
        for i in range(25):
            bit = (word >> (24 - i)) & 1
            GPIO.output(PIN_MOSI, bit)
            GPIO.output(PIN_CLK, GPIO.HIGH)
            GPIO.output(PIN_CLK, GPIO.LOW)
        GPIO.output(PIN_CS, GPIO.HIGH)

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

    async def _read_rssi(self):
        """Read RSSI_A and RSSI_B from ADS1115 via I2C."""
        try:
            import smbus2
            bus = smbus2.SMBus(1)
            ADS1115_ADDR = 0x48
            # Read CH0 (RSSI_A)
            bus.write_word_data(ADS1115_ADDR, 0x01, 0xC1E3)
            await asyncio.sleep(0.01)
            raw_a = bus.read_word_data(ADS1115_ADDR, 0x00)
            # Read CH1 (RSSI_B)
            bus.write_word_data(ADS1115_ADDR, 0x01, 0xD1E3)
            await asyncio.sleep(0.01)
            raw_b = bus.read_word_data(ADS1115_ADDR, 0x00)
            # Convert to 0-100 range
            self.status.rssi_a = min(100, max(0, (raw_a >> 8) & 0xFF))
            self.status.rssi_b = min(100, max(0, (raw_b >> 8) & 0xFF))
        except Exception as e:
            log.debug(f"RSSI read failed: {e}")

    async def start(self):
        self._init_gpio()
        self.status.connected = True
        log.info(f"RTC6715 VRX ready — {self.status.frequency_mhz} MHz")
        while True:
            await self._read_rssi()
            await asyncio.sleep(0.5)

    async def stop(self):
        if self._gpio:
            self._gpio.cleanup()
