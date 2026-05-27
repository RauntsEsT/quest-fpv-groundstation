import asyncio
import logging
import serial
from vrx_base import VRXBase
from vrx_bands import BANDS_5800, BANDS_1200

log = logging.getLogger("vrx_uart")


class UARTVRXBase(VRXBase):
    """
    Base for VRX modules with UART control interface.
    Wiring: RPi GPIO4 (TX) → VRX RX pad, RPi GPIO5 (RX) → VRX TX pad
    Enable in /boot/firmware/config.txt: dtoverlay=uart2
    """

    def __init__(self, port: str = "/dev/ttyAMA2", baud: int = 115200):
        super().__init__()
        self.port = port
        self.baud = baud
        self._ser: serial.Serial | None = None

    def _open(self):
        if not self._ser or not self._ser.is_open:
            self._ser = serial.Serial(self.port, self.baud, timeout=0.1)

    async def start(self):
        try:
            self._open()
            self.status.connected = True
            log.info(f"VRX UART open: {self.port} @ {self.baud}")
        except serial.SerialException as e:
            log.error(f"VRX UART open failed: {e}")
        while True:
            await self._poll()
            await asyncio.sleep(0.5)

    async def stop(self):
        if self._ser:
            self._ser.close()

    async def _poll(self):
        pass  # override in subclass for telemetry reading


class FoxeerWildfireUART(UARTVRXBase):
    """Foxeer Wildfire UART protocol (if available on module)."""

    def __init__(self, port="/dev/ttyAMA2"):
        super().__init__(port, baud=115200)
        self.status.driver = "foxeer_wildfire_uart"

    def set_channel(self, band: str, channel: int):
        all_bands = {**BANDS_5800, **BANDS_1200}
        band = band.upper()
        if band not in all_bands or not 1 <= channel <= 8:
            raise ValueError(f"Invalid band/channel: {band}{channel}")
        self.status.band = band
        self.status.channel = channel
        self.status.frequency_mhz = all_bands[band][channel - 1]
        if self._ser and self._ser.is_open:
            # Foxeer UART command format (0xAA + band_idx + channel)
            band_idx = list(all_bands.keys()).index(band)
            cmd = bytes([0xAA, band_idx, channel - 1, 0x55])
            self._ser.write(cmd)
            log.info(f"Foxeer UART: {band}{channel} = {self.status.frequency_mhz} MHz")
