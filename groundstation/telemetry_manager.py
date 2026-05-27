import asyncio
import logging
import time
from telemetry_base import TelemetryBase, TelemetryData

log = logging.getLogger("telem_manager")

DRIVERS = {
    "mavlink":    ("telemetry_mavlink",    "MAVLinkTelemetry"),
    "msp":        ("telemetry_msp",        "MSPTelemetry"),
    "crsf":       ("telemetry_crsf",       "CRSFTelemetry"),
    "smartport":  ("telemetry_smartport",  "SmartPortTelemetry"),
    "ltm":        ("telemetry_ltm",        "LTMTelemetry"),
    "hott":       ("telemetry_hott",       "HoTTTelemetry"),
    "dummy":      ("telemetry_dummy",      "DummyTelemetry"),
}


def create_driver(name: str, **kwargs) -> TelemetryBase:
    if name not in DRIVERS:
        raise ValueError(f"Unknown telemetry driver: {name}. Options: {list(DRIVERS)}")
    mod_name, cls_name = DRIVERS[name]
    import importlib
    cls = getattr(importlib.import_module(mod_name), cls_name)
    inst = cls(**kwargs)
    log.info(f"Telemetry driver loaded: {name}")
    return inst


class TelemetryManager:
    """
    Haldab mitut telemeetria draiverit korraga.
    Ühendab andmed üheks TelemetryData objektiks.
    Draiverid seadistatakse env muutujatega:

      TELEM_DRIVERS=mavlink,crsf        # komaga eraldatud nimekiri
      TELEM_MAVLINK_PORT=/dev/ttyAMA4
      TELEM_MAVLINK_BAUD=57600
      TELEM_MSP_PORT=/dev/ttyAMA4
      TELEM_MSP_BAUD=115200
      TELEM_LTM_PORT=/dev/ttyAMA4
      TELEM_LTM_BAUD=2400
    """

    def __init__(self, driver_names: list[str], configs: dict | None = None):
        self.merged = TelemetryData()
        configs = configs or {}
        self._drivers: list[TelemetryBase] = []
        for name in driver_names:
            kwargs = configs.get(name, {})
            self._drivers.append(create_driver(name, **kwargs))

    @classmethod
    def from_env(cls) -> "TelemetryManager":
        import os
        names_str = os.getenv("TELEM_DRIVERS", "dummy")
        names = [n.strip() for n in names_str.split(",") if n.strip()]
        configs = {}
        for name in names:
            prefix = f"TELEM_{name.upper()}_"
            cfg = {}
            port = os.getenv(f"{prefix}PORT")
            baud = os.getenv(f"{prefix}BAUD")
            if port:
                cfg["port"] = port
            if baud:
                cfg["baud"] = int(baud)
            configs[name] = cfg
        log.info(f"Telemetry drivers: {names}")
        return cls(names, configs)

    async def start(self):
        tasks = [asyncio.create_task(d.start()) for d in self._drivers]
        merge_task = asyncio.create_task(self._merge_loop())
        await asyncio.gather(*tasks, merge_task)

    async def _merge_loop(self):
        while True:
            self.merged = TelemetryData()
            for d in self._drivers:
                if d.data.age_seconds() < 5:
                    self.merged.merge(d.data)
            await asyncio.sleep(0.1)

    def get_dict(self) -> dict:
        d = self.merged
        return {
            "connected":         d.connected,
            "protocol":          d.protocol,
            "armed":             d.armed,
            "flight_mode":       d.flight_mode,
            "failsafe":          d.failsafe,
            "altitude_m":        round(d.altitude_m, 1),
            "altitude_rel_m":    round(d.altitude_rel_m, 1),
            "speed_ms":          round(d.speed_ms, 1),
            "vertical_speed_ms": round(d.vertical_speed_ms, 1),
            "heading_deg":       round(d.heading_deg, 1),
            "roll_deg":          round(d.roll_deg, 1),
            "pitch_deg":         round(d.pitch_deg, 1),
            "yaw_deg":           round(d.yaw_deg, 1),
            "lat":               d.lat,
            "lon":               d.lon,
            "gps_fix":           d.gps_fix,
            "satellites":        d.satellites,
            "home_distance_m":   round(d.home_distance_m, 1),
            "home_bearing_deg":  round(d.home_bearing_deg, 1),
            "voltage_v":         round(d.voltage_v, 2),
            "current_a":         round(d.current_a, 1),
            "capacity_used_mah": d.capacity_used_mah,
            "battery_pct":       d.battery_pct,
            "rssi_pct":          d.rssi_pct,
            "link_quality":      d.link_quality,
            "snr_db":            round(d.snr_db, 1),
            "tx_power_mw":       d.tx_power_mw,
            "age_s":             round(d.age_seconds(), 1),
        }
