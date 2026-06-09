#!/usr/bin/env python3
import asyncio
import logging
import os
import signal
import config_manager
from vrx_manager import create_vrx
from crossfire_tx import CrossfireTX
from ppm_tx import PPMTransmitter
from video_streamer import VideoStreamer
from controller_receiver import ControllerReceiver, FAILSAFE_CHANNELS
from telemetry_manager import TelemetryManager
import web_server

logging.basicConfig(level=logging.INFO,
    format='%(asctime)s %(name)-20s %(levelname)s %(message)s')
log = logging.getLogger('main')

VIDEO_DEVICE  = os.getenv('VIDEO_DEVICE',  '/dev/video0')
VIDEO_PORT    = int(os.getenv('VIDEO_PORT',    '5006'))
TX_PORT       = os.getenv('TX_PORT',       '/dev/ttyAMA0')
TX_BAUD       = int(os.getenv('TX_BAUD',       '400000'))
UDP_CTRL_PORT = int(os.getenv('UDP_CTRL_PORT', '5005'))
WEB_PORT      = int(os.getenv('WEB_PORT',      '8080'))


async def _restart_critical(name, coro_factory, delay=1.0):
    while True:
        try:
            await coro_factory()
        except asyncio.CancelledError:
            raise
        except Exception as e:
            log.error(f'{name}: krahh — {e}. Restardin {delay:.1f}s parast.')
            await asyncio.sleep(delay)


async def _log_crash(name, coro_factory):
    try:
        await coro_factory()
    except asyncio.CancelledError:
        raise
    except Exception as e:
        log.error(f'{name}: krahh (mittekriitiline) — {e}')


async def main():
    cfg   = config_manager.load()
    vrx   = create_vrx(cfg['vrx']['driver'], **cfg['vrx'].get('options', {}))
    saved_band = cfg['vrx'].get('band')
    saved_ch   = cfg['vrx'].get('channel')
    if saved_band and saved_ch:
        try:
            vrx.set_channel(saved_band, int(saved_ch))
            log.info(f'VRX restored: {saved_band}{saved_ch}')
        except Exception as e:
            log.warning(f'VRX channel restore failed: {e}')

    tx_cfg  = cfg.get('tx', {})
    tx_type = tx_cfg.get('type', 'crsf')
    tx_port = tx_cfg.get('port', TX_PORT)
    tx_baud = tx_cfg.get('baud', TX_BAUD)

    if tx_type == 'ppm':
        gpio_pin = tx_cfg.get('gpio_pin', 18)
        tx = PPMTransmitter(gpio_pin)
        log.info(f'TX: PPM GPIO{gpio_pin} (puhas PPM, CRSF keelatud)')
    else:
        tx = CrossfireTX(tx_port, tx_baud)
        log.info(f'TX mode: CRSF on {tx_port}@{tx_baud}')

    video = VideoStreamer(VIDEO_DEVICE, VIDEO_PORT)
    ctrl  = ControllerReceiver(UDP_CTRL_PORT, tx, cfg)
    telem = TelemetryManager(cfg['telemetry']['drivers'],
                             {k: cfg['telemetry'].get(k, {})
                              for k in cfg['telemetry']['drivers']})

    log.info(f'Quest FPV Ground Station — VRX:{cfg["vrx"]["driver"]} '
             f'TX:{tx_type} TELEM:{cfg["telemetry"]["drivers"]}')

    loop = asyncio.get_running_loop()

    def _on_signal(sig_name):
        log.warning(f'Signal {sig_name} — saadan failsafe ja sulgun')
        tx.send_channels(FAILSAFE_CHANNELS)
        for t in asyncio.all_tasks(loop):
            t.cancel()

    loop.add_signal_handler(signal.SIGTERM, lambda: _on_signal('SIGTERM'))
    loop.add_signal_handler(signal.SIGINT,  lambda: _on_signal('SIGINT'))

    await asyncio.gather(
        _restart_critical('tx',   tx.start),
        _restart_critical('ctrl', ctrl.start),
        _log_crash('vrx',   vrx.start),
        _log_crash('video', video.start),
        _log_crash('telem', telem.start),
        _log_crash('web',   lambda: web_server.run(vrx, tx, video, telem, ctrl, port=WEB_PORT)),
        return_exceptions=True,
    )


if __name__ == '__main__':
    asyncio.run(main())
