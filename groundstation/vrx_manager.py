import logging
from vrx_base import VRXBase, VRXStatus

log = logging.getLogger("vrx_manager")

VRX_DRIVERS = {
    "rtc6715":     ("vrx_rtc6715",  "RTC6715VRX"),
    "akk331":      ("vrx_akk331",   "AKK331VRX"),
    "button":      ("vrx_button",   "ButtonVRX"),
    "foxeer_uart": ("vrx_uart",     "FoxeerWildfireUART"),
    "walksnail":   ("vrx_digital",  "WalksnailVRX"),
    "hdzero":      ("vrx_digital",  "HDZeroVRX"),
    "dji_o3":      ("vrx_digital",  "DJIO3VRX"),
    "dummy":       ("vrx_dummy",    "DummyVRX"),
}


def create_vrx(driver_name: str, **kwargs) -> VRXBase:
    """
    Factory function — returns VRX instance by driver name.

    driver_name options:
        "rtc6715"     — analog VRX with SPI pads (RTC6715 chip)
        "button"      — any analog VRX via button emulation (GPIO transistors)
        "foxeer_uart" — Foxeer Wildfire via UART
        "walksnail"   — Walksnail Avatar digital
        "hdzero"      — HDZero digital
        "dji_o3"      — DJI O3/O3+ digital
        "dummy"       — no hardware (testing)
    """
    if driver_name not in VRX_DRIVERS:
        raise ValueError(f"Unknown VRX driver: {driver_name}. "
                         f"Options: {list(VRX_DRIVERS.keys())}")
    module_name, class_name = VRX_DRIVERS[driver_name]
    import importlib
    module = importlib.import_module(module_name)
    cls = getattr(module, class_name)
    instance = cls(**kwargs)
    log.info(f"VRX driver loaded: {driver_name} ({class_name})")
    return instance
