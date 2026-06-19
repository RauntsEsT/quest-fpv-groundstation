import asyncio
import logging
import struct
import serial
from telemetry_base import TelemetryBase

log = logging.getLogger("telem_smartport")

# FrSky SmartPort sensor IDs
SP_VFAS    = 0x0210   # Voltage
SP_CURR    = 0x0200   # Current
SP_FUEL    = 0x0600   # Battery %
SP_GPS_LAT = 0x0800
SP_GPS_LON = 0x0820
SP_GPS_ALT = 0x0820
SP_VSPD    = 0x0110   # Vertical speed
SP_ALT     = 0x0100   # Altitude
SP_HDOP    = 0x082A
SP_GPS_SPD = 0x0830
SP_HEADING = 0x0840
SP_T1      = 0x0400   # FC mode
SP_T2      = 0x0410   # GPS sats + fix
SP_ACCX    = 0x0700
SP_ACCY    = 0x0710
SP_ACCZ    = 0x0720
SP_RXBT    = 0x0F00   # RX battery


class SmartPortTelemetry(TelemetryBase):
    """
    FrSky SmartPort / FPort telemetry.
    UART: half-duplex, baud 57600
    Wiring: JR-pin5 → inverter → RPi GPIO13 (ttyAMA4 RX)
    Vajalik: signal inverter (transistor või SN74LVC1G04)

    Konfiguratsioon FC-s:
      Betaflight: Ports → UART X → Telemetry → SmartPort
    """

    def __init__(self, port: str = "/dev/ttyAMA4", baud: int = 57600):
        super().__init__()
        self.port = port
        self.baud = baud
        self.data.protocol = "smartport"
        self._ser: serial.Serial | None = None

    def _open(self) -> bool:
        try:
            self._ser = serial.Serial(
                self.port, self.baud,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=0.1
            )
            log.info(f"SmartPort UART: {self.port} @ {self.baud}")
            return True
        except Exception as e:
            log.error(f"SmartPort open failed: {e}")
            return False

    def _parse_value(self, sensor_id: int, raw: int):
        d = self.data
        if sensor_id == SP_VFAS:
            d.voltage_v = (raw & 0x1FFFFFFF) / 100.0
        elif sensor_id == SP_CURR:
            d.current_a = (raw & 0x1FFFFFFF) / 10.0
        elif sensor_id == SP_FUEL:
            d.battery_pct = raw & 0xFF
        elif sensor_id == SP_ALT:
            d.altitude_rel_m = (raw & 0x1FFFFFFF) / 100.0
        elif sensor_id == SP_VSPD:
            d.vertical_speed_ms = struct.unpack('<i', struct.pack('<I', raw))[0] / 100.0
        elif sensor_id == SP_GPS_SPD:
            d.gps_speed_ms = (raw & 0x1FFFFFFF) / 1000.0 / 3.6
        elif sensor_id == SP_HEADING:
            d.heading_deg = (raw & 0x1FFFFFFF) / 100.0
        elif sensor_id == SP_T1:
            d.flight_mode = str(raw)
        elif sensor_id == SP_T2:
            d.gps_fix = (raw // 1000) % 10
            d.satellites = raw % 100
        elif sensor_id == SP_GPS_LAT or sensor_id == SP_GPS_LON:
            deg = (raw >> 4) & 0x3FFFF
            bp = deg // 10000
            ap = deg % 10000
            coord = bp + ap / 6000.0
            if raw & (1 << 31):
                coord = -coord
            if sensor_id == SP_GPS_LAT:
                d.lat = coord
            else:
                d.lon = coord
        d.connected = True

    async def _read_loop(self):
        buf = bytearray()
        while True:
            data = self._ser.read(64)
            if data:
                buf.extend(data)
                # Parse SmartPort frames (0x7E + sensor_id 2B + value 4B + CRC)
                while len(buf) >= 8:
                    if buf[0] != 0x7E:
                        buf.pop(0)
                        continue
                    frame = bytes(buf[:8])
                    buf = buf[8:]
                    sensor_id = struct.unpack_from('<H', frame, 1)[0]
                    value     = struct.unpack_from('<I', frame, 3)[0]
                    self._parse_value(sensor_id, value)
            else:
                await asyncio.sleep(0.005)

    async def start(self):
        while not self._open():
            await asyncio.sleep(5)
        log.info("SmartPort telemetry running")
        try:
            await self._read_loop()
        except Exception as e:
            log.error(f"SmartPort error: {e}")
            self.data.connected = False

    async def stop(self):
        if self._ser:
            self._ser.close()
