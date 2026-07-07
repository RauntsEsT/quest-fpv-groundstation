import asyncio
import time
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
    _test_locked = False

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

    @app.get("/api/tx/channels")
    async def get_tx_channels():
        return {"ch_us": tx._ch_us[:] if hasattr(tx, "_ch_us") else []}

    @app.get("/api/tx/jitter")
    async def get_tx_jitter():
        if hasattr(tx, 'get_jitter'):
            return tx.get_jitter()
        return {}

    @app.post("/api/tx/jitter/reset")
    async def reset_tx_jitter():
        if hasattr(tx, 'reset_jitter'):
            tx.reset_jitter()
        return {"ok": True}

    @app.post("/api/test/lock")
    async def test_lock():
        nonlocal _test_locked
        _test_locked = True
        if ctrl:
            ctrl.set_test_mode(True)
        log.info("Test mode LUKUS — web + UDP controller blokeeritud")
        return {"ok": True, "locked": True}

    @app.post("/api/test/unlock")
    async def test_unlock():
        nonlocal _test_locked
        _test_locked = False
        if ctrl:
            ctrl.set_test_mode(False)
        log.info("Test mode AVATUD — web + UDP controller lubatud")
        return {"ok": True, "locked": False}

    @app.get("/api/test/lock")
    async def test_lock_status():
        return {"locked": _test_locked}

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
                if _test_locked:
                    continue  # test mode aktiivne — ignoreeri web controller sisendit
                channels = ctrl.mapper.map_web_input(axes, buttons)
                ctrl._last_rx = time.monotonic()
                ctrl._in_failsafe = False
                tx.send_channels(channels)
                _last_channels[:] = channels
        except WebSocketDisconnect:
            log.info("Web controller disconnected — failsafe aktiivseks")
            if ctrl:
                ctrl.web_controller_disconnect()

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
                    except asyncio.TimeoutError:  # keepalive handles placeholder
                        continue
            finally:
                video_streamer.unsubscribe(q)

        return StreamingResponse(
            generate(), media_type="multipart/x-mixed-replace; boundary=frame")


    @app.websocket("/ws/video")
    async def websocket_video(ws: WebSocket):
        await ws.accept()
        q = video_streamer.subscribe()
        try:
            while True:
                try:
                    frame = await asyncio.wait_for(q.get(), timeout=5.0)
                    await ws.send_bytes(frame)
                except asyncio.TimeoutError:
                    continue
                except Exception:
                    break
        finally:
            video_streamer.unsubscribe(q)

    SAFE_CH_US = [1500, 1500, 1500, 1000, 1000, 1000, 1000, 1000]

    @app.post("/api/test/set")
    async def test_set_channels(request: Request):
        body = await request.json()
        ch = body.get("channels", SAFE_CH_US)
        if hasattr(tx, "set_raw_us"):
            tx.set_raw_us(ch)
        if ctrl:
            ctrl._last_rx = time.monotonic()
            ctrl._in_failsafe = False
        return {"ok": True, "channels": ch}

    @app.post("/api/test/save")
    async def test_save(request: Request):
        body = await request.json()
        mapping = body.get("mapping", {})
        cfg = config_manager.load()
        # Funktsioon -> PPM kanal indeks
        fn_to_ch = {str(v): int(k) for k, v in mapping.items()}
        # Telje konfiguratsioon controller akseleist
        axis_src = {"roll": "rx", "pitch": "ry", "throttle": "ly", "yaw": "lx"}
        axis_invert = {"roll": False, "pitch": True, "throttle": False, "yaw": False}
        new_axes = {}
        fn_order = ["roll", "pitch", "throttle", "yaw"]
        for fn in fn_order:
            ch_idx = fn_to_ch.get(fn)
            if ch_idx is None:
                # Leia vaike positsioon
                ch_idx = fn_order.index(fn)
            ch_key = f"ch{ch_idx+1}_{fn}"
            new_axes[ch_key] = {
                "src": axis_src.get(fn, "rx"),
                "invert": axis_invert.get(fn, False),
                "expo": 0.3 if fn != "throttle" else 0.0,
                "rate": 1
            }
        # ARM kanal
        arm_ch = fn_to_ch.get("arm", 4)  # vaikimisi CH5
        arm_key = f"ch{arm_ch+1}"
        new_buttons = {arm_key: {"src": "btn_a", "mode": "toggle", "on": 1, "off": -1}}
        # Teine nupp CH6-le
        remaining = [i for i in range(8) if i not in fn_to_ch.values() and i != arm_ch]
        if remaining:
            new_buttons[f"ch{remaining[0]+1}"] = {"src": "btn_b", "mode": "toggle", "on": 1, "off": -1}
        cfg["controller"]["axes"] = new_axes
        cfg["controller"]["buttons"] = new_buttons
        import json as _json
        with open("config.json", "w") as f:
            _json.dump(cfg, f, indent=2, ensure_ascii=False)
        return {"ok": True, "axes": new_axes, "buttons": new_buttons}

    @app.get("/test", response_class=HTMLResponse)
    async def test_page():
        with open("static/test.html") as f:
            return f.read()

    @app.websocket("/ws/test")
    async def websocket_test(ws: WebSocket):
        await ws.accept()
        log.info("Test WebSocket ühendatud")
        SAFE = [1500, 1500, 1500, 1000, 1000, 1000, 1000, 1000]
        if hasattr(tx, "set_raw_us"):
            tx.set_raw_us(SAFE)
        try:
            while True:
                text = await ws.receive_text()
                msg = json.loads(text)
                if ctrl:
                    ctrl._last_rx = time.monotonic()
                    ctrl._in_failsafe = False
                if "channels" in msg and hasattr(tx, "set_raw_us"):
                    tx.set_raw_us(msg["channels"])
                    _last_channels[:] = [(v - 1500) / 500.0 for v in msg["channels"][:16]]
                elif msg.get("safe"):
                    if hasattr(tx, "set_raw_us"):
                        tx.set_raw_us(SAFE)
                    log.info("Test: turvaline seisund")
        except WebSocketDisconnect:
            if hasattr(tx, "set_raw_us"):
                tx.set_raw_us(SAFE)
            log.info("Test WebSocket lahutatud")


    # ── Salvestamine ──────────────────────────────────────────────────────

    @app.post("/api/record")
    async def api_record(request: Request):
        body = await request.json()
        action = body.get("action", "")
        if action == "start":
            fname = video_streamer.start_recording()
            return {"ok": True, "status": "recording", "filename": fname}
        elif action == "stop":
            result = video_streamer.stop_recording()
            return result
        elif action == "status":
            return {
                "recording": video_streamer.is_recording,
                "duration": round(video_streamer.recording_duration, 1),
                "filename": video_streamer._rec_filename if video_streamer.is_recording else ""
            }
        return {"ok": False, "error": "Tundmatu tegevus"}

    @app.get("/api/recordings")
    async def api_recordings():
        return video_streamer.list_recordings()

    @app.delete("/api/recordings/{filename}")
    async def api_delete_recording(filename: str):
        ok = video_streamer.delete_recording(filename)
        return {"ok": ok}

    @app.get("/recordings/{filename}")
    async def serve_recording(filename: str):
        import os
        from fastapi.responses import FileResponse
        from video_streamer import RECORDINGS_DIR
        safe = os.path.basename(filename)
        if not safe.startswith("rec_") or not safe.endswith(".mp4"):
            raise HTTPException(404)
        fpath = os.path.join(RECORDINGS_DIR, safe)
        if not os.path.exists(fpath):
            raise HTTPException(404)
        return FileResponse(fpath, media_type="video/mp4",
                           filename=safe,
                           headers={"Content-Disposition": f"attachment; filename={safe}"})

    @app.get("/app.apk")
    async def serve_apk():
        import os
        from fastapi.responses import FileResponse
        apk = "static/app.apk"
        if not os.path.exists(apk):
            raise HTTPException(404, detail="APK ei leitud. Ehita ja lae uuendus üles.")
        return FileResponse(apk, media_type="application/vnd.android.package-archive",
                           filename="quest-fpv.apk")

    app.mount("/static", StaticFiles(directory="static"), name="static")
    return app


async def run(vrx, tx, video_streamer, telem=None, ctrl=None,
              host="0.0.0.0", port=8080):
    create_app(vrx, tx, video_streamer, telem, ctrl)
    config = uvicorn.Config(app, host=host, port=port, log_level="warning")
    server = uvicorn.Server(config)
    log.info(f"Web UI: http://{host}:{port}")
    await asyncio.sleep(0)
    await server.serve()
