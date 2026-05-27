from abc import ABC, abstractmethod
from dataclasses import dataclass, field
import time


@dataclass
class TelemetryData:
    # Lend
    altitude_m: float = 0.0
    altitude_rel_m: float = 0.0
    speed_ms: float = 0.0
    vertical_speed_ms: float = 0.0
    heading_deg: float = 0.0

    # Asend
    roll_deg: float = 0.0
    pitch_deg: float = 0.0
    yaw_deg: float = 0.0

    # GPS
    lat: float = 0.0
    lon: float = 0.0
    gps_fix: int = 0        # 0=puudub 2=2D 3=3D
    satellites: int = 0
    gps_speed_ms: float = 0.0
    home_distance_m: float = 0.0
    home_bearing_deg: float = 0.0

    # Toide
    voltage_v: float = 0.0
    current_a: float = 0.0
    capacity_used_mah: int = 0
    battery_pct: int = 0

    # Link
    rssi_pct: int = 0
    link_quality: int = 0
    snr_db: float = 0.0
    tx_power_mw: int = 0

    # FC staatus
    armed: bool = False
    flight_mode: str = ""
    failsafe: bool = False

    # Meta
    protocol: str = ""
    connected: bool = False
    last_update: float = field(default_factory=time.time)

    def merge(self, other: "TelemetryData"):
        """Merge another source in — non-zero values overwrite."""
        for f in self.__dataclass_fields__:
            if f in ("protocol", "last_update"):
                continue
            val = getattr(other, f)
            if val not in (0, 0.0, False, ""):
                setattr(self, f, val)
        self.last_update = time.time()

    def age_seconds(self) -> float:
        return time.time() - self.last_update


class TelemetryBase(ABC):
    """Abstract base for all telemetry drivers."""

    def __init__(self):
        self.data = TelemetryData()

    @abstractmethod
    async def start(self): ...

    @abstractmethod
    async def stop(self): ...
