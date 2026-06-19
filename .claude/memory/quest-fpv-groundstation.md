---
name: quest-fpv-groundstation
description: "Quest FPV Ground Station projekt — RPi5 groundstation tarkvara, SSH ligipääs, hetkeseisu ja järgmised sammud"
metadata: 
  node_type: memory
  type: project
  originSessionId: 39c3f354-14ec-4e54-acdf-7ce1b302c6f4
---

# Quest FPV Ground Station

**Repo:** https://github.com/RauntsEsT/quest-fpv-groundstation  
**Kohalik koopia:** `C:\Users\RaunoArulaane\Documents\quest-fpv-groundstation`

## RPi5 ligipääs
**IP:** `192.168.1.145` (staatiline, nmcli kaudu) | **Kasutaja:** `pi` | **Parool:** `rpi5`
**mDNS:** `fpv-groundstation.local`
```bash
ssh pi@192.168.1.145
echo 'rpi5' | sudo -S systemctl restart quest-groundstation
journalctl -u quest-groundstation -f
```
Web UI: `http://192.168.1.145:8080`

## Süsteemi arhitektuur
```
Quest 3 → UDP:5005 → RPi5 → GPIO18 PPM → Crossfire TX → RF → Droon
Droon → VTX → analog → Foxeer VRX → /dev/video0 → HTTP /video → Quest
```

## UART / GPIO pinout
| Port | GPIO | Füüsiline pin | Kasutus |
|------|------|---------------|---------|
| /dev/ttyAMA0 | GPIO14(TX), GPIO15(RX) | Pin 8, 10 | Crossfire CRSF (tuleviku telemetria) |
| /dev/ttyAMA2 | GPIO4(TX), GPIO5(RX) | Pin 7, 29 | Foxeer Wildfire VRX |
| — | GPIO18 | **Pin 12** | **PPM output → Crossfire pin 1** |

## Crossfire TX ühendus (TÖÖTAB ✅)
```
Crossfire pin 1 (PPM)  ──── RPi GPIO18 (pin 12)     ← RC kanalid PPM
Crossfire pin 3 (5V)   ──── RPi 5V
Crossfire pin 4 (GND)  ──── RPi GND
Crossfire pin 5 (CRSF) ──┬── RPi GPIO15 (pin 10)    ← tuleviku telemetria
                           └──[1kΩ]── RPi GPIO14 (pin 8)
```
**TBS Crossfire Micro TX v2** | FW: V6.42 | HW: V2.03  
RC Input: PPM 8ch ✅ (kinnitatud TBS Agentiga)

## Kanal mapping (lõplik, kinnitatud kalibratsiooni mõõtmisega 2026-06-09)

**Crossfire SWAPIB PPM CH3/CH4** — kinnitatud MSP mõõtmisega (PPM[2]=1000 → INAV CH4=1032, PPM[3]=1500 → INAV CH3=1472):

| PPM kanal | Array index | INAV kanal | Funktsioon |
|-----------|-------------|------------|------------|
| CH1 | 0 | INAV CH1 | Roll (Aileron) |
| CH2 | 1 | INAV CH2 | Pitch (Elevator) |
| **CH3** | **2** | **INAV CH4** | **Yaw (Rudder)** ← swap! |
| **CH4** | **3** | **INAV CH3** | **Throttle** ← swap! |
| CH5 | 4 | INAV CH5 | AUX1 / ARM |

**INAV Channel Map: AETR (standard)**  
`channel_mapper.py`: `"ch3_throttle": 3, "ch4_yaw": 2`

### Ohutusseisund (safe state):
```
PPM CH1=1500 (Roll center)    → INAV CH1 ~1500
PPM CH2=1500 (Pitch center)   → INAV CH2 ~1500
PPM CH3=1500 (Yaw center)     → INAV CH4 ~1500
PPM CH4=1000 (Throttle min)   → INAV CH3 ~1000  ← OHUTU!
PPM CH5=1000 (ARM off)        → INAV CH5 ~1000
```
`ppm_tx.py default`: `[CENTER, CENTER, CENTER, MIN, ...]`
`SAFE_CH_US (web_server)`: `[1500, 1500, 1500, 1000, 1000, 1000, 1000, 1000]`

