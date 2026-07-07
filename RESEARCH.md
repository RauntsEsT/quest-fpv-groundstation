# Quest FPV Ground Station — Uurimusleiud ja Lahendatud Probleemid

Dokument kogub kõik olulised leiud, et vältida samade vigade kordamist.

---

## 1. RPi5 UART GPIO Mapping (KRIITILINE)

**Probleem:** BCM2711 dokumentatsioon ütleb `uart4=GPIO8/9` ja `uart5=GPIO12/13`.  
**RPi5-l (RP1 kiip) on TEISITI.**

**Kinnitatud `pinctrl get` käsuga:**
```
GPIO12 = TXD4   ← uart4 TX
GPIO13 = RXD4   ← uart4 RX  ← SmartPort inverter siia!
```

**Praegune /boot/firmware/config.txt:**
```ini
dtoverlay=uart0    # ELRS TX module (GPIO14/15, ttyAMA0)
dtoverlay=uart2    # Foxeer VRX UART (GPIO4/5, ttyAMA2)
dtoverlay=uart4    # SmartPort telemetria (GPIO12/13, ttyAMA4)
```

**Reegel:** Ära usalda BCM2711 GPIO numbreid RPi5-l. Kontrolli alati `pinctrl get`.

---

## 2. Video Must-Valge Probleem (LAHENDATUD)

**Sümptom:** Videol värv puudub (must-valge).

**Põhjus:** USBTV007 USB capture card (1b71:3002) kasutab vaikimisi NTSC chroma dekooderit (3.58 MHz), kuid VRX composite video väljund on PAL (4.43 MHz). Tulemus: värvikandja sagedus ei sobitu → must-valge pilt.

**Mida prooviti (ei töötanud):**
- Kaamera vahetus (Foxeer Razer → teine kaamera) — sama tulemus
- VTX vahetus — sama tulemus
- ffmpeg filtrite eemaldamine (yadif, hqdn3d, scale) — sama tulemus
- Kõigi viimaste koodimuudatuste üks-haaval tagasivõtmine (7 muudatust testiti)

**Tegelik põhjus:** Commit `bbf6d4b` lisas ffmpeg käsule `-standard NTSC`, mis programmeeris USBTV007 kiibi NTSC reziimi. Kiibi seadistus jääb püsima isegi pärast ffmpeg taaskäivitust (kerneli tasemel).

**Lahendus:** `-standard PAL` ffmpeg käsus:
```python
"-standard", "PAL",
```

**Oluline:** Pärast USB reset-i lähtestatakse USBTV007 NTSC vaikimisi seadele. PAL tuleb uuesti rakendada:
```python
proc = await asyncio.create_subprocess_exec(
    'v4l2-ctl', '--set-standard=PAL', '-d', '/dev/video0', ...)
```

**V4L2 standard püsivus:** VIDIOC_S_STD seadistus püsib kerneli tasemel üle ffmpeg taaskäivituste. Kustutatakse ainult USB unbind/bind või mooduli laadimisega.

---

## 3. Video Latency Optimeerimine

**Meetodid, mis vähendasid latentsust:**
- `asyncio.Queue(maxsize=1)` — vana kaader visatakse ära, uus asendab kohe
- `-thread_queue_size 1` — ffmpeg sisendpuhver miinimumini
- `-probesize 32` + `-analyzeduration 0` — ffmpeg käivitub kohe, ei analy stream
- `-fflags nobuffer -flags low_delay`
- WebSocket video (`/ws/video`) MJPEG HTTP streami asemel — browser ei puhverda

**WebSocket video põhimõte:**
- Server teeb `video_streamer.subscribe()` → saab Queue
- Iga MJPEG kaader pushitakse WebSocket kaudu binary sõnumina
- Browser: `URL.createObjectURL(blob)` → `<img src>`, eelmine URL revokeditakse
- Auto-reconnect: `ws.onclose → setTimeout(connectVideoWs, 1000)`

---

## 4. SmartPort Telemeetria (POOLELI)

**Protokoll:** FrSky SmartPort (S.Port)
- 57600 baud, **inverteeritud** UART, pool-dupleks (üks juhe)
- JR mooduli pin5 väljastab S.Port signaali
- Vajalik riistvarainverter kuna RPi UART ei suuda inverteeritud signaali lugeda

**Inverter:** SN74LVC1G04 (single inverter gate)
- Pinout: GND, 3.3V, IN, OUT
- Ühendus: JR pin5 → IN, OUT → GPIO13 (RPi5 RXD4)

**Praegune staatus:** 0 baiti ttyAMA4-l. Juhe liigutati GPIO12-lt → GPIO13-le (õige RX pinn). Test katkestati enne tulemuse saamist (RPi läks võrgust eemale).

**Järgmised sammud:**
1. Peata teenus: `sudo systemctl stop quest-groundstation`
2. Testi otse:
   ```bash
   python3 -c "import serial,time; s=serial.Serial('/dev/ttyAMA4',57600,timeout=4); d=s.read(256); print(len(d),'baiti:',d[:32].hex())"
   ```
3. Kui 0 baiti → kontrolli Betaflight Ports lehelt kas SmartPort on sisse lülitatud
4. Kui andmed tulevad → kontrolli HUD-is telemetriat (`/` → Fly vaade)

**Betaflight seadistus FC-s:**
- Configuration → Receiver → Serial-based receiver, CRSF (kui ELRS)  
- Ports → UART [X] → Telemetry Output → SmartPort
- Kus X on see UART, millega FC S.Port juhe on ühendatud

---

