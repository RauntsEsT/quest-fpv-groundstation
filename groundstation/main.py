#!/usr/bin/env python3
import asyncio
import logging
from foxeer_vrx import FoxeerVRX
from elrs_manager import ELRSManager
from video_streamer import VideoStreamer
from controller_receiver import ControllerReceiver
import web_server

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)-20s %(levelname)s %(message)s"
)
log = logging.getLogger("main")

VIDEO_DEVICE  = "/dev/video0"
VIDEO_PORT    = 5006
ELRS_PORT     = "/dev/ttyAMA0"
ELRS_BAUD     = 420000
UDP_CTRL_PORT = 5005
WEB_PORT      = 8080


async def main():
    vrx     = FoxeerVRX(VIDEO_DEVICE)
    elrs    = ELRSManager(ELRS_PORT, ELRS_BAUD)
    video   = VideoStreamer(VIDEO_DEVICE, VIDEO_PORT)
    ctrl    = ControllerReceiver(UDP_CTRL_PORT, elrs)

    log.info("Quest FPV Ground Station starting")
    await asyncio.gather(
        vrx.start(),
        elrs.start(),
        ctrl.start(),
        video.start(),
        web_server.run(vrx, elrs, video, port=WEB_PORT),
    )


if __name__ == "__main__":
    asyncio.run(main())
