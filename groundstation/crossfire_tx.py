"""
TBS Crossfire TX module manager — CRSF protocol over UART.
UART: RPi5 GPIO14(TX)→Crossfire RX, GPIO15(RX)←Crossfire TX
Port: /dev/ttyAMA0 @ 400000 baud

Capabilities:
  - RC channel sending (16ch, 11-bit, 50 Hz)
  - TX module device discovery (CRSF device ping)
  - Parameter enumeration and read/write (power, rate, region, …)
  - Drone binding via parameter trigger
  - Link-stats telemetry parsing
"""
import asyncio
import logging
import serial
import struct
from dataclasses import dataclass, field
from typing import Optional

log = logging.getLogger("crossfire_tx")

# ── CRSF addresses ─────────────────────────────────────────────────────────
CRSF_ADDR_BROADCAST       = 0x00
CRSF_ADDR_FC              = 0xC8
CRSF_ADDR_GROUND_STATION  = 0xEA
CRSF_ADDR_RX              = 0xEC
CRSF_ADDR_TX_MODULE       = 0xEE

# ── Standard frame types ───────────────────────────────────────────────────
CRSF_TYPE_GPS             = 0x02
CRSF_TYPE_BATTERY         = 0x08
CRSF_TYPE_LINK_STATS      = 0x14
CRSF_TYPE_RC_CHANNELS     = 0x16
CRSF_TYPE_ATTITUDE        = 0x1E
CRSF_TYPE_FLIGHT_MODE     = 0x21

# ── Extended frame types (type >= 0x28, carry dest + src) ─────────────────
CRSF_TYPE_DEVICE_PING     = 0x28
CRSF_TYPE_DEVICE_INFO     = 0x29
CRSF_TYPE_PARAM_ENTRY     = 0x2B
CRSF_TYPE_PARAM_READ      = 0x2C
CRSF_TYPE_PARAM_WRITE     = 0x2D
CRSF_TYPE_COMMAND         = 0x32

# ── Parameter value types ──────────────────────────────────────────────────
PARAM_UINT8    = 0
PARAM_INT8     = 1
PARAM_UINT16   = 2
PARAM_INT16    = 3
PARAM_FLOAT    = 8
PARAM_TEXT_SEL = 9
PARAM_STRING   = 10
PARAM_FOLDER   = 11
PARAM_INFO     = 12
PARAM_COMMAND  = 13

CRSF_CENTER = 992
CRSF_RANGE  = 819  # 992 ± 819 = 172..1811

_POWER_TABLE = [0, 10, 25, 100, 500, 1000, 2000, 250, 50]  # mW indexed by CRSF power enum

# Model ID subcommand constants (from EdgeTX crossfire.cpp)
CRSF_SUBCOMMAND_CRSF        = 0x10
CRSF_COMMAND_MODEL_SELECT   = 0x05


# ── Frame builders ─────────────────────────────────────────────────────────

def _crc8(data: bytes) -> int:
    crc = 0
    for b in data:
        crc ^= b
        for _ in range(8):
            crc = ((crc << 1) ^ 0xD5) if crc & 0x80 else crc << 1
            crc &= 0xFF
    return crc


def _crc8_ba(data: bytes) -> int:
    """CRC8 with polynomial 0xBA — used in Model ID frame (EdgeTX crossfire.cpp)."""
    crc = 0
    for b in data:
        crc ^= b
        for _ in range(8):
            crc = ((crc << 1) ^ 0xBA) if crc & 0x80 else crc << 1
            crc &= 0xFF
    return crc


def build_model_id_frame(model_id: int = 0) -> bytes:
    """
    Model ID frame — tells Crossfire TX which model is active.
    EdgeTX sends this at startup and after 500ms module silence.
    Without it, module may not activate RF output.

    Format (from EdgeTX createCrossfireModelIDFrame):
    [0xC8][8][0x32][0xEE][0xEA][0x10][0x05][model_id][crc8_BA][crc8]
    """
    frame = bytes([
        CRSF_ADDR_FC,              # 0xC8 sync/radio address
        8,                          # length = 8 bytes following
        CRSF_TYPE_COMMAND,         # 0x32
        CRSF_ADDR_TX_MODULE,       # 0xEE destination
        CRSF_ADDR_GROUND_STATION,  # 0xEA source
        CRSF_SUBCOMMAND_CRSF,      # 0x10
        CRSF_COMMAND_MODEL_SELECT, # 0x05
        model_id & 0xFF,
    ])
    payload = frame[2:]             # bytes after sync+len
    crc_ba  = _crc8_ba(payload)    # crc8_BA over 6 bytes
    crc     = _crc8(payload + bytes([crc_ba]))  # crc8 over 7 bytes
    return frame + bytes([crc_ba, crc])


