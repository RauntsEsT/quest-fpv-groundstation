import asyncio
import logging
from vrx_base import VRXBase
from vrx_bands import BANDS_5800, BANDS_1200

log = logging.getLogger("vrx_button")

PIN_BTN_UP    = 6   # GPIO6  → transistor → VRX UP button
PIN_BTN_DOWN  = 13  # GPIO13 → transistor → VRX DOWN button
PIN_BTN_ENTER = 19  # GPIO19 → transistor → VRX ENTER button
BTN_PULSE_MS  = 100 # milliseconds


class ButtonVRX(VRXBase):
    """
    Generic analog VRX driver using button emulation via GPIO transistors.
    Works with any VRX that has UP/DOWN/ENTER buttons (Foxeer, Eachine, etc).

    Wiring (per button):
        RPi GPIO → 1kΩ → NPN transistor base (BC547/2N2222)
        Transistor collector → VRX button pad
        Transistor emitter   → GND
    """

    def __init__(self):
        super().__init__()
        self.status.driver = "button_emulation"
        self._gpio = None

    def _init_gpio(self):
        try:
            import RPi.GPIO as GPIO
            GPIO.setmode(GPIO.BCM)
            for pin in (PIN_BTN_UP, PIN_BTN_DOWN, PIN_BTN_ENTER):
                GPIO.setup(pin, GPIO.OUT, initial=GPIO.LOW)
            self._gpio = GPIO
            log.info("Button emulation GPIO init OK")
        except ImportError:
            log.warning("RPi.GPIO not available — button emulation disabled")

    async def _press(self, pin: int):
        if not self._gpio:
            return
        self._gpio.output(pin, self._gpio.HIGH)
        await asyncio.sleep(BTN_PULSE_MS / 1000)
        self._gpio.output(pin, self._gpio.LOW)
        await asyncio.sleep(0.05)

    def set_channel(self, band: str, channel: int):
        # Store target — actual button presses happen async
        band = band.upper()
        all_bands = {**BANDS_5800, **BANDS_1200}
        if band not in all_bands or not 1 <= channel <= 8:
            raise ValueError(f"Invalid band/channel: {band}{channel}")
        self.status.band = band
        self.status.channel = channel
        self.status.frequency_mhz = all_bands[band][channel - 1]
        log.info(f"Button VRX target: {band}{channel} ({self.status.frequency_mhz} MHz)"
                 " — change manually or via button sequence")

    async def press_up(self):
        await self._press(PIN_BTN_UP)

    async def press_down(self):
        await self._press(PIN_BTN_DOWN)

    async def press_enter(self):
        await self._press(PIN_BTN_ENTER)

    async def start(self):
        self._init_gpio()
        self.status.connected = True
        log.info("Button emulation VRX ready")
        while True:
            await asyncio.sleep(5)

    async def stop(self):
        if self._gpio:
            self._gpio.cleanup()
