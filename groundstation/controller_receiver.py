import asyncio
import struct
import logging

log = logging.getLogger("controller_receiver")

# Packet format from Quest app: 8 floats (roll, pitch, throttle, yaw, aux1..4), each -1.0 to 1.0
PACKET_FORMAT = "8f"
PACKET_SIZE = struct.calcsize(PACKET_FORMAT)


class ControllerReceiver:
    def __init__(self, port: int, elrs_sender):
        self.port = port
        self.elrs = elrs_sender

    async def start(self):
        log.info(f"Listening for controller data on UDP port {self.port}")
        loop = asyncio.get_event_loop()
        transport, _ = await loop.create_datagram_endpoint(
            lambda: _UDPProtocol(self.elrs),
            local_addr=("0.0.0.0", self.port),
        )
        try:
            await asyncio.Future()
        finally:
            transport.close()


class _UDPProtocol(asyncio.DatagramProtocol):
    def __init__(self, elrs_sender):
        self.elrs = elrs_sender

    def datagram_received(self, data: bytes, addr):
        if len(data) != PACKET_SIZE:
            return
        channels = struct.unpack(PACKET_FORMAT, data)
        self.elrs.send_channels(channels)
