import asyncio
import logging
import struct
from telemetry_base import TelemetryBase, TelemetryData

log = logging.getLogger("telem_crsf")

# CRSF telemetry frame types
CRSF_FRAMETYPE_GPS          = 0x02
CRSF_FRAMETYPE_VARIO        = 0x07
CRSF_FRAMETYPE_BATTERY      = 0x08
CRSF_FRAMETYPE_BARO_ALTITUDE = 0x09
CRSF_FRAMETYPE_HEARTBEAT    = 0x0B
CRSF_FRAMETYPE_LINK_STATS   = 0x14
CRSF_FRAMETYPE_ATTITUDE     = 0x1E
CRSF_FRAMETYPE_FLIGHT_MODE  = 0x21


class CRSFTelemetry(TelemetryBase):
    """
    CRSF telemetry — ExpressLRS / TBS Crossfire.
    Loeb sama UART pealt mis ELRS TX moodul saadab tagasi.
    Port: /dev/ttyAMA0 @ 420000 baud (jagatud ELRSManager-iga)

    NB: ELRSManager peab CRSF telemetry pakette edastama siia.
    Seotud elrs_manager.py-ga — vaata integrate() meetodit.
    """

    def __init__(self):
        super().__init__()
        self.data.protocol = "crsf"
        self._queue: asyncio.Queue = asyncio.Queue()

    def feed(self, frame_type: int, payload: bytes):
        """Called by ELRSManager when it receives a telemetry frame."""
        self._queue.put_nowait((frame_type, payload))

    def _parse(self, frame_type: int, payload: bytes):
        d = self.data
        try:
            if frame_type == CRSF_FRAMETYPE_LINK_STATS:
                # uplink_rssi_1, uplink_rssi_2, uplink_lq, uplink_snr,
                # active_antenna, rf_mode, uplink_power,
                # downlink_rssi, downlink_lq, downlink_snr
                (ul_rssi1, ul_rssi2, ul_lq, ul_snr, antenna,
                 rf_mode, ul_power, dl_rssi, dl_lq, dl_snr) = \
                    struct.unpack_from('BBBbBBBBBb', payload)
                d.rssi_pct     = ul_lq
                d.link_quality = ul_lq
                d.snr_db       = float(ul_snr)
                d.tx_power_mw  = _crsf_power(ul_power)
                d.connected    = True

            elif frame_type == CRSF_FRAMETYPE_GPS:
                lat, lon, speed, heading, alt, sats = \
                    struct.unpack_from('>iiHHHB', payload)
                d.lat          = lat / 1e7
                d.lon          = lon / 1e7
                d.gps_speed_ms = speed / 36.0   # km/h*10 → m/s
                d.heading_deg  = heading / 100.0
                d.altitude_m   = alt / 10.0 - 1000
                d.satellites   = sats

            elif frame_type == CRSF_FRAMETYPE_BATTERY:
                volt, curr, cap, pct = struct.unpack_from('>HHiB', payload)
                d.voltage_v         = volt / 10.0
                d.current_a         = curr / 10.0
                d.capacity_used_mah = cap
                d.battery_pct       = pct

            elif frame_type == CRSF_FRAMETYPE_ATTITUDE:
                pitch, roll, yaw = struct.unpack_from('>hhh', payload)
                d.pitch_deg = pitch / 10000.0 * 57.296
                d.roll_deg  = roll  / 10000.0 * 57.296
                d.yaw_deg   = yaw   / 10000.0 * 57.296

            elif frame_type == CRSF_FRAMETYPE_FLIGHT_MODE:
                d.flight_mode = payload.rstrip(b'\x00').decode('ascii', errors='ignore')

            elif frame_type == CRSF_FRAMETYPE_VARIO:
                vario, = struct.unpack_from('>h', payload)
                d.vertical_speed_ms = vario / 100.0

            elif frame_type == CRSF_FRAMETYPE_BARO_ALTITUDE:
                alt, vario = struct.unpack_from('>Hh', payload)
                d.altitude_rel_m    = (alt / 10.0) - 10000
                d.vertical_speed_ms = vario / 100.0

        except struct.error as e:
            log.debug(f"CRSF parse error type=0x{frame_type:02x}: {e}")

    async def start(self):
        log.info("CRSF telemetry listening (fed by ELRSManager)")
        while True:
            frame_type, payload = await self._queue.get()
            self._parse(frame_type, payload)

    async def stop(self):
        pass


def _crsf_power(idx: int) -> int:
    table = [0, 10, 25, 100, 500, 1000, 2000, 250, 50]
    return table[idx] if idx < len(table) else 0
