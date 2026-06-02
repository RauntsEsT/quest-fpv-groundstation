#!/usr/bin/env python3
import asyncio
import logging
import os
import config_manager
from vrx_manager import create_vrx
from crossfire_tx import CrossfireTX
from ppm_tx import PPMTransmitter
from video_streamer import VideoStreamer
from controller_receiver import ControllerReceiver
from telemetry_manager import TelemetryManager
import web_server

logging.basicConfig(level=logging.INFO,
    format="%(asctime)s %(name)-20s %(levelname)s %(message)s")
log = logging.getLogger("main")

VIDEO_DEVICE  = os.getenv("VIDEO_DEVICE",  "/dev/video0")
VIDEO_PORT    = int(os.getenv("VIDEO_PORT",    "5006"))
TX_PORT       = os.getenv("TX_PORT",       "/dev/ttyAMA0")
TX_BAUD       = int(os.getenv("TX_BAUD",       "400000"))
UDP_CTRL_PORT = int(os.getenv("UDP_CTRL_PORT", "5005"))
WEB_PORT      = int(os.getenv("WEB_PORT",      "8080"))


async def main():
    cfg   = config_manager.load()
    vrx   = create_vrx(cfg["vrx"]["driver"], **cfg["vrx"].get("options", {}))
    saved_band = cfg["vrx"].get("band")
    saved_ch   = cfg["vrx"].get("channel")
    if saved_band and saved_ch:
        try:
            vrx.set_channel(saved_band, int(saved_ch))
            log.info(f"VRX restored: {saved_band}{saved_ch}")
        except Exception as e:
            log.warning(f"VRX channel restore failed: {e}")

    tx_cfg  = cfg.get("tx", {})
    tx_type = tx_cfg.get("type", "crsf")
    if tx_type == "ppm":
        gpio_pin = tx_cfg.get("gpio_pin", 18)
        tx = PPMTransmitter(gpio_pin)
        log.info(f"TX mode: PPM on GPIO{gpio_pin} (pin 12)")
    else:
        tx_port = tx_cfg.get("port", TX_PORT)
        tx_baud = tx_cfg.get("baud", TX_BAUD)
        tx = CrossfireTX(tx_port, tx_baud)
        log.info(f"TX mode: CRSF on {tx_port}@{tx_baud}")
    video = VideoStreamer(VIDEO_DEVICE, VIDEO_PORT)
    ctrl  = ControllerReceiver(UDP_CTRL_PORT, tx, cfg)
    telem = TelemetryManager(cfg["telemetry"]["drivers"],
                             {k: cfg["telemetry"].get(k, {})
                              for k in cfg["telemetry"]["drivers"]})

    log.info(f"Quest FPV Ground Station — VRX:{cfg['vrx']['driver']} "
             f"TX:{tx_type} TELEM:{cfg['telemetry']['drivers']}")
    await asyncio.gather(
        vrx.start(),
        tx.start(),
        ctrl.start(),
        video.start(),
        telem.start(),
        web_server.run(vrx, tx, video, telem, ctrl, port=WEB_PORT),
    )


if __name__ == "__main__":
    asyncio.run(main())
