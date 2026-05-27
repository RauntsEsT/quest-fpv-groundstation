import asyncio
import logging
import math
import time
from telemetry_base import TelemetryBase

log = logging.getLogger("telem_dummy")


class DummyTelemetry(TelemetryBase):
    """Simuleerib telemeetriat ilma riistvarata — arenduse/testimise jaoks."""

    def __init__(self):
        super().__init__()
        self.data.protocol = "dummy"
        self.data.connected = True
        self.data.armed = True
        self.data.flight_mode = "HORIZON"
        self.data.gps_fix = 3
        self.data.satellites = 12
        self.data.lat = 59.4370
        self.data.lon = 24.7536

    async def start(self):
        log.info("Dummy telemetry started")
        t = 0
        while True:
            t += 0.1
            self.data.altitude_rel_m    = 50 + 10 * math.sin(t * 0.1)
            self.data.speed_ms          = 8 + 4 * math.sin(t * 0.07)
            self.data.vertical_speed_ms = math.sin(t * 0.3)
            self.data.heading_deg       = (t * 5) % 360
            self.data.roll_deg          = 15 * math.sin(t * 0.4)
            self.data.pitch_deg         = 5 * math.sin(t * 0.3)
            self.data.voltage_v         = 15.8 - t * 0.001
            self.data.current_a         = 12 + 3 * math.sin(t * 0.2)
            self.data.battery_pct       = max(0, 100 - int(t * 0.1))
            self.data.rssi_pct          = 95 - int(5 * math.sin(t * 0.05))
            self.data.link_quality      = 99
            self.data.home_distance_m   = 100 + 50 * math.sin(t * 0.05)
            self.data.last_update       = time.time()
            await asyncio.sleep(0.1)

    async def stop(self):
        pass
