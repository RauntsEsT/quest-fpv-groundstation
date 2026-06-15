"""
PPM RC signal generator — RP1 otsene mmap GPIO (RPi5 jitter-free).

Vana lahendus: Python lgpio.gpio_write() kandis 2-4ms RP1 latentsi.
Uus lahendus: rp1_ppm_run() — terve PPM loop C-s, kirjutab RP1 registreid otse mmap kaudu.
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
    lib.busywait_until_ns.restype  = None
    lib.busywait_until_ns.argtypes = [ctypes.c_long]
    lib.monotonic_ns.restype  = ctypes.c_long
    lib.monotonic_ns.argtypes = []
    lib.rp1_gpio_mmap_init.restype  = ctypes.c_int
    lib.rp1_gpio_mmap_init.argtypes = [ctypes.c_int]
    lib.rp1_gpio_mmap_close.restype  = None
    lib.rp1_gpio_mmap_close.argtypes = []
    lib.rp1_ppm_run.restype  = ctypes.c_long
    lib.rp1_ppm_run.argtypes = [
        ctypes.POINTER(ctypes.c_int),
        ctypes.POINTER(ctypes.c_int),
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.POINTER(ctypes.c_double),
    ]
    return lib


class PPMTransmitter:
    """PPM generaator: rp1_ppm_run() otse RP1 mmap GPIO kaudu."""

    def __init__(self, gpio_pin: int = PPM_GPIO):
        self.gpio_pin  = gpio_pin
        self.stats     = LinkStats()
        self.device    = None
        self.params    = {}
        self._ch_us    = [CENTER_US, CENTER_US, CENTER_US, MIN_US] + [MIN_US] * (NUM_CH - 4)
        self._ch_us_c  = (ctypes.c_int * NUM_CH)(*self._ch_us)
        self._running_c = ctypes.c_int(0)
        self._jitter_c = (ctypes.c_double * 4)(0.0, 0.0, 0.0, 0.0)
        self._running  = False
        self._timing   = None

    def send_channels(self, channels: tuple):
        for i in range(min(NUM_CH, len(channels))):
            v = max(-1.0, min(1.0, float(channels[i])))
            val = int(CENTER_US + v * (MAX_US - CENTER_US))
            self._ch_us_c[i] = val
            self._ch_us[i]   = val

    def set_raw_us(self, us_values: list):
        for i in range(min(NUM_CH, len(us_values))):
            val = max(MIN_US, min(MAX_US, int(us_values[i])))
            self._ch_us_c[i] = val
            self._ch_us[i]   = val

    def ping(self): pass
    def bind(self): pass
    def write_param(self, index, value): pass
    def write_param_uint8(self, index, value): pass
    async def enumerate_params(self): pass

    def get_status(self) -> dict:
        return {"mode": "ppm", "gpio_pin": self.gpio_pin, "device": None,
                "link_quality": self.stats.link_quality,
                "rssi_ant1": self.stats.rssi_ant1,
                "rssi_ant2": self.stats.rssi_ant2,
                "snr": self.stats.snr,
                "tx_power_mw": self.stats.tx_power_mw}

    def get_jitter(self) -> dict:
        j = self._jitter_c
        return {
            "frames":     int(j[3]),
            "avg_err_us": round(j[0], 2),
            "max_err_us": round(j[1], 2),
            "stddev_us":  round(j[2], 2),
        }

    def reset_jitter(self):
        for i in range(4):
            self._jitter_c[i] = 0.0

    def get_params(self) -> list:
        return []

    def _set_rt(self):
        libc = ctypes.CDLL(ctypes.util.find_library("c"), use_errno=True)
        SCHED_FIFO = 1
        class sp(ctypes.Structure):
            _fields_ = [("sched_priority", ctypes.c_int)]
        ret = libc.sched_setscheduler(0, SCHED_FIFO, ctypes.byref(sp(99)))
        if ret == 0:
            log.info("PPM TX: SCHED_FIFO prio 99")
        try:
            os.sched_setaffinity(0, {3})
            log.info("PPM TX: CPU3 affinity seatud")
        except Exception as e:
            log.warning(f"PPM TX: affinity viga: {e}")

    def _ppm_loop(self):
        import lgpio
        import time as _time
        retry_delay = 1.0

        while self._running:
            h = None
            mmap_ok = False
            try:
                self._set_rt()
                h = lgpio.gpiochip_open(4)
                lgpio.gpio_claim_output(h, self.gpio_pin, 0)

                ret = self._timing.rp1_gpio_mmap_init(self.gpio_pin)
                if ret == 0:
                    mmap_ok = True
                    log.info(f"PPM TX: RP1 mmap GPIO aktiivseks (jitter-free) GPIO{self.gpio_pin}")
                else:
                    log.warning("PPM TX: RP1 mmap init ebaonnestus — lgpio fallback")

                retry_delay = 1.0

                if mmap_ok:
                    self._running_c.value = 1
                    for i, v in enumerate(self._ch_us):
                        self._ch_us_c[i] = v
                    log.info("PPM TX: rp1_ppm_run() kaudu GPIO18")
                    self._timing.rp1_ppm_run(
                        ctypes.byref(self._running_c),
                        self._ch_us_c,
                        ctypes.c_int(NUM_CH),
                        ctypes.c_int(FRAME_US),
                        ctypes.c_int(PULSE_US),
                        self._jitter_c,
                    )
                    log.info("PPM TX: rp1_ppm_run() lopetatud")
                else:
                    # Fallback: lgpio loop
                    timing = self._timing
                    wait_until = timing.busywait_until_ns
                    now_ns = timing.monotonic_ns
                    log.info("PPM TX: lgpio fallback loop")
                    while self._running and self._running_c.value:
                        ch_us = self._ch_us[:]
                        sync_gap = max(FRAME_US - sum(ch_us) - PULSE_US, 3000)
                        t = now_ns()
                        for us in ch_us:
                            lgpio.gpio_write(h, self.gpio_pin, 1)
                            t += PULSE_US * 1000
                            wait_until(ctypes.c_long(t))
                            lgpio.gpio_write(h, self.gpio_pin, 0)
                            t += (us - PULSE_US) * 1000
                            wait_until(ctypes.c_long(t))
                        lgpio.gpio_write(h, self.gpio_pin, 1)
                        t += PULSE_US * 1000
                        wait_until(ctypes.c_long(t))
                        lgpio.gpio_write(h, self.gpio_pin, 0)
                        t += sync_gap * 1000
                        wait_until(ctypes.c_long(t))

            except Exception as e:
                log.error(f"PPM TX: krahh — {e}. Taaskäivitan {retry_delay:.1f}s.")
                retry_delay = min(retry_delay * 2, 10.0)
            finally:
                if mmap_ok:
                    self._timing.rp1_gpio_mmap_close()
                if h is not None:
                    try:
                        lgpio.gpio_write(h, self.gpio_pin, 0)
                        lgpio.gpiochip_close(h)
                    except Exception:
                        pass
                if self._running:
                    _time.sleep(retry_delay)

        log.info("PPM TX: lopetatud")

    async def start(self):
        try:
            self._timing = _load_timing_lib()
            log.info("PPM TX: C timing teek laetud (ppm_timing.so)")
        except Exception as e:
            log.error(f"PPM TX: timing teeki ei leitud: {e}")
            self._timing = None
            return

        self._running = True
        self._running_c.value = 1
        loop = asyncio.get_event_loop()
        try:
            await loop.run_in_executor(None, self._ppm_loop)
        except Exception as e:
            log.error(f"PPM TX: executor krahh — {e}")

    async def stop(self):
        self._running = False
        self._running_c.value = 0