### config.json failsafe (õige):
`ch3: 0` (yaw center), `ch4: -1` (throttle min)
`FAILSAFE_CHANNELS = tuple([0.0, 0.0, 0.0, -1.0] + [-1.0] * 12)`

### Ajalugu:
- 2026-06-08: vale "swap" tuvastati kuna web controller segas channel sweep testi → reverteeriti
- 2026-06-09: MSP kalibratsioonimõõtmine kinnitas swap definitiivselt → fix taas rakendatud

## Testimisskriptid (Windows)
- `C:\Users\RaunoArulaane\AppData\Local\Temp\channel_sweep.py` — PPM kanalite sweep test (IP: 192.168.1.144)
- `C:\Users\RaunoArulaane\AppData\Local\Temp\verify_fix.py` — paranduse kontroll (IP: 192.168.1.144)
- `C:\Users\RaunoArulaane\AppData\Local\Temp\check_link.py` — RC lingi olemasolu kontroll
- `C:\Users\RaunoArulaane\AppData\Local\Temp\channel_autotest.py` — algne automaatne test

**NB:** Python skriptides kasuta IP `192.168.1.144:8080` (mDNS ei tööta Windows pythonist)

## Android app (Capacitor)
- **Projekt:** `C:\Users\RaunoArulaane\Documents\quest-fpv-app\android`
- **Deploy skript:** `C:\Users\RaunoArulaane\Documents\quest-fpv-app\deploy.ps1`
- **OTA update:** APK serveeritakse `http://192.168.1.145:8080/app.apk` → telefon laadib alla ja installib
- **RPi teenuse nimi:** `quest-groundstation` (mitte quest-fpv)
- **GitHub SSH võti:** genereeritud RPi-l (`~/.ssh/id_ed25519`) ja lisatud GitHubi → remote on `git@github.com:RauntsEsT/quest-fpv-groundstation.git`

### Lahendatud UI probleemid:
- Zoom lennulehelt eemaldatud — ainult Settings → VRX alt muudetav (zoom slider + fit mode)
- Salvestused MP4 formaadis (H.264, `-preset ultrafast`) → mängib otse telefoni browseris
- Recordings lehel ▶ play nupp → avab inline video playeri modali
- Global top bar (44px): Fly, REC, 📹, Settings dropdown + Edit nupp
- Edit mode: teine vajutus salvestab; ✕ tühistab
- ARM widget: default Y=70% (ei jää edit riba alla)

### Pooleli: GitHub push
- 8 commiti on RPi-l lokalset pushimist ootamas (`git push origin master`)
- RPi oli võrgust maas — homme push'i: `! ssh pi@192.168.1.145 "cd /home/pi/quest-fpv-groundstation && git push origin master"`

## Järgmised sammud (tähtsuse järjekorras)

### 1. ESIMENE PRIORITEET — Droon sisse + RC lingi kontroll
- Lülita droon (patarei) sisse
- Kontrolli Crossfire TX roheline LED (RF link loodud)
- Käivita `check_link.py` — kui väärtused liiguvad >10us, link on aktiivne
- Käivita `channel_sweep.py` — kontrolli et mapping on endiselt korrektne

### 2. Täielik kontroll test
Kui link aktiivne, testi:
```
Roll right:  PPM CH1=1900 → INAV CH1 peaks +400us muutuma
Pitch up:    PPM CH2=1900 → INAV CH2 peaks +400us muutuma
Yaw right:   PPM CH3=1900 → INAV CH4 peaks +400us muutuma
Throttle up: PPM CH4=1900 → INAV CH3 peaks +400us muutuma
ARM:         PPM CH5=1900 → INAV CH5 peaks +400us muutuma ✅ (kinnitatud 386us delta)
```

### 3. ARM test
- Esmalt: throttle MIN + ARM ON → droon peaks armima
- PPM: [1500, 1500, 1500, 1000, 1900, 1000, 1000, 1000]
- INAV näitab: Throttle~1000, AUX1~1900

### 4. Web UI kontroll test
- Ava http://192.168.1.144:8080
- Testi joystick input (joystick mappingu kontroller)
- Kontrolli et Roll/Pitch/Yaw/Throttle lähevad õigetesse kanalitesse

