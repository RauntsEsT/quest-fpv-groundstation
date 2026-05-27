#!/usr/bin/env python3
import asyncio
import logging
import os
from vrx_manager import create_vrx
from elrs_manager import ELRSManager
from video_streamer import VideoStreamer
from controller_receiver import ControllerReceiver
import web_server

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)-20s %(levelname)s %(message)s"
)
log = logging.getLogger("main")

# ── Konfiguratsioon ────────────────────────────────────────────────────────────
# VRX draiver: rtc6715 | button | foxeer_uart | walksnail | hdzero | dji_o3 | dummy
VRX_DRIVER    = os.getenv("VRX_DRIVER", "dummy")

VIDEO_DEVICE  = os.getenv("VIDEO_DEVICE", "/dev/video0")
VIDEO_PORT    = int(os.getenv("VIDEO_PORT", "5006"))
ELRS_PORT     = os.getenv("ELRS_PORT", "/dev/ttyAMA0")
ELRS_BAUD     = int(os.getenv("ELRS_BAUD", "420000"))
UDP_CTRL_PORT = int(os.getenv("UDP_CTRL_PORT", "5005"))
WEB_PORT      = int(os.getenv("WEB_PORT", "8080"))
# ──────────────────────────────────────────────────────────────────────────────


async def main():
    vrx   = create_vrx(VRX_DRIVER)
    elrs  = ELRSManager(ELRS_PORT, ELRS_BAUD)
    video = VideoStreamer(VIDEO_DEVICE, VIDEO_PORT)
    ctrl  = ControllerReceiver(UDP_CTRL_PORT, elrs)

    log.info(f"Quest FPV Ground Station starting — VRX: {VRX_DRIVER}")
    await asyncio.gather(
        vrx.start(),
        elrs.start(),
        ctrl.start(),
        video.start(),
        web_server.run(vrx, elrs, video, port=WEB_PORT),
    )


if __name__ == "__main__":
    asyncio.run(main())