def _ch(v: float) -> int:
    return int(CRSF_CENTER + max(-1.0, min(1.0, v)) * CRSF_RANGE)


def build_rc_frame(channels: tuple) -> bytes:
    """Pack 16 channels (float -1..1) into a CRSF RC frame."""
    ch = [_ch(channels[i]) if i < len(channels) else CRSF_CENTER for i in range(16)]
    bits = bit_count = 0
    packed = bytearray()
    for val in ch:
        bits |= (val & 0x7FF) << bit_count
        bit_count += 11
        while bit_count >= 8:
            packed.append(bits & 0xFF)
            bits >>= 8
            bit_count -= 8
    payload = bytes([CRSF_TYPE_RC_CHANNELS]) + bytes(packed)
    return bytes([CRSF_ADDR_FC, len(payload) + 1]) + payload + bytes([_crc8(payload)])


def build_extended_frame(ftype: int, dest: int, src: int, data: bytes = b'') -> bytes:
    """
    CRSF extended frame: [dest][len][type][dest][src][data…][crc]
    len = count of bytes after len field (type + dest + src + data + crc)
    CRC over: type + dest + src + data
    """
    body = bytes([ftype, dest, src]) + data
    return bytes([dest, len(body) + 1]) + body + bytes([_crc8(body)])


# ── Data classes ───────────────────────────────────────────────────────────

@dataclass
class LinkStats:
    rssi_ant1: int    = 0
    rssi_ant2: int    = 0
    link_quality: int = 0
    snr: int          = 0
    tx_power_mw: int  = 0


@dataclass
class DeviceInfo:
    name: str        = ""
    serial: str      = ""
    hw_version: str  = ""
    sw_version: str  = ""
    param_count: int = 0


@dataclass
class TxParam:
    index: int       = 0
    parent: int      = 0
    name: str        = ""
    type: int        = 0
    value: object    = None
    min_val: object  = None
    max_val: object  = None
    default_val: object = None
    unit: str        = ""
    options: list    = field(default_factory=list)


# ── Main class ─────────────────────────────────────────────────────────────

