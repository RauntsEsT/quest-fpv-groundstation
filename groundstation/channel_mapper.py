import logging
import struct
import math

log = logging.getLogger("channel_mapper")

# UDP packet Quest → RPi:
# Header: 4 axes (float32) + 8 buttons (uint8 bitmask)
# Total: 16 + 1 = 17 bytes
PACKET_AXES    = "4f"    # lx, ly, rx, ry
PACKET_BUTTONS = "B"     # bitmask: A B X Y LG RG LT RT
PACKET_FORMAT  = PACKET_AXES + PACKET_BUTTONS
PACKET_SIZE    = struct.calcsize(PACKET_FORMAT)

# Legacy: 8 floats (backward compat)
LEGACY_FORMAT = "8f"
LEGACY_SIZE   = struct.calcsize(LEGACY_FORMAT)

BTN_A  = 0x01
BTN_B  = 0x02
BTN_X  = 0x04
BTN_Y  = 0x08
BTN_LG = 0x10
BTN_RG = 0x20
BTN_LT = 0x40
BTN_RT = 0x80

BTN_MAP = {
    "btn_a": BTN_A, "btn_b": BTN_B, "btn_x": BTN_X, "btn_y": BTN_Y,
    "btn_lg": BTN_LG, "btn_rg": BTN_RG, "btn_lt": BTN_LT, "btn_rt": BTN_RT
}

AXIS_MAP = {"lx": 0, "ly": 1, "rx": 2, "ry": 3}


def _expo(value: float, expo: float) -> float:
    """Expo curve: expo=0 = linear, expo=1 = max curve"""
    if expo <= 0:
        return value
    e = max(0.0, min(1.0, expo))
    return value * (1 - e) + math.copysign(value**2, value) * e


def _dead_zone(value: float, dz: float) -> float:
    if abs(value) < dz:
        return 0.0
    sign = 1 if value > 0 else -1
    return sign * (abs(value) - dz) / (1.0 - dz)


class ChannelMapper:
    def __init__(self, cfg: dict):
        self._cfg = cfg["controller"]
        self._btn_states: dict[str, bool] = {k: False for k in BTN_MAP}
        self._toggle_vals: dict[str, float] = {}
        # Init toggle values to "off"
        for ch, bcfg in self._cfg["buttons"].items():
            self._toggle_vals[ch] = bcfg["off"]

    def update_config(self, cfg: dict):
        self._cfg = cfg["controller"]

    def parse(self, data: bytes) -> tuple[float, ...]:
        if len(data) == PACKET_SIZE:
            *axes, btn_mask = struct.unpack(PACKET_FORMAT, data)
        elif len(data) == LEGACY_SIZE:
            vals = struct.unpack(LEGACY_FORMAT, data)
            axes = list(vals[:4])
            btn_mask = 0
        else:
            return None

        axes = list(axes)
        dz  = self._cfg.get("dead_zone", 0.05)
        ax_cfg = self._cfg["axes"]
        channels = [0.0] * 16

        # Axis channels (CH1-4)
        for ch_name, acfg in ax_cfg.items():
            src_idx  = AXIS_MAP.get(acfg["src"], 0)
            raw      = axes[src_idx] if src_idx < len(axes) else 0.0
            val      = _dead_zone(raw, dz)
            val      = _expo(val, acfg.get("expo", 0.0))
            val     *= acfg.get("rate", 1.0)
            if acfg.get("invert", False):
                val = -val
            # Map ch name to index
            ch_idx = {"ch1_roll": 0, "ch2_pitch": 1,
                      "ch3_throttle": 2, "ch4_yaw": 3}.get(ch_name, 0)
            channels[ch_idx] = max(-1.0, min(1.0, val))

        # Button channels (CH5-16)
        for ch_name, bcfg in self._cfg["buttons"].items():
            ch_idx = int(ch_name.replace("ch", "")) - 1
            if ch_idx >= 16:
                continue
            src     = bcfg["src"]
            bit     = BTN_MAP.get(src, 0)
            pressed = bool(btn_mask & bit)
            prev    = self._btn_states.get(src, False)
            mode    = bcfg.get("mode", "momentary")

            if mode == "toggle":
                if pressed and not prev:
                    self._toggle_vals[ch_name] = (
                        bcfg["on"] if self._toggle_vals[ch_name] == bcfg["off"]
                        else bcfg["off"]
                    )
                channels[ch_idx] = self._toggle_vals[ch_name]
            else:  # momentary
                channels[ch_idx] = bcfg["on"] if pressed else bcfg["off"]

            self._btn_states[src] = pressed

        return tuple(channels)
