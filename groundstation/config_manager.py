import json
import logging
import os

log = logging.getLogger("config")

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")

DEFAULT = {
    "vrx": {
        "driver":  "foxeer_uart",
        "options": {"port": "/dev/ttyAMA2"},
        "band":    "F",
        "channel": 2
    },
    "tx": {
        "type":     "ppm",
        "gpio_pin": 18,
        "port":     "/dev/ttyAMA0",
        "baud":     400000
    },
    "telemetry": {
        "drivers": ["dummy"],
        "mavlink":    {"port": "/dev/ttyAMA4", "baud": 57600},
        "msp":        {"port": "/dev/ttyAMA4", "baud": 115200},
        "ltm":        {"port": "/dev/ttyAMA4", "baud": 2400},
        "smartport":  {"port": "/dev/ttyAMA4", "baud": 57600},
        "hott":       {"port": "/dev/ttyAMA4", "baud": 19200},
        "foxeer_uart":{"port": "/dev/ttyAMA3", "baud": 115200}
    },
    "controller": {
        "axes": {
            "ch1_roll":     {"src": "rx",  "invert": False, "expo": 0.3, "rate": 1.0},
            "ch2_pitch":    {"src": "ry",  "invert": True,  "expo": 0.3, "rate": 1.0},
            "ch3_throttle": {"src": "ly",  "invert": False, "expo": 0.0, "rate": 1.0},
            "ch4_yaw":      {"src": "lx",  "invert": False, "expo": 0.3, "rate": 1.0}
        },
        "dead_zone": 0.05,
        "buttons": {
            "ch5":  {"src": "btn_a", "mode": "toggle",    "on": 1.0,  "off": -1.0},
            "ch6":  {"src": "btn_b", "mode": "toggle",    "on": 1.0,  "off": -1.0},
            "ch7":  {"src": "btn_x", "mode": "momentary", "on": 1.0,  "off": -1.0},
            "ch8":  {"src": "btn_y", "mode": "momentary", "on": 1.0,  "off": -1.0},
            "ch9":  {"src": "btn_lg","mode": "toggle",    "on": 1.0,  "off": -1.0},
            "ch10": {"src": "btn_rg","mode": "toggle",    "on": 1.0,  "off": -1.0},
            "ch11": {"src": "btn_lt","mode": "momentary", "on": 1.0,  "off": -1.0},
            "ch12": {"src": "btn_rt","mode": "momentary", "on": 1.0,  "off": -1.0}
        },
        "failsafe": {
            "ch1": 0.0, "ch2": 0.0, "ch3": -1.0, "ch4": 0.0,
            "ch5": -1.0, "ch6": -1.0, "ch7": -1.0, "ch8": -1.0
        }
    }
}


def load() -> dict:
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH) as f:
                saved = json.load(f)
            return _deep_merge(DEFAULT, saved)
        except Exception as e:
            log.warning(f"Config load failed: {e} — using defaults")
    return json.loads(json.dumps(DEFAULT))


def save(cfg: dict):
    with open(CONFIG_PATH, "w") as f:
        json.dump(cfg, f, indent=2)
    log.info("Config saved")


def _deep_merge(base: dict, override: dict) -> dict:
    result = base.copy()
    for k, v in override.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = _deep_merge(result[k], v)
        else:
            result[k] = v
    return result