### 5. (Hiljem) Model Match välja lülitada
Pane moodul puldile → CrossFire menüü → Model Match OFF → RPi-le tagasi
(Kui RPi-ga ühendamine ei tööta automaatselt)

## Video stream (TÖÖTAB ✅)
- USB capture card: `/dev/video0` (usbtv)
- ffmpeg: yuyv422 → PAL 720×576 → MJPEG → HTTP `/video`
- **Auto-retry:** USB pole käivitusel saadaval → ootab ja proovib uuesti
- **Watchdog (lisatud 2026-06-15, commit 157c340):** kui ffmpeg jookseb aga
  ei tooda päris kaadreid (vaid "NO SIGNAL" placeholder) >8s (kasvav kuni 30s),
  kill ffmpeg + USB reset + restart. Lahendab probleemi kus uue sessiooni
  alguses video ei tulnud automaatselt läbi (ffmpeg/usbtv jäi "kinni" placeholder
  moodi kuigi VTX signaal oli olemas — ainult teenuse restart aitas varem).

## Web UI bug (parandatud 2026-06-15, commit d177161)
`groundstation/static/index.html` rida ~1533: stray `\'` tekitas JS süntaksivea,
mis lõhkus KOGU inline `<script>` bloki → `showPage()`, `connectWS()` jms
funktsioone ei eksisteerinud. Sümptomid: status dot püsis "off" (ühendamata),
Fly nupp ei reageerinud. Kontrolli sarnaste muudatuste järel alati
`node --check` (extract script → check syntax) kui index.html JS-stringe muudad.

## Recordings playback bug (parandatud 2026-06-15, commit b16f3c4)
`web_server.py` `/recordings/{filename}` endpoint nõudis `.avi` laiendit, aga
`MJPEGRecorder` salvestab `.mp4` (H.264) faile → kõik salvestused 404.
Fix: kontroll + media_type muudetud `.mp4`/`video/mp4`. Testitud: salvestamine
ja taasesitus töötab.

