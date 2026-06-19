# Quest FPV Ground Station — Claude juhised

## Projekt
RPi5-põhine FPV droonikontrolli maajaam. RPi5 on samaaegselt TX (PPM/CRSF), video vastuvõtja ja veebiserver.

## RPi5 ligipääs
```
ssh pi@192.168.1.145   (parool: rpi5)
Teenus: quest-groundstation.service
Logid:  journalctl -u quest-groundstation -n 50
Web UI: http://192.168.1.145:8080
```

## Repo
- **GitHub:** https://github.com/RauntsEsT/quest-fpv-groundstation
- **Kohalik RPi koopia:** `/home/pi/quest-fpv-groundstation`
- **Kohalik Windows koopia:** `C:\Users\RaunoArulaane\AppData\Local\Temp\gs-local`

## Kriitilised faktid — loe enne muutmist

### RPi5 UART GPIO mapping (erineb BCM2711 dokumentatsioonist!)
`pinctrl get` kinnitas RPi5 (RP1 kiip) tegelikud pinid:
```
dtoverlay=uart2 → GPIO4 (TXD2), GPIO5 (RXD2) → /dev/ttyAMA2   [Foxeer VRX]
dtoverlay=uart4 → GPIO12 (TXD4), GPIO13 (RXD4) → /dev/ttyAMA4  [SmartPort]
```
BCM2711 dokumendid väidavad uart4=GPIO8/9 — see on VALE RPi5-l. Ära kasuta BCM2711 GPIO numbreid.

### Video — PAL vs NTSC
USBTV007 capture card (1b71:3002) kasutab vaikimisi NTSC dekooderit (3.58 MHz).
VRX väljastab PAL composite (4.43 MHz) → ilma `-standard PAL` ffmpeg argumendita on pilt must-valge.
Pärast USB reset-i tuleb PAL uuesti rakendada (`v4l2-ctl --set-standard=PAL`).

### MAVLink — EI KASUTA
MAVLink on liiga aeglane. Kasutame SmartPort telemeetriat.

### SmartPort juhtmestik
```
JR mooduli pin5 → SN74LVC1G04 inverter IN
Inverter OUT → GPIO13 (RPi5 pin 33, ttyAMA4 RXD4)  ← NB: GPIO13, mitte GPIO12!
Inverter 3V3 → RPi pin 17
Inverter GND → RPi pin 39
```
SmartPort: 57600 baud, inverteeritud UART, pool-dupleks.

## Praegune olek (2026-06-19)

### Töötab ✅
- PPM RC kanalid → GPIO18 → JR moodul
- CRSF link → ttyAMA0
- Video (WebSocket `/ws/video`) värvilisel pildil
- Web UI http://192.168.1.145:8080
- Android rakendus (Capacitor) — repo: https://github.com/RauntsEsT/quest-fpv-app

### Pooleli ⏳
**SmartPort telemeetria** — peamine avatud probleem.
- Inverter ühendatud GPIO13-le (õige RX pinn)
- `config.json`: `telemetry.smartport.port = /dev/ttyAMA4`, baud 57600
- Viimane test: 0 baiti — katkestati enne lõppu (RPi läks võrgust eemale)
- Järgmine samm:
  ```bash
  sudo systemctl stop quest-groundstation
  python3 -c "import serial,time; s=serial.Serial('/dev/ttyAMA4',57600,timeout=4); d=s.read(256); print(len(d),'baiti:',d[:32].hex())"
  ```
  Kui 0 baiti → kontrolli Betaflight FC Ports lehelt kas SmartPort on sisse lülitatud.

### Ootel (ei alusta enne SmartPort töötab)
- RSSI (ADS1115 ADC, I2C GPIO2/3)
- VRX kanali muutmine (Foxeer Wildfire, protokoll selguseta)
- RPi WiFi hotspot (AP mode välikasutuseks, IP 10.42.0.1)

## Failide struktuur
```
groundstation/
  main.py              — teenuse käivitamine
  config.json          — UART pordid, draiverid, kanalid
  video_streamer.py    — ffmpeg + WebSocket video
  web_server.py        — FastAPI, /ws/video, /api/telemetry
  telemetry_smartport.py — SmartPort draiver
  ppm_tx.py            — PPM GPIO18 kaudu
  static/index.html    — Web UI (kogu frontend)
WIRING.md              — juhtmestiku diagrammid (RPi5 tegelike GPIO numbritega)
RESEARCH.md            — kõik lahendatud probleemid, mida ei tasu uuesti proovida
```

## Kasutaja eelistused
- Suhtlus eesti keeles
- Tee kohe, ära küsi luba iga sammu ees
- Ära kasuta MAVLink-i
