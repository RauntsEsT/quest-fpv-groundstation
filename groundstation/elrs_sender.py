import serial
import struct
import logging

log = logging.getLogger("elrs_sender")

# CRSF channel range: 172-1811 (992 = center)
CRSF_CENTER = 992
CRSF_RANGE = 819  # 992 +/- 819 covers 172-1811

CRSF_ADDRESS_FC = 0xC8
CRSF_FRAMETYPE_RC_CHANNELS = 0x16


def float_to_crsf(value: float) -> int:
    """Convert -1.0..1.0 to CRSF channel value 172..1811."""
    return int(CRSF_CENTER + value * CRSF_RANGE)


def _crsf_crc8(data: bytes) -> int:
    crc = 0
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 0x80:
                crc = (crc << 1) ^ 0xD5
            else:
                crc <<= 1
            crc &= 0xFF
    return crc


def build_crsf_rc_packet(channels: tuple) -> bytes:
    """Pack 16 CRSF channels (11 bits each) into a CRSF RC frame."""
    ch = [float_to_crsf(v) if i < len(channels) else CRSF_CENTER for i, v in enumerate(range(16))]
    for i, v in enumerate(channels[:16]):
        ch[i] = float_to_crsf(v)

    # Pack 16 x 11-bit values into 22 bytes
    bits = 0
    bit_count = 0
    packed = bytearray()
    for val in ch:
        bits |= (val & 0x7FF) << bit_count
        bit_count += 11
        while bit_count >= 8:
            packed.append(bits & 0xFF)
            bits >>= 8
            bit_count -= 8

    payload = bytes([CRSF_FRAMETYPE_RC_CHANNELS]) + bytes(packed)
    frame_len = len(payload) + 1  # +1 for CRC
    header = bytes([CRSF_ADDRESS_FC, frame_len])
    crc = _crsf_crc8(payload)
    return header + payload + bytes([crc])


class ELRSSender:
    def __init__(self, port: str, baud: int):
        self.port = port
        self.baud = baud
        self._serial = None

    def _open(self):
        if self._serial is None or not self._serial.is_open:
            self._serial = serial.Serial(self.port, self.baud, timeout=0)
            log.info(f"Opened UART {self.port} at {self.baud} baud")

    def send_channels(self, channels: tuple):
        try:
            self._open()
            packet = build_crsf_rc_packet(channels)
            self._serial.write(packet)
        except serial.SerialException as e:
            log.error(f"UART error: {e}")
            self._serial = None
