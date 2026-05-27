import asyncio
import json
import logging
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from fastapi import Request
import uvicorn
import config_manager

log = logging.getLogger("web_server")
app = FastAPI(title="Quest FPV Ground Station")


def create_app(vrx, elrs, video_streamer, telem=None, ctrl=None):
    _last_channels = [0.0] * 16


    @app.get("/", response_class=HTMLResponse)
    async def index():
        with open("static/index.html") as f:
            return f.read()

    @app.get("/api/status")
    async def get_status():
        return {
            "vrx": {
                "band": vrx.status.band, "channel": vrx.status.channel,
                "frequency_mhz": vrx.status.frequency_mhz,
                "rssi_a": vrx.status.rssi_a, "rssi_b": vrx.status.rssi_b,
                "driver": vrx.status.driver, "connected": vrx.status.connected,
            },
            "elrs": {
                "rssi_ant1": elrs.stats.rssi_ant1, "rssi_ant2": elrs.stats.rssi_ant2,
                "link_quality": elrs.stats.link_quality,
                "snr": elrs.stats.snr, "tx_power_mw": elrs.stats.tx_power_mw,
            },
            "video_port": video_streamer.port,
            "telemetry": telem.get_dict() if telem else {},
        }

    @app.get("/api/telemetry")
    async def get_telemetry():
        return telem.get_dict() if telem else {}

    @app.get("/api/config")
    async def get_config():
        return config_manager.load()

    @app.post("/api/config")
    async def post_config(request: Request):
        cfg = await request.json()
        config_manager.save(cfg)
        if ctrl:
            ctrl.update_config(cfg)
        return {"ok": True}

    @app.post("/api/vrx/channel")
    async def set_channel(band: str, channel: int):
        vrx.set_channel(band, channel)
        return {"ok": True, "frequency_mhz": vrx.status.frequency_mhz}

    @app.post("/api/vrx/frequency")
    async def set_frequency(freq_mhz: int):
        vrx.set_frequency(freq_mhz)
        return {"ok": True, "band": vrx.status.band, "channel": vrx.status.channel}

    @app.get("/api/vrx/channels")
    async def get_channels():
        return vrx.get_all_channels()

    @app.websocket("/ws/status")
    async def websocket_status(ws: WebSocket):
        await ws.accept()
        try:
            while True:
                msg = {
                    "rssi_a": vrx.status.rssi_a, "rssi_b": vrx.status.rssi_b,
                    "lq": elrs.stats.link_quality, "snr": elrs.stats.snr,
                    "txpwr": elrs.stats.tx_power_mw,
                    "band": vrx.status.band, "channel": vrx.status.channel,
                    "freq": vrx.status.frequency_mhz,
                    "telem": telem.get_dict() if telem else {},
                    "channels": list(_last_channels),
                }
                await ws.send_text(json.dumps(msg))
                await asyncio.sleep(0.2)
        except WebSocketDisconnect:
            pass


    @app.websocket("/ws/control")
    async def websocket_control(ws: WebSocket):
        await ws.accept()
        log.info("Web controller connected")
        try:
            while True:
                text = await ws.receive_text()
                if not ctrl or not elrs:
                    continue
                msg = json.loads(text)
                axes = msg.get("axes", [0.0, 0.0, 0.0, 0.0])
                buttons = msg.get("buttons", {})
                channels = ctrl.mapper.map_web_input(axes, buttons)
                elrs.send_channels(channels)
                _last_channels[:] = channels
        except WebSocketDisconnect:
            log.info("Web controller disconnected")

    app.mount("/static", StaticFiles(directory="static"), name="static")
    return app


async def run(vrx, elrs, video_streamer, telem=None, ctrl=None,
              host="0.0.0.0", port=8080):
    create_app(vrx, elrs, video_streamer, telem, ctrl)
    config = uvicorn.Config(app, host=host, port=port, log_level="warning")
    server = uvicorn.Server(config)
    log.info(f"Web UI: http://{host}:{port}")
    await server.serve()
