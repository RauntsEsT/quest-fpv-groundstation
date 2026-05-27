import asyncio
import logging
import struct
import serial
from telemetry_base import TelemetryBase

log = logging.getLogger("telem_hott")


class HoTTTelemetry(TelemetryBase):
    """
    Graupner HoTT telemetry (SUMD/SUMD+).
    Baud: 19200, half-duplex
    Kasutusel vanematel Graupner/MZ saatjatega.
    """

    def __init__(self, port: str = "/dev/ttyAMA4", baud: int = 19200):
        super().__init__()
        self.port = port
        self.baud = baud
        self.data.protocol = "hott"
        self._ser: serial.Serial | None = None

    def _open(self) -> bool:
        try:
            self._ser = serial.Serial(self.port, self.baud, timeout=0.1)
            log.info(f"HoTT UART: {self.port} @ {self.baud}")
            return True
        except Exception as e:
            log.error(f"HoTT open failed: {e}")
            return False

    def _parse_gps_module(self, data: bytes):
        if len(data) < 45:
            return
        d = self.data
        # HoTT GPS module binary format
        d.voltage_v    = data[10] / 10.0
        d.altitude_rel_m = struct.unpack_from('<H', data, 14)[0] - 500.0
        d.gps_speed_ms = data[20] / 3.6
        lat_deg = data[21]; lat_min = struct.unpack_from('<H', data, 22)[0]
        lon_deg = data[24]; lon_min = struct.unpack_from('<H', data, 25)[0]
        d.lat = lat_deg + lat_min / 6000.0
        d.lon = lon_deg + lon_min / 6000.0
        d.home_distance_m = struct.unpack_from('<H', data, 29)[0] * 10.0
        d.home_bearing_deg = struct.unpack_from('<H', data, 31)[0]
        d.gps_fix = 3 if data[40] > 3 else 0
        d.satellites = data[40]
        d.connected = True

    async def start(self):
        while not self._open():
            await asyncio.sleep(5)
        log.info("HoTT telemetry running")
        buf = bytearray()
        while True:
            try:
                data = self._ser.read(128)
                if data:
                    buf.extend(data)
                    # HoTT GPS module starts with 0x7C 0x80
                    idx = 0
                    while idx < len(buf) - 1:
                        if buf[idx] == 0x7C and buf[idx+1] == 0x80:
                            if len(buf) - idx >= 45:
                                self._parse_gps_module(bytes(buf[idx:idx+45]))
                                idx += 45
                            else:
                                break
                        else:
                            idx += 1
                    buf = buf[idx:]
                else:
                    await asyncio.sleep(0.01)
            except Exception as e:
                log.warning(f"HoTT error: {e}")
                await asyncio.sleep(2)

    async def stop(self):
        if self._ser:
            self._ser.close()
