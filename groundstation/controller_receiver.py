import asyncio
import logging
from channel_mapper import ChannelMapper, PACKET_SIZE, LEGACY_SIZE

log = logging.getLogger("controller_receiver")


class ControllerReceiver:
    def __init__(self, port: int, elrs_sender, config: dict):
        self.port   = port
        self.elrs   = elrs_sender
        self.mapper = ChannelMapper(config)

    def update_config(self, cfg: dict):
        self.mapper.update_config(cfg)

    async def start(self):
        log.info(f"Listening for controller data on UDP port {self.port}")
        loop = asyncio.get_event_loop()
        transport, _ = await loop.create_datagram_endpoint(
            lambda: _UDPProtocol(self.elrs, self.mapper),
            local_addr=("0.0.0.0", self.port),
        )
        try:
            await asyncio.Future()
        finally:
            transport.close()


class _UDPProtocol(asyncio.DatagramProtocol):
    def __init__(self, elrs_sender, mapper: ChannelMapper):
        self.elrs   = elrs_sender
        self.mapper = mapper
        self._last_addr = None

    def datagram_received(self, data: bytes, addr):
        if len(data) not in (PACKET_SIZE, LEGACY_SIZE):
            return
        self._last_addr = addr
        channels = self.mapper.parse(data)
        if channels:
            self.elrs.send_channels(channels)
