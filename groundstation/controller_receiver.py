import asyncio
import logging
import time
from channel_mapper import ChannelMapper, PACKET_SIZE, LEGACY_SIZE

log = logging.getLogger("controller_receiver")

FAILSAFE_TIMEOUT  = 1.0
FAILSAFE_CHANNELS = tuple([0.0, 0.0, 0.0, -1.0] + [-1.0] * 12)  # ch3=yaw center, ch4=throttle min


class ControllerReceiver:
    def __init__(self, port: int, elrs_sender, config: dict):
        self.port   = port
        self.elrs   = elrs_sender
        self.mapper = ChannelMapper(config)
        self._last_rx     = 0.0
        self._in_failsafe = True

    def update_config(self, cfg: dict):
        self.mapper.update_config(cfg)

    async def _failsafe_watchdog(self):
        while True:
            await asyncio.sleep(0.2)
            if time.monotonic() - self._last_rx > FAILSAFE_TIMEOUT:
                if not self._in_failsafe:
                    log.warning("Kontroller lahutus - failsafe aktiivne (throttle min)")
                    self._in_failsafe = True
                self.elrs.send_channels(FAILSAFE_CHANNELS)

    async def start(self):
        log.info(f"Listening for controller data on UDP port {self.port}")
        loop = asyncio.get_event_loop()
        transport, _ = await loop.create_datagram_endpoint(
            lambda: _UDPProtocol(self.elrs, self.mapper, self),
            local_addr=("0.0.0.0", self.port),
        )
        asyncio.ensure_future(self._failsafe_watchdog())
        try:
            await asyncio.Future()
        finally:
            transport.close()


class _UDPProtocol(asyncio.DatagramProtocol):
    def __init__(self, elrs_sender, mapper: ChannelMapper, receiver: ControllerReceiver):
        self.elrs     = elrs_sender
        self.mapper   = mapper
        self.receiver = receiver

    def datagram_received(self, data: bytes, addr):
        if len(data) not in (PACKET_SIZE, LEGACY_SIZE):
            return
        if self.receiver._in_failsafe:
            log.info("Kontroller uhendas")
            self.receiver._in_failsafe = False
        self.receiver._last_rx = time.monotonic()
        channels = self.mapper.parse(data)
        if channels:
            self.elrs.send_channels(channels)