## Äpi ühenduse robustsus + multi-groundstation (2026-06-15, commit 391f7de)
- **Capacitor launcher** (`quest-fpv-app/www/index.html`): uus täielik leheke, mis
  laaditakse esimesena (eemaldatud `server.url` capacitor.config.json'ist).
  - Hoiab maajaamade nimekirja localStorage'is (`gs_list`: `[{name, host}]`),
    vaikimisi "Kodu" → `192.168.1.145`.
  - Reachability check: `fetch(url + '/api/status', {mode:'no-cors', cache:'no-store'})`
    + AbortController timeout 2.5s.
  - Auto-retry adaptiivse backoff'iga (2/3/5/8/10s), "Proovi kohe" nupp.
  - "Maajaamad" haldusvaade: lisa/kustuta/näe online-staatust; õnnestunud
    ühendus tõstetakse nimekirja etteotsa (viimati kasutatud = esimene proov
    järgmisel käivitusel).
  - Õnnestumisel `window.location.href = url + '/'` (suunab otse RPi UI-le).
- **RPi UI** (`groundstation/static/index.html`): Settings menüüsse lisatud
  "Vaheta maajaam" (id `smenu-switch-gs`), nähtav vaid `window.Capacitor`
  olemasolul → navigeerib `https://localhost/index.html#manage` (avab
  launcheri halduse vaate otse).
- **capacitor.config.json**: `server.url` eemaldatud, `allowNavigation: ["*"]`
  (lubab navigeerida ükskõik millisesse konfigureeritud maajaama IP-sse).
- APK ehitatud ja laetud RPi-le OTA jaoks (`/app.apk`), pole veel telefoni
  installitud (ADB seadet ei tuvastatud sel sessioonil — installi OTA kaudu
  äpi seest või käsitsi).

### NB: deploy.ps1 ei käivitu otse PowerShellis
`deploy.ps1` on UTF-8 (ilma BOM-ita) ja sisaldab `→` märke — PowerShell 5.1
loeb skriptifaili vale codepage'iga ja viskab "string missing terminator".
Töötab kui käivitada gradle/scp/adb käsud käsitsi Bashis (vt seda sessiooni).
Fix oleks lisada BOM faili või asendada `→` märgid ASCII-ga.

### Pooleli (deferred, kasutaja valikul "App esmalt, RPi AP hiljem")
**RPi WiFi AP fallback** — kui lendamas looduses, telefon peab saama otse
RPi-ga ühenduda (RPi kui WiFi AP, nt SSID "QuestFPV-GS", staatiline IP
10.42.0.1 `wlan0`-l). Tehakse hiljem, kui kasutaja on Pi juures füüsiliselt
(risk: SSH ligipääsu kadu, kui konfiguratsioon valesti läheb üle võrgu).
Kui see valmis, lisa launcheri vaikenimekirja teine kirje (nt "Väli (AP)" →
`10.42.0.1`).

## Telemeetria sisse lülitatud (2026-06-15, commit 2556b6b)
Varem oli telemeetria taristu (`/api/telemetry`, `telemetry_crsf.py`,
`TelemetryManager`) olemas, aga TX mode = "ppm" tähendas, et `CrossfireTX`
klassi (mis loeb CRSF UART-i pealt telemeetria/link-stats kaadreid) ei
loodud kunagi → `telemetry_crsf.py` `.feed()` ei saanud kunagi midagi.
Fix `main.py`: kui `tx.type == 'ppm'`, käivitatakse PARALLEELSELT
`CrossfireTX(tx_port, tx_baud).start(handshake_only=True)` (UART
`/dev/ttyAMA0` = Crossfire CRSF pin5, vt pinout) — see ei saada RC kanaleid
(PPM teeb seda GPIO18 kaudu), aga loeb sissetulevad CRSF kaadrid (LINK_STATS,
GPS, BATTERY, ATTITUDE, FLIGHT_MODE, VARIO, BARO_ALT) ja edastab
`telemetry_crsf.py`-le `_telem_feed` hooki kaudu. `PPMTransmitter.get_status()`
loeb nüüd `self.stats`-ist (jagatud `LinkStats` objekt `crsf_telem_link`-iga)
päris LQ/RSSI/SNR väärtused, mitte konstantseid nulle.
Lisaks fix: `telemetry_crsf.py` GPS kaadris seadis `gps_speed_ms`, aga
`get_dict()` loeb `speed_ms` → lisatud `d.speed_ms = speed/36.0` ja
`d.gps_fix` arvutus satelliitide arvust.

**Testimine 2026-06-15:** teenus käivitub korrektselt, log näitab
"Crossfire TX starting on /dev/ttyAMA0 (handshake only)" ja
"CRSF telemetry listening". `/api/status` näitas kõik telemeetria väärtused
veel nulli — droon/Crossfire TX moodul oli väljas testimise ajal, seega
LINK_STATS/GPS/BATTERY kaadreid ei tulnud. **Järgmine test:** lülita droon +
RC link sisse, kontrolli `/api/status` → `tx.link_quality`/`rssi_ant1` peaks
muutuma nullist erinevaks (link-stats CRSF kaadrid TX moodulilt). Täielik
lennuandmete telemeetria (GPS, patarei, attitude) vajab, et **INAV FC-l
oleks CRSF telemeetria sensorid sisse lülitatud** (Configurator → Ports/
Telemetry → CRSF) ja RX oleks ühendatud FC-ga CRSF-iga — see on FC-poolne
konfiguratsioon, mida pole veel kontrollitud.

## CRSF telemeetria diagnoos: pin5 = S.Port, mitte CRSF (2026-06-15)
Diagnostika (debug logiga `crossfire_tx.py`) näitas, et `/dev/ttyAMA0`
(GPIO14/15, Crossfire pin5) sai 0 baiti — isegi mitte self-echo'd.
Kasutaja kontrollis JR-bay pinout't: **pin5 on märgistatud "SPort"**, mitte
CRSF. S.Port (FrSky SmartPort) on **inverteeritud UART @ 57600** (idle LOW),
RPi PL011 UART eeldab idle HIGH — moodul hoiab rida konstantselt LOW-s,
mistõttu UART start-bitti ei tuvasta kunagi → 0 baiti. See seletab täielikult
varasema "0 bytes" leiu.

**Lahendus valitud: MAVLink otse INAV-ist, mitte CRSF/SmartPort sniffing.**
`telemetry_mavlink.py` on juba täielikult implementeeritud (GPS, patarei,
attitude, armed, flight mode, home distance/bearing).

### MAVLink ettevalmistus (TEHTUD 2026-06-15, commit 6d80f9d)
- `pymavlink` installitud `venv`-i (`/home/pi/quest-fpv-groundstation/venv`)
- `/boot/firmware/config.txt`: lisatud `dtoverlay=uart4` (rida 55, pärast
  uart0/uart2) → annab `/dev/ttyAMA4` GPIO12(TX)/GPIO13(RX) — **mõlemad pinid
  kontrollitud vabad** (`pinctrl get 12,13` → "none")
- `config.json`: `telemetry.drivers = ["crsf","mavlink"]`,
  `telemetry.mavlink = {"port":"/dev/ttyAMA4","baud":57600}`
- **Reboot vajalik**, et `dtoverlay=uart4` jõustuks → `/dev/ttyAMA4` tekib.
  Reboot lükatud edasi (droon oli sees/armitav, PPM katkeks lühidalt).
  MAVLink draiver on graceful kuni reboot — proovib ühendust iga 5s,
  ebaõnnestub vaikselt kuni `/dev/ttyAMA4` olemas.

### Pooleli — kasutaja peab tegema (vajab füüsilist ligipääsu droonile/FC-le)
1. INAV Configurator → Ports tab: lülita **MAVLink telemetry** sisse ühel
   vabal FC UART-il, baud 57600
2. Juhtmestik: FC UART TX → RPi **GPIO13 (RX)**, FC UART RX ← RPi
   **GPIO12 (TX)**, jagatud GND
3. RPi reboot (kui droon on disarmitud/PPM ei kriitiline) → `/dev/ttyAMA4`
   tekib, teenus restardib automaatselt ja MAVLink draiver ühendub
4. Kontroll: `curl localhost:8080/api/telemetry` → `protocol:"mavlink"`,
   `connected:true`, GPS/aku/attitude väärtused

Crossfire CRSF UART (ttyAMA0/handshake_only, vt eelnev sektsioon) jääb
aktiivseks paralleelselt — annab LQ/RSSI link-statsi kui Crossfire link aktiivne
(see osa ei sõltu S.Port probleemist, kuna LINK_STATS kaadrid tulevad
Crossfire TX moodulilt vastusena meie CRSF ping/model-id kaadritele —
TODO: kontrollida, kas needki kaadrid jõuavad läbi, kui pin5=SPort hõivab
liini; võib vajada, et see UART jäetaks lihtsalt välja, kui MAVLink katab
kõik vajaliku).

## Pinch-zoom vs joystick konflikt (parandatud 2026-06-15, commit 5a7fbba)
Leftover pinch-to-zoom handler (~rida 1237) reageeris IGALE 2-puute
touchstart/touchmove sündmusele Fly lehel ja zoomis videot vahemaa järgi —
konfliktis kahe joystick'i samaaegse kasutamisega (kangid lähemale/kaugemale
= video zoom sisse/välja). Eemaldatud täielikult; zoom jääb ainult
Settings → VRX slider'i kaudu muudetavaks (vastab varasemale "zoom eemaldatud
fly lehelt" otsusele, mis polnud täielikult rakendatud).

## Config (RPi5) — praegune seis
```json
{
  "vrx": {"driver": "foxeer_uart", "options": {"port": "/dev/ttyAMA2"}, "band": "F", "channel": 7},
  "tx":  {"type": "ppm", "gpio_pin": 18, "port": "/dev/ttyAMA0", "baud": 400000},
  "controller": {
    "axes": {
      "ch1_roll": {"src": "rx", "invert": false, "expo": 0.3, "rate": 1},
      "ch2_pitch": {"src": "ry", "invert": true, "expo": 0.3, "rate": 1},
      "ch3_throttle": {"src": "ly", "invert": false, "expo": 0.0, "rate": 1},
      "ch4_yaw": {"src": "lx", "invert": false, "expo": 0.3, "rate": 1}
    },
    "buttons": {
      "ch5": {"src": "btn_a", "mode": "toggle", "on": 1, "off": -1}
    },
    "failsafe": {"ch1": 0, "ch2": 0, "ch3": 0, "ch4": -1, "ch5": -1, ...}
  }
}
```

## TBS Agent
Installitud: `C:\Users\RaunoArulaane\Downloads\TBS-Agent\TBS Agent Setup 4.5.1.exe`
