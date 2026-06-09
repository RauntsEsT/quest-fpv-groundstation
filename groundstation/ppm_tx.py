"""
PPM RC signal generator — Python lgpio GPIO + C busy-wait timing.

Python lgpio teeb GPIO kirjutamisi (ainus viis mis RPi5 RP1 chipiga töötab).
C teek (ppm_timing.so) teeb täpse busy-wait ajastuse GIL-i vabastades.
CPU3 affinity + SCHED_FIFO prio 99 minimeerivad jitter-i.
"""
import asyncio
import ctypes
import ctypes.util
import logging
import os
from dataclasses import dataclass

log = logging.getLogger("ppm_tx")

PPM_GPIO  = 18
FRAME_US  = 22500
PULSE_US  = 300
MIN_US    = 1000
MAX_US    = 2000
CENTER_US = 1500
NUM_CH    = 8


@dataclass
class LinkStats:
    rssi_ant1: int    = 0
    rssi_ant2: int    = 0
    link_quality: int = 0
    snr: int          = 0
    tx_power_mw: int  = 0


def _load_timing_lib():
    here = os.path.dirname(os.path.abspath(__file__))
    lib = ctypes.CDLL(os.path.join(here, "ppm_timing.so"))
    lib.busywait_us.restype  = None
    lib.busywait_us.argtypes = [ctypes.c_long]
    lib.monotonic_ns.restype  = ctypes.c_long
    lib.monotonic_ns.argtypes = []
    return lib


class PPMTransmitter:
    """
    PPM generaator: Python lgpio GPIO kirjutised + C täpne ajastus.
    send_channels() võtab float -1.0..1.0, set_raw_us() võtab otse µs.
    """

    def __init__(self, gpio_pin: int = PPM_GPIO):
        self.gpio_pin  = gpio_pin
        self.stats     = LinkStats()
        self.device    = None
        self.params    = {}
        # Turvaline vaikimisi: throttle min, arm off
        self._ch_us    = [CENTER_US, CENTER_US, MIN_US, CENTER_US] + [MIN_US] * (NUM_CH - 4)
        self._running  = False
        self._timing   = None

    # ── Kanalite seadmine ──────────────────────────────────────────────────

    def send_channels(self, channels: tuple):
        """Float -1.0..1.0 → µs."""
        for i in range(min(NUM_CH, len(channels))):
            v = max(-1.0, min(1.0, float(channels[i])))
            self._ch_us[i] = int(CENTER_US + v * (MAX_US - CENTER_US))

    def set_raw_us(self, us_values: list):
        """Otse µs väärtused (test lehelt)."""
        for i in range(min(NUM_CH, len(us_values))):
            self._ch_us[i] = max(MIN_US, min(MAX_US, int(us_values[i])))

    # ── No-op stubs ────────────────────────────────────────────────────────

    def ping(self): pass
    def bind(self): pass
    def write_param(self, index, value): pass
    def write_param_uint8(self, index, value): pass
    async def enumerate_params(self): pass

    def get_status(self) -> dict:
        return {"mode": "ppm", "gpio_pin": self.gpio_pin, "device": None,
                "link_quality": 0, "rssi_ant1": 0, "rssi_ant2": 0,
                "snr": 0, "tx_power_mw": 0}

    def get_params(self) -> list:
        return []

    # ── PPM loop ───────────────────────────────────────────────────────────

    def _set_rt(self):
        libc = ctypes.CDLL(ctypes.util.find_library("c"), use_errno=True)
        SCHED_FIFO = 1
        class sp(ctypes.Structure):
            _fields_ = [("sched_priority", ctypes.c_int)]
        ret = libc.sched_setscheduler(0, SCHED_FIFO, ctypes.byref(sp(99)))
        if ret == 0:
            log.info("PPM TX: SCHED_FIFO prio 99")
        # CPU3 affinity
        try:
            os.sched_setaffinity(0, {3})
            log.info("PPM TX: CPU3 affinity seatud")
        except Exception as e:
            log.warning(f"PPM TX: affinity viga: {e}")

    def _ppm_loop(self):
        import lgpio
        import time as _time
        timing = self._timing
        retry_delay = 1.0

        while self._running:
            h = None
            try:
                self._set_rt()
                h = lgpio.gpiochip_open(4)
                lgpio.gpio_claim_output(h, self.gpio_pin, 0)
                log.info(f"PPM TX: jookseb GPIO{self.gpio_pin} (Python lgpio + C timing)")

                wait = timing.busywait_us
                retry_delay = 1.0  # reset on success

                while self._running:
                    ch_us = self._ch_us[:]
                    used = sum(ch_us)
                    sync_gap = max(FRAME_US - used - PULSE_US, 3000)

                    for us in ch_us:
                        lgpio.gpio_write(h, self.gpio_pin, 1)
                        wait(ctypes.c_long(PULSE_US))
                        lgpio.gpio_write(h, self.gpio_pin, 0)
                        wait(ctypes.c_long(us - PULSE_US))

                    lgpio.gpio_write(h, self.gpio_pin, 1)
                    wait(ctypes.c_long(PULSE_US))
                    lgpio.gpio_write(h, self.gpio_pin, 0)
                    wait(ctypes.c_long(sync_gap))

            except Exception as e:
                log.error(f"PPM TX: krahh — {e}. Taaskäivitan {retry_delay:.1f}s pärast.")
                retry_delay = min(retry_delay * 2, 10.0)
            finally:
                if h is not None:
                    try:
                        lgpio.gpio_write(h, self.gpio_pin, 0)
                        lgpio.gpiochip_close(h)
                    except Exception:
                        pass
                if self._running:
                    _time.sleep(retry_delay)

        log.info("PPM TX: lõpetatud")

    async def start(self):
        try:
            self._timing = _load_timing_lib()
            log.info("PPM TX: C timing teek laetud (ppm_timing.so)")
        except Exception as e:
            log.error(f"PPM TX: timing teeki ei leitud: {e}")
            self._timing = None

        if not self._timing:
            log.error("PPM TX: ei saa käivituda ilma ppm_timing.so-ta")
            return

        self._running = True
        loop = asyncio.get_event_loop()
        try:
            await loop.run_in_executor(None, self._ppm_loop)
        except Exception as e:
            log.error(f"PPM TX: executor krahh — {e}")

    async def stop(self):
        self._running = False
