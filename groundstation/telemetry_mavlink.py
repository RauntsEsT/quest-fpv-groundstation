import asyncio
import logging
import math
from telemetry_base import TelemetryBase, TelemetryData

log = logging.getLogger("telem_mavlink")

# MAVLink message IDs
MSG_HEARTBEAT         = 0
MSG_SYS_STATUS        = 1
MSG_GPS_RAW_INT       = 24
MSG_ATTITUDE          = 30
MSG_GLOBAL_POSITION   = 33
MSG_RC_CHANNELS       = 65
MSG_BATTERY_STATUS    = 147
MSG_VFR_HUD           = 74
MSG_NAV_CONTROLLER    = 62
MSG_HOME_POSITION     = 242


class MAVLinkTelemetry(TelemetryBase):
    """
    MAVLink telemetry — ArduPilot, PX4, iNav.
    UART: RPi GPIO12(TX)/GPIO13(RX) → FC telemetry port
    Enable: dtoverlay=uart4 in /boot/firmware/config.txt
    Baud: 57600 tüüpiliselt (konfigureeritav FC-s)

    pip install pymavlink
    """

    def __init__(self, port: str = "/dev/ttyAMA4", baud: int = 57600):
        super().__init__()
        self.port = port
        self.baud = baud
        self.data.protocol = "mavlink"
        self._mav = None

    def _connect(self):
        try:
            from pymavlink import mavutil
            self._mav = mavutil.mavlink_connection(
                self.port, baud=self.baud, source_system=255)
            log.info(f"MAVLink connected: {self.port} @ {self.baud}")
            return True
        except Exception as e:
            log.error(f"MAVLink connect failed: {e}")
            return False

    def _parse(self, msg):
        t = msg.get_type()
        d = self.data

        if t == "HEARTBEAT":
            d.armed = bool(msg.base_mode & 0x80)
            d.flight_mode = str(msg.custom_mode)
            d.connected = True

        elif t == "SYS_STATUS":
            d.voltage_v = msg.voltage_battery / 1000.0
            d.current_a = msg.current_battery / 100.0
            d.battery_pct = msg.battery_remaining
            d.rssi_pct = msg.drop_rate_comm

        elif t == "BATTERY_STATUS":
            if msg.voltages[0] != 65535:
                d.voltage_v = msg.voltages[0] / 1000.0
            d.current_a = msg.current_battery / 100.0
            d.capacity_used_mah = msg.current_consumed
            d.battery_pct = msg.battery_remaining

        elif t == "GPS_RAW_INT":
            d.lat = msg.lat / 1e7
            d.lon = msg.lon / 1e7
            d.altitude_m = msg.alt / 1000.0
            d.gps_fix = msg.fix_type
            d.satellites = msg.satellites_visible
            d.gps_speed_ms = msg.vel / 100.0

        elif t == "ATTITUDE":
            d.roll_deg = math.degrees(msg.roll)
            d.pitch_deg = math.degrees(msg.pitch)
            d.yaw_deg = math.degrees(msg.yaw)

        elif t == "VFR_HUD":
            d.speed_ms = msg.airspeed
            d.altitude_rel_m = msg.alt
            d.vertical_speed_ms = msg.climb
            d.heading_deg = msg.heading

        elif t == "GLOBAL_POSITION_INT":
            d.lat = msg.lat / 1e7
            d.lon = msg.lon / 1e7
            d.altitude_m = msg.alt / 1000.0
            d.altitude_rel_m = msg.relative_alt / 1000.0
            d.speed_ms = math.sqrt(msg.vx**2 + msg.vy**2) / 100.0
            d.vertical_speed_ms = msg.vz / -100.0
            d.heading_deg = msg.hdg / 100.0

        elif t == "HOME_POSITION":
            home_lat = msg.latitude / 1e7
            home_lon = msg.longitude / 1e7
            if d.lat and d.lon:
                d.home_distance_m = _haversine(d.lat, d.lon, home_lat, home_lon)
                d.home_bearing_deg = _bearing(d.lat, d.lon, home_lat, home_lon)

        elif t == "RC_CHANNELS":
            d.rssi_pct = msg.rssi * 100 // 255

    async def start(self):
        while not self._connect():
            await asyncio.sleep(5)
        log.info("MAVLink telemetry running")
        while True:
            try:
                msg = self._mav.recv_match(blocking=False)
                if msg:
                    self._parse(msg)
                else:
                    await asyncio.sleep(0.01)
            except Exception as e:
                log.warning(f"MAVLink error: {e}")
                self.data.connected = False
                await asyncio.sleep(2)
                self._connect()

    async def stop(self):
        if self._mav:
            self._mav.close()


def _haversine(lat1, lon1, lat2, lon2) -> float:
    R = 6371000
    p = math.pi / 180
    a = (math.sin((lat2-lat1)*p/2)**2 +
         math.cos(lat1*p)*math.cos(lat2*p)*math.sin((lon2-lon1)*p/2)**2)
    return 2 * R * math.asin(math.sqrt(a))


def _bearing(lat1, lon1, lat2, lon2) -> float:
    p = math.pi / 180
    y = math.sin((lon2-lon1)*p) * math.cos(lat2*p)
    x = (math.cos(lat1*p)*math.sin(lat2*p) -
         math.sin(lat1*p)*math.cos(lat2*p)*math.cos((lon2-lon1)*p))
    return (math.degrees(math.atan2(y, x)) + 360) % 360