## 5. MAVLink — EI KASUTA

MAVLink on liiga aeglane. Projekt kasutab SmartPort telemeetriat.  
`telemetry_mavlink.py` fail on alles, kuid konfist eemaldatud.

---

## 6. VRX Kanali Muutmine

**Foxeer Wildfire** — UART protokol puudub (dokumentatsioon olematu).

**Võimalused:**
- `rtc6715` — SPI otseprogrammeerimine (GPIO8/10/11). Töötab, kuid konflikti risk GPIO8-ga.
- `button` — NPN transistorid simuleerivad nuppude vajutusi (GPIO6/13/19). Konflikti risk GPIO13-ga (SmartPort RX).
- `foxeer_uart` — praegu kasutusel, kuid tegelikku protokolli pole õnnestunud tuvastada.

**Praegune draiver:** `foxeer_uart` on konfiguratsioonis, kuid tegeliku kanalmuutuse käskude formaat on ebaselge.

---

## 7. RSSI

**Staatus:** Pole implementeeritud.  
**Plaan:** ADS1115 I2C ADC → Foxeer Wildfire pin2 (RSSI analoogsignaal 0–3.3V)  
**I2C:** GPIO2 (SDA), GPIO3 (SCL), aadress 0x48

---

## 8. Süsteemi Arhitektuur

```
RPi5 → (GPIO18 PPM) → JR mooduli pin1  [RC kanalid drooni]
RPi5 ↔ (ttyAMA0 CRSF 400k) → ELRS TX moodul  [RC + telemeetria link]
RPi5 ↔ (ttyAMA2 115200) → Foxeer Wildfire UART  [VRX kontroll]
RPi5 ← (ttyAMA4 57600) ← inverter ← JR pin5  [SmartPort telemeetria]
RPi5 ← (USB /dev/video0) ← EasyCap ← VRX composite out  [Video]
```

**Teenus:** `quest-groundstation.service`  
**Logid:** `journalctl -u quest-groundstation -n 50`  
**Web UI:** `http://192.168.1.145:8080`

---

## 9. WiFi Fallback-AP Sundlülituse Bug (LAHENDATUD, 2026-07-07)

**Sümptom:** RPi lülitus EWG (töövõrgu) WiFi-lt korduvalt hotspot-režiimi
(FPV-Ground, 10.0.0.1) tagasi, isegi kui EWG-ga oli äsja edukalt ühendutud
ja signaal oli tugev (100%). Restart aitas ajutiselt, aga probleem kordus
tavaliselt ~30-50s jooksul pärast bootimist.

**Juurpõhjus:** `/usr/local/bin/fallback-ap.sh` (boot-aegne oneshot teenus,
`fallback-ap.service`) ja `/etc/NetworkManager/dispatcher.d/99-fallback-ap`
(dispatcher hook) kontrollisid aktiivset WiFi-ühendust command'iga:
```bash
nmcli -t -f NAME,TYPE,DEVICE connection show --active | grep wifi
```
`nmcli` näitab WiFi-ühenduse TYPE väljal `802-11-wireless`, mitte `wifi` —
`grep wifi` ei leidnud SEDA KUNAGI, mistõttu skript arvas alati, et
stations-ühendust pole, ja:
1. `fallback-ap.sh` lülitas 30s pärast bootimist **sundkorras** hotspoti
   sisse, isegi kui EWG oli juba edukalt ühendunud (NetworkManageri
   autoconnect töötas kiiremini kui 30s, aga fallback-skript ei
   tuvastanud seda ja lülitas selle üle kirjutades ümber).
2. Dispatcher (`99-fallback-ap`) tekitas lisaks lõputu tsükli: hotspoti
   sisselülitamine tekitab enda `wlan0 down` sündmuse → dispatcher käivitub
   uuesti → sama vale kontroll → toob hotspoti "uuesti" üles → tekitab jälle
   `wlan0 down` → ... (logides nähtav "WiFi lost — starting AP" iga ~6s).

**Fix:** vahetati kontroll usaldusväärsema vastu, mis loeb otse DEVICE=wlan0
välja (TYPE-le ei tugine):
```bash
nmcli -t -f NAME,DEVICE connection show --active | grep ':wlan0$' | cut -d: -f1
```
Dispatcher lisaks kontrollib, kas aktiivne ühendus on juba `FPV-Hotspot` ise
(enda tekitatud `down` sündmus) ja väljub vaikselt, ilma taas `nmcli
connection up` käivitamata — see katkestab tsükli.

Boot-aegne ooteaeg tõsteti `WAIT=30` → `WAIT=45` (EWG on mesh mitme
pöörduspunktiga, assotsieerumine võib mõni kord kauem aega võtta).

Lisaks lisati `retry-station.timer` (systemd timer, iga 2 min, `OnBootSec=90`)
+ `retry-station.service`, mis hotspot-režiimis olles skannib kas `EWG` või
`Kirsikivi` on leviala sees ning proovib automaatselt tagasi lülituda —
ilma käsitsi restardita, kui WiFi taastub.

**Testitud:** 2 järjestikust reboot-tsüklit, stabiilne EWG-ühendus 4+ minutit
ilma katkestusteta (varem katkes garanteeritult ~50s juures).

Failid: `/usr/local/bin/fallback-ap.sh`, `/usr/local/bin/retry-station.sh`,
`/etc/NetworkManager/dispatcher.d/99-fallback-ap`,
`/etc/systemd/system/retry-station.{service,timer}` (kõik ainult RPi-l,
mitte git-repos — vt käesolevat sektsiooni koodinäidete jaoks).
