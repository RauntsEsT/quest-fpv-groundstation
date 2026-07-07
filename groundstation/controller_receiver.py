import asyncio
import logging
import time
from channel_mapper import ChannelMapper, PACKET_SIZE, LEGACY_SIZE

log = logging.getLogger("controller_receiver")

FAILSAFE_TIMEOUT  = 1.0
FAILSAFE_CHANNELS = tuple([0.0, 0.0, 0.0, -1.0] + [-1.0] * 12)  # ch3=yaw center(PPM CH3->INAV YAW), ch4=throttle min(PPM CH4->INAV THR)


class ControllerReceiver:
    def __init__(self, port: int, elrs_sender, config: dict):
        self.port   = port
        self.elrs   = elrs_sender
        self.mapper = ChannelMapper(config)
        self._last_rx     = 0.0
        self._in_failsafe = True
        self._test_mode   = False  # kui True, UDP sisend ignoreeritakse

    def update_config(self, cfg: dict):
        self.mapper.update_config(cfg)

    def set_test_mode(self, enabled: bool):
        self._test_mode = enabled
        if enabled:
            log.info("Test mode AKTIIVNE — UDP controller sisend blokeeritud")
        else:
            log.info("Test mode INAKTIIVNE — UDP controller lubatud")

    async def _failsafe_watchdog(self):
        while True:
            await asyncio.sleep(0.2)
            try:
                if time.monotonic() - self._last_rx > FAILSAFE_TIMEOUT:
                    if not self._in_failsafe:
                        log.warning("Kontroller lahutus - failsafe aktiivne (throttle min)")
                        self._in_failsafe = True
                    self.elrs.send_channels(FAILSAFE_CHANNELS)
            except Exception as e:
                log.error(f"Failsafe watchdog viga: {e}")

    async def start(self):
        log.info(f"Listening for controller data on UDP port {self.port}")
        loop = asyncio.get_event_loop()
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("0.0.0.0", self.port))
        transport, _ = await loop.create_datagram_endpoint(
            lambda: _UDPProtocol(self.elrs, self.mapper, self),
            sock=sock,
        )
        wdog = asyncio.create_task(self._failsafe_watchdog())
        wdog.add_done_callback(
            lambda t: log.critical(f"FAILSAFE WATCHDOG SURI: {t.exception()}")
            if not t.cancelled() and t.exception() else None
        )
        try:
            await asyncio.Future()
        finally:
            transport.close()
            wdog.cancel()

    def web_controller_disconnect(self):
        """Kutsuda kui web WebSocket controller lahutab — aktiveerib failsafe kohe."""
        self._in_failsafe = True
        self._last_rx = 0.0


class _UDPProtocol(asyncio.DatagramProtocol):
    def __init__(self, elrs_sender, mapper: ChannelMapper, receiver: ControllerReceiver):
        self.elrs     = elrs_sender
        self.mapper   = mapper
        self.receiver = receiver

    def datagram_received(self, data: bytes, addr):
        if len(data) not in (PACKET_SIZE, LEGACY_SIZE):
            return
        if self.receiver._test_mode:
            return  # test mode — ignoreeri UDP sisendit
        if self.receiver._in_failsafe:
            log.info("Kontroller uhendas")
            self.receiver._in_failsafe = False
        self.receiver._last_rx = time.monotonic()
        channels = self.mapper.parse(data)
        if channels:
            self.elrs.send_channels(channels)

