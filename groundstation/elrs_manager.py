import asyncio
import serial
import struct
import logging
from dataclasses import dataclass

log = logging.getLogger("elrs_manager")

CRSF_ADDRESS_FC = 0xC8
CRSF_FRAMETYPE_RC_CHANNELS = 0x16
CRSF_CENTER = 992
CRSF_RANGE = 819  # 992 ± 819 = 172..1811


@dataclass
class LinkStats:
    rssi_ant1: int = 0
    rssi_ant2: int = 0
    link_quality: int = 0
    snr: int = 0
    tx_power_mw: int = 0


def _crsf_crc8(data: bytes) -> int:
    crc = 0
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = ((crc << 1) ^ 0xD5) if crc & 0x80 else crc << 1
            crc &= 0xFF
    return crc


def _float_to_crsf(value: float) -> int:
    return int(CRSF_CENTER + max(-1.0, min(1.0, value)) * CRSF_RANGE)


def build_rc_packet(channels: tuple) -> bytes:
    ch = [_float_to_crsf(v) if i < len(channels) else CRSF_CENTER
          for i in range(16)
          for v in [channels[i] if i < len(channels) else 0.0]]

    # Pack 16 × 11-bit values into 22 bytes
    bits = bit_count = 0
    packed = bytearray()
    for val in ch:
        bits |= (val & 0x7FF) << bit_count
        bit_count += 11
        while bit_count >= 8:
            packed.append(bits & 0xFF)
            bits >>= 8
            bit_count -= 8

    payload = bytes([CRSF_FRAMETYPE_RC_CHANNELS]) + bytes(packed)
    frame = bytes([CRSF_ADDRESS_FC, len(payload) + 1]) + payload
    return frame + bytes([_crsf_crc8(payload)])


class ELRSManager:
    """
    Manages ELRS TX module (EMAX Aeris Link) over UART.
    Sends CRSF RC channel packets and reads link statistics.
    UART: RPi5 GPIO14(TX)→ELRS RX, GPIO15(RX)←ELRS TX
    """

    def __init__(self, port: str = "/dev/ttyAMA0", baud: int = 420000):
        self.port = port
        self.baud = baud
        self.stats = LinkStats()
        self._serial: serial.Serial | None = None
        self._channels: tuple = (0.0,) * 8

    def _open(self):
        if self._serial is None or not self._serial.is_open:
            self._serial = serial.Serial(self.port, self.baud, timeout=0)
            log.info(f"ELRS UART open: {self.port} @ {self.baud}")

    def send_channels(self, channels: tuple):
        try:
            self._open()
            self._channels = channels
            self._serial.write(build_rc_packet(channels))
        except serial.SerialException as e:
            log.error(f"UART write error: {e}")
            self._serial = None

    async def start(self):
        """Continuously send channel packets at 50Hz (keepalive + failsafe)."""
        log.info("ELRS manager started")
        self._open()
        while True:
            try:
                self._serial.write(build_rc_packet(self._channels))
            except Exception as e:
                log.warning(f"UART write error: {e}")
                self._serial = None
                self._open()
            await asyncio.sleep(0.02)  # 50 Hz
