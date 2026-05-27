import asyncio
import logging
import struct
import serial
from telemetry_base import TelemetryBase

log = logging.getLogger("telem_ltm")

# LTM frame types
LTM_G = ord('G')   # GPS
LTM_A = ord('A')   # Attitude
LTM_S = ord('S')   # Status
LTM_O = ord('O')   # Origin (home)
LTM_N = ord('N')   # Navigation
LTM_X = ord('X')   # Extra


class LTMTelemetry(TelemetryBase):
    """
    LTM (Lightweight Telemetry) — iNav, Cleanflight, Betaflight.
    Lightweight, ühepoolne 100Hz protokoll.
    UART: RPi GPIO12/13 → FC LTM port, baud 2400-19200

    FC seadistus:
      iNav: Ports → UART X → Telemetry → LTM
    """

    def __init__(self, port: str = "/dev/ttyAMA4", baud: int = 2400):
        super().__init__()
        self.port = port
        self.baud = baud
        self.data.protocol = "ltm"
        self._ser: serial.Serial | None = None

    def _open(self) -> bool:
        try:
            self._ser = serial.Serial(self.port, self.baud, timeout=0.1)
            log.info(f"LTM UART: {self.port} @ {self.baud}")
            return True
        except Exception as e:
            log.error(f"LTM open failed: {e}")
            return False

    def _parse(self, ftype: int, payload: bytes):
        d = self.data
        try:
            if ftype == LTM_G:   # GPS frame: lat lon speed alt sats/fix
                lat, lon, speed, alt, sats_fix = struct.unpack_from('<iiBiB', payload)
                d.lat          = lat / 1e7
                d.lon          = lon / 1e7
                d.gps_speed_ms = speed / 100.0
                d.altitude_m   = alt / 100.0
                d.satellites   = sats_fix >> 2
                d.gps_fix      = sats_fix & 0x03
                d.connected    = True

            elif ftype == LTM_A:  # Attitude: pitch roll heading
                pitch, roll, heading = struct.unpack_from('<hhH', payload)
                d.pitch_deg   = float(pitch)
                d.roll_deg    = float(roll)
                d.heading_deg = float(heading)

            elif ftype == LTM_S:  # Status: voltage current rssi airspeed status
                volt, curr, rssi, aspd, status = struct.unpack_from('<HHBBb', payload)
                d.voltage_v    = volt / 1000.0
                d.current_a    = curr / 1000.0
                d.rssi_pct     = rssi
                d.armed        = bool(status & 0x01)
                d.failsafe     = bool(status & 0x02)
                mode_bits = (status >> 2) & 0x1F
                d.flight_mode  = _ltm_mode(mode_bits)

            elif ftype == LTM_O:  # Origin: lat lon alt osd_fix
                lat, lon, alt, fix = struct.unpack_from('<iiIB', payload)
                # Home position stored internally for distance calc
                if d.lat and d.lon:
                    import math
                    home_lat, home_lon = lat / 1e7, lon / 1e7
                    R = 6371000
                    p = math.pi / 180
                    a = (math.sin((home_lat-d.lat)*p/2)**2 +
                         math.cos(d.lat*p)*math.cos(home_lat*p)*
                         math.sin((home_lon-d.lon)*p/2)**2)
                    d.home_distance_m = 2 * R * math.asin(math.sqrt(a))

            elif ftype == LTM_X:  # Extra: hdop sats
                hdop, sats, ltm_x2, ltm_x3 = struct.unpack_from('<HBBB', payload)
                if sats:
                    d.satellites = sats

        except struct.error as e:
            log.debug(f"LTM parse error type={chr(ftype)}: {e}")

    async def start(self):
        FRAME_SIZES = {LTM_G: 14, LTM_A: 6, LTM_S: 7,
                       LTM_O: 14, LTM_N: 6, LTM_X: 6}
        while not self._open():
            await asyncio.sleep(5)
        log.info("LTM telemetry running")
        buf = bytearray()
        while True:
            try:
                data = self._ser.read(64)
                if data:
                    buf.extend(data)
                    while len(buf) >= 3:
                        if buf[0] != 0x24 or buf[1] != 0x54:  # $T
                            buf.pop(0)
                            continue
                        ftype = buf[2]
                        size = FRAME_SIZES.get(ftype, 0)
                        if size == 0:
                            buf.pop(0)
                            continue
                        total = 4 + size  # $T + type + payload + crc
                        if len(buf) < total:
                            break
                        payload = bytes(buf[3:3+size])
                        crc = buf[3+size]
                        calc = 0
                        for b in payload:
                            calc ^= b
                        if calc == crc:
                            self._parse(ftype, payload)
                        buf = buf[total:]
                else:
                    await asyncio.sleep(0.01)
            except Exception as e:
                log.warning(f"LTM error: {e}")
                self.data.connected = False
                await asyncio.sleep(2)
                self._open()

    async def stop(self):
        if self._ser:
            self._ser.close()


def _ltm_mode(bits: int) -> str:
    modes = {0: "MANUAL", 1: "RATE", 2: "ANGLE", 3: "HORIZON",
             4: "ACRO", 5: "STABILIZED", 6: "RATTITUDE",
             7: "ALTHOLD", 8: "POSHOLD", 9: "RTH",
             10: "MISSION", 11: "LAUNCHMODE", 12: "FAILSAFE"}
    return modes.get(bits, f"MODE_{bits}")
