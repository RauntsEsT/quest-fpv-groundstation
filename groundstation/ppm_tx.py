"""
PPM RC signal generator for TBS Crossfire PPM input (pin 1).
Wiring: RPi GPIO18 (physical pin 12) → Crossfire PPM pad (pin 1)

PPM frame structure (positive polarity):
  [pulse][ch1_gap][pulse][ch2_gap]...[pulse][sync_gap]
  pulse = 300μs HIGH, gap encodes channel value
  total frame = 22.5ms (≈44Hz)
"""
import asyncio
import logging
import time
import threading
from dataclasses import dataclass

log = logging.getLogger("ppm_tx")

PPM_GPIO   = 18      # GPIO18 = physical pin 12
FRAME_US   = 22500   # 22.5ms frame period
PULSE_US   = 300     # 300μs high pulse per channel slot
MIN_US     = 1000    # channel min (1ms)
MAX_US     = 2000    # channel max (2ms)
CENTER_US  = 1500    # channel center (1.5ms)
NUM_CH     = 8       # standard PPM = 8 channels


@dataclass
class LinkStats:
    rssi_ant1: int    = 0
    rssi_ant2: int    = 0
    link_quality: int = 0
    snr: int          = 0
    tx_power_mw: int  = 0


class PPMTransmitter:
    """
    Generates hardware-timed PPM on a single GPIO pin.
    Drop-in replacement for CrossfireTX — same send_channels() interface.
    Uses busy-wait for microsecond precision (runs in a dedicated thread).
    """

    def __init__(self, gpio_pin: int = PPM_GPIO):
        self.gpio_pin  = gpio_pin
        self.stats     = LinkStats()
        self.device    = None
        self.params    = {}
        self._channels = [0.0] * NUM_CH
        self._running  = False
        self._h        = None

    # ── Channel interface (same as CrossfireTX) ────────────────────────────

    def send_channels(self, channels: tuple):
        """Accept float -1.0..1.0 per channel, same as CrossfireTX."""
        self._channels = list(channels[:NUM_CH]) + \
                         [0.0] * max(0, NUM_CH - len(channels))

    # ── No-op stubs for web_server compatibility ───────────────────────────

    def ping(self): pass
    def bind(self): pass
    def write_param(self, index, value): pass
    def write_param_uint8(self, index, value): pass

    async def enumerate_params(self): pass

    def get_status(self) -> dict:
        return {
            "mode":         "ppm",
            "gpio_pin":     self.gpio_pin,
            "device":       None,
            "link_quality": 0,
            "rssi_ant1":    0,
            "rssi_ant2":    0,
            "snr":          0,
            "tx_power_mw":  0,
        }

    def get_params(self) -> list:
        return []

    # ── PPM generation ─────────────────────────────────────────────────────

    @staticmethod
    def _busy_wait(us: int):
        """Pure busy-wait — only for short final segments (< 500μs)."""
        end = time.perf_counter() + us * 1e-6
        while time.perf_counter() < end:
            pass

    @staticmethod
    def _hybrid_wait(us: int):
        """
        Sleep for most of the duration, busy-wait only the last 400μs.
        Releases GIL during sleep → asyncio event loop can run.
        """
        BUSY_TAIL_US = 400
        if us > BUSY_TAIL_US:
            time.sleep((us - BUSY_TAIL_US) * 1e-6)
        end = time.perf_counter() + BUSY_TAIL_US * 1e-6
        while time.perf_counter() < end:
            pass

    def _ch_us(self, v: float) -> int:
        return int(CENTER_US + max(-1.0, min(1.0, v)) * (MAX_US - CENTER_US))

    def _ppm_loop(self):
        import lgpio
        h = lgpio.gpiochip_open(4)
        lgpio.gpio_claim_output(h, self.gpio_pin, 0)
        self._h = h
        log.info(f"PPM TX running on GPIO{self.gpio_pin} (pin {self.gpio_pin})")

        while self._running:
            ch_us = [self._ch_us(v) for v in self._channels]
            used  = sum(ch_us) + NUM_CH * PULSE_US + PULSE_US
            sync_gap = max(FRAME_US - used, 3000)

            for us in ch_us:
                lgpio.gpio_write(h, self.gpio_pin, 1)
                self._busy_wait(PULSE_US)          # 300μs — pure busy-wait
                lgpio.gpio_write(h, self.gpio_pin, 0)
                self._hybrid_wait(us - PULSE_US)   # ~1200μs — sleep + busy-wait tail

            # Sync pulse
            lgpio.gpio_write(h, self.gpio_pin, 1)
            self._busy_wait(PULSE_US)
            lgpio.gpio_write(h, self.gpio_pin, 0)
            self._hybrid_wait(sync_gap)            # ~7800μs — sleep + tail

        lgpio.gpio_write(h, self.gpio_pin, 0)
        lgpio.gpiochip_close(h)

    async def start(self):
        self._running = True
        loop = asyncio.get_event_loop()
        # Run PPM in thread — busy-wait needs dedicated CPU core
        await loop.run_in_executor(None, self._ppm_loop)

    async def stop(self):
        self._running = False
