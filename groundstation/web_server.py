import asyncio
import json
import logging
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from fastapi import Request
import uvicorn
import config_manager

log = logging.getLogger("web_server")
app = FastAPI(title="Quest FPV Ground Station")


def create_app(vrx, tx, video_streamer, telem=None, ctrl=None):
    _last_channels = [0.0] * 16

    @app.get("/", response_class=HTMLResponse)
    async def index():
        with open("static/index.html") as f:
            return f.read()

    # ── System status ──────────────────────────────────────────────────────

    @app.get("/api/status")
    async def get_status():
        return {
            "vrx": {
                "band":          vrx.status.band,
                "channel":       vrx.status.channel,
                "frequency_mhz": vrx.status.frequency_mhz,
                "rssi_a":        vrx.status.rssi_a,
                "rssi_b":        vrx.status.rssi_b,
                "driver":        vrx.status.driver,
                "connected":     vrx.status.connected,
            },
            "tx": tx.get_status(),
            "video_port":  video_streamer.port,
            "telemetry":   telem.get_dict() if telem else {},
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
        existing = config_manager.load()
        cfg.setdefault("vrx", {})["driver"] = existing["vrx"]["driver"]
        config_manager.save(cfg)
        if ctrl:
            ctrl.update_config(cfg)
        return {"ok": True}

    # ── VRX control ────────────────────────────────────────────────────────

    @app.post("/api/vrx/channel")
    async def set_channel(band: str, channel: int):
        vrx.set_channel(band, channel)
        cfg = config_manager.load()
        cfg.setdefault("vrx", {})["band"]    = band
        cfg["vrx"]["channel"] = channel
        config_manager.save(cfg)
        return {"ok": True, "frequency_mhz": vrx.status.frequency_mhz}

    @app.post("/api/vrx/frequency")
    async def set_frequency(freq_mhz: int):
        vrx.set_frequency(freq_mhz)
        return {"ok": True, "band": vrx.status.band, "channel": vrx.status.channel}

    @app.get("/api/vrx/channels")
    async def get_channels():
        return vrx.get_all_channels()

    # ── TX (Crossfire) control ─────────────────────────────────────────────

    @app.get("/api/tx/status")
    async def get_tx_status():
        return tx.get_status()

    @app.get("/api/tx/params")
    async def get_tx_params():
        return tx.get_params()

    @app.post("/api/tx/params/{index}")
    async def write_tx_param(index: int, request: Request):
        """
        Write a TX parameter.
        Body: {"value": <int>}  for UINT8 / TEXT_SELECTION
              {"raw": [b0, b1, …]}  for raw bytes
        """
        body = await request.json()
        if "raw" in body:
            tx.write_param(index, bytes(body["raw"]))
        elif "value" in body:
            tx.write_param_uint8(index, int(body["value"]))
        else:
            raise HTTPException(400, "body must contain 'value' or 'raw'")
        return {"ok": True}

    @app.post("/api/tx/scan")
    async def scan_tx_params():
        """Re-ping TX module and enumerate all parameters (takes ~5 s)."""
        asyncio.create_task(tx.enumerate_params())
        return {"ok": True, "message": "Scanning TX parameters…"}

    @app.post("/api/tx/bind")
    async def tx_bind():
        """
        Enter binding mode on the TX module.
        Put the drone receiver into bind mode first (power on while pressing bind button).
        """
        tx.bind()
        return {"ok": True, "message": "Bind command sent"}

    @app.post("/api/tx/ping")
    async def tx_ping():
        tx.ping()
        return {"ok": True}

    # ── WebSocket: real-time status ────────────────────────────────────────

    @app.websocket("/ws/status")
    async def websocket_status(ws: WebSocket):
        await ws.accept()
        try:
            while True:
                msg = {
                    "rssi_a":   vrx.status.rssi_a,
                    "rssi_b":   vrx.status.rssi_b,
                    "band":     vrx.status.band,
                    "channel":  vrx.status.channel,
                    "freq":     vrx.status.frequency_mhz,
                    "lq":       tx.stats.link_quality,
                    "snr":      tx.stats.snr,
                    "txpwr":    tx.stats.tx_power_mw,
                    "rssi1":    tx.stats.rssi_ant1,
                    "rssi2":    tx.stats.rssi_ant2,
                    "telem":    telem.get_dict() if telem else {},
                    "channels": list(_last_channels),
                }
                await ws.send_text(json.dumps(msg))
                await asyncio.sleep(0.2)
        except WebSocketDisconnect:
            pass

    # ── WebSocket: controller input ────────────────────────────────────────

    @app.websocket("/ws/control")
    async def websocket_control(ws: WebSocket):
        await ws.accept()
        log.info("Web controller connected")
        try:
            while True:
                text = await ws.receive_text()
                if not ctrl or not tx:
                    continue
                msg     = json.loads(text)
                axes    = msg.get("axes", [0.0, 0.0, 0.0, 0.0])
                buttons = msg.get("buttons", {})
                channels = ctrl.mapper.map_web_input(axes, buttons)
                tx.send_channels(channels)
                _last_channels[:] = channels
        except WebSocketDisconnect:
            log.info("Web controller disconnected")

    # ── MJPEG video stream ─────────────────────────────────────────────────

    @app.get("/video")
    async def video_feed():
        from fastapi.responses import StreamingResponse
        BOUNDARY = b"--frame\r\nContent-Type: image/jpeg\r\n\r\n"

        async def generate():
            q = video_streamer.subscribe()
            try:
                while True:
                    try:
                        frame = await asyncio.wait_for(q.get(), timeout=5.0)
                        yield BOUNDARY + frame + b"\r\n"
                    except asyncio.TimeoutError:
                        break
            finally:
                video_streamer.unsubscribe(q)

        return StreamingResponse(
            generate(), media_type="multipart/x-mixed-replace; boundary=frame")

    app.mount("/static", StaticFiles(directory="static"), name="static")
    return app


async def run(vrx, tx, video_streamer, telem=None, ctrl=None,
              host="0.0.0.0", port=8080):
    create_app(vrx, tx, video_streamer, telem, ctrl)
    config = uvicorn.Config(app, host=host, port=port, log_level="warning")
    server = uvicorn.Server(config)
    log.info(f"Web UI: http://{host}:{port}")
    await server.serve()
