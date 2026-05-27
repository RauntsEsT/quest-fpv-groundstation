import asyncio
import logging
import struct
import serial
from telemetry_base import TelemetryBase, TelemetryData

log = logging.getLogger("telem_msp")

# MSP v1 command IDs
MSP_STATUS      = 101
MSP_RAW_GPS     = 106
MSP_ATTITUDE    = 108
MSP_ALTITUDE    = 109
MSP_ANALOG      = 110
MSP_RC          = 105
MSP_BATTERY     = 110

# MSP v2 command IDs (Betaflight 4.x+)
MSP2_INAV_STATUS = 0x2000


class MSPTelemetry(TelemetryBase):
    """
    MSP (MultiWii Serial Protocol) — Betaflight, iNav, Cleanflight.
    UART: RPi GPIO12(TX)/GPIO13(RX) → FC MSP port
    Baud: 115200 tüüpiliselt

    Konfigureeri FC-s:
      Betaflight: Ports → UART X → MSP (telemetry)
      iNav: Ports → UART X → MSP
    """

    def __init__(self, port: str = "/dev/ttyAMA4", baud: int = 115200):
        super().__init__()
        self.port = port
        self.baud = baud
        self.data.protocol = "msp"
        self._ser: serial.Serial | None = None

    def _open(self) -> bool:
        try:
            self._ser = serial.Serial(self.port, self.baud, timeout=0.1)
            log.info(f"MSP UART: {self.port} @ {self.baud}")
            return True
        except Exception as e:
            log.error(f"MSP open failed: {e}")
            return False

    def _build_request(self, cmd: int) -> bytes:
        """Build MSP v1 request packet."""
        return bytes([ord('$'), ord('M'), ord('<'), 0, cmd, cmd])

    def _send(self, cmd: int):
        if self._ser and self._ser.is_open:
            self._ser.write(self._build_request(cmd))

    def _recv(self) -> tuple[int, bytes] | None:
        """Read one MSP response. Returns (cmd, payload) or None."""
        if not self._ser:
            return None
        try:
            # Find header $M>
            while True:
                b = self._ser.read(1)
                if not b:
                    return None
                if b == b'$':
                    if self._ser.read(1) == b'M' and self._ser.read(1) == b'>':
                        break
            size = self._ser.read(1)[0]
            cmd  = self._ser.read(1)[0]
            payload = self._ser.read(size)
            crc = self._ser.read(1)[0]
            # Verify CRC
            check = size ^ cmd
            for byte in payload:
                check ^= byte
            if check != crc:
                return None
            return cmd, payload
        except Exception:
            return None

    def _parse(self, cmd: int, payload: bytes):
        d = self.data
        try:
            if cmd == MSP_STATUS:
                d.armed = bool(struct.unpack_from('<H', payload, 6)[0] & 1)
                d.connected = True

            elif cmd == MSP_ATTITUDE:
                roll, pitch, yaw = struct.unpack_from('<hhH', payload)
                d.roll_deg  = roll / 10.0
                d.pitch_deg = pitch / 10.0
                d.yaw_deg   = float(yaw)

            elif cmd == MSP_RAW_GPS:
                fix, numsat, lat, lon, alt, speed, gcourse = \
                    struct.unpack_from('<BBiiHHH', payload)
                d.gps_fix    = fix
                d.satellites = numsat
                d.lat        = lat / 1e7
                d.lon        = lon / 1e7
                d.altitude_m = alt / 10.0
                d.gps_speed_ms = speed / 100.0
                d.heading_deg  = gcourse / 10.0

            elif cmd == MSP_ALTITUDE:
                alt_cm, vario = struct.unpack_from('<iH', payload)
                d.altitude_rel_m    = alt_cm / 100.0
                d.vertical_speed_ms = vario / 100.0

            elif cmd == MSP_ANALOG:
                volt, mah, rssi, amps = struct.unpack_from('<BHHH', payload)
                d.voltage_v        = volt / 10.0
                d.capacity_used_mah = mah
                d.rssi_pct         = rssi * 100 // 1023
                d.current_a        = amps / 100.0

        except struct.error as e:
            log.debug(f"MSP parse error cmd={cmd}: {e}")

    async def start(self):
        while not self._open():
            await asyncio.sleep(5)

        POLL_CMDS = [MSP_STATUS, MSP_ATTITUDE, MSP_RAW_GPS,
                     MSP_ALTITUDE, MSP_ANALOG]
        log.info("MSP telemetry running")

        while True:
            try:
                for cmd in POLL_CMDS:
                    self._send(cmd)
                    result = self._recv()
                    if result:
                        self._parse(*result)
                    await asyncio.sleep(0.02)
            except Exception as e:
                log.warning(f"MSP error: {e}")
                self.data.connected = False
                await asyncio.sleep(2)
                self._open()

    async def stop(self):
        if self._ser:
            self._ser.close()
