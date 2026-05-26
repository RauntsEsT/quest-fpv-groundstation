#!/usr/bin/env python3
"""
Ground station middleware for Quest FPV system.
Receives controller data via UDP from Meta Quest app,
forwards CRSF packets to ELRS TX over UART,
and streams video from USB capture card to Quest.
"""

import asyncio
import logging
from controller_receiver import ControllerReceiver
from elrs_sender import ELRSSender
from video_streamer import VideoStreamer

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
log = logging.getLogger("groundstation")

UDP_PORT = 5005
ELRS_UART_PORT = "/dev/ttyUSB0"
ELRS_BAUD = 420000
VIDEO_DEVICE = "/dev/video0"
VIDEO_STREAM_PORT = 5006


async def main():
    elrs = ELRSSender(ELRS_UART_PORT, ELRS_BAUD)
    video = VideoStreamer(VIDEO_DEVICE, VIDEO_STREAM_PORT)
    receiver = ControllerReceiver(UDP_PORT, elrs)

    log.info("Starting Quest FPV Ground Station")
    await asyncio.gather(
        receiver.start(),
        video.start(),
    )


if __name__ == "__main__":
    asyncio.run(main())