class CrossfireTX:
    """
    TBS Crossfire TX module manager — half-duplex single-wire CRSF.

    CRSF is half-duplex: TX and RX share one physical wire.
    Every byte we send echoes back on the RX line immediately.
    The _echo_pending buffer tracks outgoing bytes so they can be
    stripped from incoming data before parsing module responses.

    Wiring: RPi5 GPIO14 (TX) ──┬── Crossfire CRSF pad
                  GPIO15 (RX) ──┘
    (connect both GPIO14 and GPIO15 to the same Crossfire wire)
    """

    def __init__(self, port: str = "/dev/ttyAMA0", baud: int = 400000):
        self.port = port
        self.baud = baud
        self.stats  = LinkStats()
        self.device: Optional[DeviceInfo] = None
        self.params: dict[int, TxParam]   = {}
        self._serial: Optional[serial.Serial] = None
        self._channels: tuple = (0.0,) * 16
        self._buf          = bytearray()
        self._echo_pending = bytearray()   # bytes we sent, awaiting echo discard
        self._telem_feed   = None          # set by TelemetryManager to forward frames

    # ── Serial helpers ─────────────────────────────────────────────────────

    def _open(self):
        if not self._serial or not self._serial.is_open:
            self._serial = serial.Serial(self.port, self.baud, timeout=0)
            log.info(f"Crossfire UART open: {self.port} @ {self.baud} (half-duplex)")

    def _write(self, frame: bytes):
        try:
            self._open()
            self._serial.write(frame)
            # Queue the sent bytes — they will echo back on RX and must be discarded
            self._echo_pending.extend(frame)
        except serial.SerialException as e:
            log.error(f"UART write error: {e}")
            self._serial = None

    # ── Public API ─────────────────────────────────────────────────────────

    def send_channels(self, channels: tuple):
        """Send 16-channel CRSF RC frame. channels = tuple of float -1.0..1.0."""
        self._channels = channels
        self._write(build_rc_frame(channels))

    def send_model_id(self, model_id: int = 0):
        """
        Send Model ID frame — required for Crossfire RF activation.
        EdgeTX sends this at startup and after 500ms module silence.
        model_id 0 = first model slot (matches radio default).
        """
        self._write(build_model_id_frame(model_id))
        log.debug(f"Model ID frame sent (model={model_id})")

    def ping(self):
        """Broadcast device ping — TX module will respond with DEVICE_INFO."""
        self._write(build_extended_frame(
            CRSF_TYPE_DEVICE_PING, CRSF_ADDR_BROADCAST, CRSF_ADDR_GROUND_STATION))

    def request_param(self, index: int, chunk: int = 0):
        """Request parameter entry by 1-based index."""
        self._write(build_extended_frame(
            CRSF_TYPE_PARAM_READ, CRSF_ADDR_TX_MODULE, CRSF_ADDR_GROUND_STATION,
            bytes([index, chunk])))

    def write_param(self, index: int, value: bytes):
        """Write raw bytes to parameter at index."""
        self._write(build_extended_frame(
            CRSF_TYPE_PARAM_WRITE, CRSF_ADDR_TX_MODULE, CRSF_ADDR_GROUND_STATION,
            bytes([index]) + value))

    def write_param_uint8(self, index: int, value: int):
        self.write_param(index, bytes([value & 0xFF]))

    def write_param_selection(self, index: int, selection: int):
        """Write TEXT_SELECTION parameter (option index as uint8)."""
        self.write_param(index, bytes([selection & 0xFF]))

    def bind(self):
        """
        Enter binding mode.
        Tries to find a 'bind' parameter first; falls back to CRSF command frame.
        Power-cycle the drone receiver before calling this.
        """
        for idx, p in self.params.items():
            if 'bind' in p.name.lower():
                log.info(f"Bind via param {idx}: '{p.name}'")
                self.write_param(idx, bytes([0]))
                return
        # Generic Crossfire bind command (works on most TBS TX modules)
        self._write(build_extended_frame(
            CRSF_TYPE_COMMAND, CRSF_ADDR_TX_MODULE, CRSF_ADDR_GROUND_STATION,
            bytes([CRSF_ADDR_TX_MODULE, CRSF_ADDR_GROUND_STATION, 0x01])))
        log.info("Bind command sent (fallback CRSF command frame)")

    async def enumerate_params(self):
        """Ping the TX module, then sequentially read all parameters."""
        self.params.clear()
        self.ping()
        await asyncio.sleep(0.5)
        if not self.device:
            log.warning("TX module not responding to ping — check UART wiring")
            return
        log.info(f"Reading {self.device.param_count} TX parameters…")
        for i in range(1, self.device.param_count + 1):
            self.request_param(i)
            await asyncio.sleep(0.15)

    # ── Incoming frame parsing ─────────────────────────────────────────────

    def _drain_rx(self):
        try:
            raw = self._serial.read(256)
            if not raw:
                return
            # Strip self-echo: bytes we sent come back first in order
            if self._echo_pending:
                n = min(len(raw), len(self._echo_pending))
                # Match greedily from front; discard up to n matched echo bytes
                matched = 0
                for i in range(n):
                    if raw[i] == self._echo_pending[i]:
                        matched += 1
                    else:
                        break
                raw = raw[matched:]
                self._echo_pending = self._echo_pending[matched:]
            if raw:
                self._buf.extend(raw)
        except (serial.SerialException, AttributeError):
            self._serial = None

    def _process_buf(self):
        while len(self._buf) >= 3:
            sync = self._buf[0]
            if sync not in (0xC8, 0xEA, 0xEE, 0x00):
                self._buf.pop(0)
                continue
            frame_body_len = self._buf[1]        # bytes after [sync][len]
            total = frame_body_len + 2            # full bytes to consume
            if len(self._buf) < total:
                break
            frame = bytes(self._buf[:total])
            self._buf = self._buf[total:]

            ftype    = frame[2]
            body_crc = frame[2:-1]                # type + payload (excl sync, len, crc)
            if _crc8(body_crc) != frame[-1]:
                continue

            if ftype < 0x28:
                self._handle_standard(ftype, frame[3:-1])
            else:
                if total < 6:
                    continue
                src  = frame[4]
                data = frame[5:-1]
                self._handle_extended(ftype, src, data)

    def _handle_standard(self, ftype: int, payload: bytes):
        if ftype == CRSF_TYPE_LINK_STATS and len(payload) >= 10:
            ul_rssi1, ul_rssi2, ul_lq, ul_snr, _, _, ul_pwr = \
                struct.unpack_from('BBBbBBB', payload)
            self.stats.rssi_ant1    = ul_rssi1
            self.stats.rssi_ant2    = ul_rssi2
            self.stats.link_quality = ul_lq
            self.stats.snr          = ul_snr
            self.stats.tx_power_mw  = (
                _POWER_TABLE[ul_pwr] if ul_pwr < len(_POWER_TABLE) else 0)
        if self._telem_feed:
            self._telem_feed(ftype, payload)

    def _handle_extended(self, ftype: int, src: int, data: bytes):
        if ftype == CRSF_TYPE_DEVICE_INFO:
            self._parse_device_info(data)
        elif ftype == CRSF_TYPE_PARAM_ENTRY:
            self._parse_param_entry(data)

    def _parse_device_info(self, data: bytes):
        nul = data.find(0)
        if nul < 0:
            return
        name = data[:nul].decode('utf-8', errors='replace')
        rest = data[nul + 1:]
        if len(rest) < 13:
            return
        sn  = rest[:4].hex().upper()
        hw  = struct.unpack_from('>I', rest, 4)[0]
        sw  = struct.unpack_from('>I', rest, 8)[0]
        cnt = rest[12]
        self.device = DeviceInfo(
            name=name, serial=sn,
            hw_version=f"{hw >> 16}.{(hw >> 8) & 0xFF}.{hw & 0xFF}",
            sw_version=f"{sw >> 16}.{(sw >> 8) & 0xFF}.{sw & 0xFF}",
            param_count=cnt,
        )
        log.info(f"Crossfire TX: {name}  SW={self.device.sw_version}  params={cnt}")

    def _parse_param_entry(self, data: bytes):
        if len(data) < 4:
            return
        idx    = data[0]
        parent = data[2]
        ptype  = data[3]
        nul    = data.find(0, 4)
        if nul < 0:
            return
        name = data[4:nul].decode('utf-8', errors='replace')
        rest = data[nul + 1:]

        p = TxParam(index=idx, parent=parent, name=name, type=ptype)

        if ptype == PARAM_UINT8 and len(rest) >= 4:
            p.min_val, p.max_val, p.default_val, p.value = rest[0], rest[1], rest[2], rest[3]
        elif ptype == PARAM_TEXT_SEL:
            opts_end = rest.find(0)
            if opts_end >= 0:
                p.options = rest[:opts_end].decode('utf-8', errors='replace').split(';')
                after = rest[opts_end + 1:]
                if len(after) >= 4:
                    p.min_val, p.max_val, p.default_val, p.value = (
                        after[0], after[1], after[2], after[3])
        elif ptype == PARAM_INT8 and len(rest) >= 4:
            p.min_val, p.max_val, p.default_val = (
                struct.unpack('b', bytes([rest[0]]))[0],
                struct.unpack('b', bytes([rest[1]]))[0],
                struct.unpack('b', bytes([rest[2]]))[0],
            )
            p.value = struct.unpack('b', bytes([rest[3]]))[0]
        elif ptype in (PARAM_FOLDER, PARAM_INFO, PARAM_COMMAND, PARAM_STRING):
            if ptype == PARAM_STRING and rest:
                end = rest.find(0)
                p.value = rest[:end].decode('utf-8', errors='replace') if end >= 0 else ""
        self.params[idx] = p
        log.debug(f"Param {idx}: [{ptype}] {name!r} = {p.value!r}  opts={p.options}")

    # ── Status / serialisation ─────────────────────────────────────────────

    def get_status(self) -> dict:
        return {
            "device":       vars(self.device) if self.device else None,
            "rssi_ant1":    self.stats.rssi_ant1,
            "rssi_ant2":    self.stats.rssi_ant2,
            "link_quality": self.stats.link_quality,
            "snr":          self.stats.snr,
            "tx_power_mw":  self.stats.tx_power_mw,
        }

    def get_params(self) -> list:
        return [
            {
                "index":   p.index,
                "parent":  p.parent,
                "name":    p.name,
                "type":    p.type,
                "value":   p.value,
                "min":     p.min_val,
                "max":     p.max_val,
                "default": p.default_val,
                "options": p.options,
            }
            for p in sorted(self.params.values(), key=lambda x: x.index)
        ]

    # ── Async main loop ────────────────────────────────────────────────────

    async def start(self):
        log.info(f"Crossfire TX starting on {self.port}")
        # EdgeTX sends Model ID at startup — required to activate RF output
        self.send_model_id(0)
        self.ping()
        tick = 0
        while True:
            # Send RC frame at 50 Hz
            self._write(build_rc_frame(self._channels))
            # Read incoming telemetry / param responses
            if self._serial:
                self._drain_rx()
                self._process_buf()
            tick += 1
            # Model ID every ~2s (EdgeTX sends after 500ms silence detection)
            if tick % 100 == 0:
                self.send_model_id(0)
            # Ping every ~5s to refresh device info
            if tick % 250 == 0:
                self.ping()
            await asyncio.sleep(0.02)
