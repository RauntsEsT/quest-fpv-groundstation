# Quest FPV Ground Station — Claude juhised

## ⚡ IGA SESSIOONI ALGUSES — loe tracker seis

Enne kui midagi teed, laadi projekti tracker Supabasest. See näitab mis on blokeeritud, mis töös ja kasutaja märkused:

```powershell
$r = Invoke-RestMethod -Uri "https://lsdkrmyrgyrayimwndaw.supabase.co/rest/v1/task_states?project_slug=eq.quest-fpv-groundstation&status=neq.pending&select=task_id,status,notes&order=updated_at.desc" -Headers @{ "apikey" = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImxzZGtybXlyZ3lyYXlpbXduZGF3Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODMwOTA5MDMsImV4cCI6MjA5ODY2NjkwM30.kVap-MdL_fohoMjRit8EyoNZTIYKNQEF1PzOvzAjmRo"; "Authorization" = "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImxzZGtybXlyZ3lyYXlpbXduZGF3Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODMwOTA5MDMsImV4cCI6MjA5ODY2NjkwM30.kVap-MdL_fohoMjRit8EyoNZTIYKNQEF1PzOvzAjmRo" }; $r | ConvertTo-Json
```

Või Bashis (RPi SSH kaudu):
```bash
curl -s "https://lsdkrmyrgyrayimwndaw.supabase.co/rest/v1/task_states?project_slug=eq.quest-fpv-groundstation&status=neq.pending&select=task_id,status,notes&order=updated_at.desc" \
  -H "apikey: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImxzZGtybXlyZ3lyYXlpbXduZGF3Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODMwOTA5MDMsImV4cCI6MjA5ODY2NjkwM30.kVap-MdL_fohoMjRit8EyoNZTIYKNQEF1PzOvzAjmRo" | python3 -m json.tool
```

**Loe tulemusest:**
- `status: "blocked"` → kasutaja on takistusele otsa jooksnud, märkus selgitab mida
- `status: "inprogress"` → aktiivne töö, märkus näitab viimast seisu
- `notes` väli → kasutaja kommentaarid, võivad sisaldada kriitilisi fakte

Tracker veebis: **https://curious-hamster-51f166.netlify.app**

## 💬 Kahepoolne vestlus (task_comments) — KONTROLLI IGA SESSIOONI ALGUSES

Tracker'is saab iga ülesande all kirjutada vabas vormis muudatussoovi ("vestlus").
Need on eraldi tabelis ja on kahepoolse suhtluse kanal — kasutaja kirjutab
soovi, Claude teeb muudatuse ja vastab samasse lõime.

**1. Loe lahendamata soovid:**
```bash
curl -s "https://lsdkrmyrgyrayimwndaw.supabase.co/rest/v1/task_comments?project_slug=eq.quest-fpv-groundstation&author=eq.user&resolved=eq.false&select=id,task_id,body,created_at&order=created_at.asc" \
  -H "apikey: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImxzZGtybXlyZ3lyYXlpbXduZGF3Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODMwOTA5MDMsImV4cCI6MjA5ODY2NjkwM30.kVap-MdL_fohoMjRit8EyoNZTIYKNQEF1PzOvzAjmRo" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImxzZGtybXlyZ3lyYXlpbXduZGF3Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODMwOTA5MDMsImV4cCI6MjA5ODY2NjkwM30.kVap-MdL_fohoMjRit8EyoNZTIYKNQEF1PzOvzAjmRo"
```
Iga rida = `task_id` juurde kirjutatud muudatussoov, mida pole veel käsitletud.
Käsitle neid **enne** üldise "Järgmised sammud" nimekirja järgimist — need on
kasutaja otsene, värske sisend.

**2. Kui muudatus on tehtud, vasta lõimes JA märgi lahendatuks:**
```bash
# a) Claude vastus samasse vestlusesse
curl -s -X POST "https://lsdkrmyrgyrayimwndaw.supabase.co/rest/v1/task_comments" \
  -H "apikey: <sama key>" -H "Authorization: Bearer <sama key>" \
  -H "Content-Type: application/json" -H "Prefer: return=minimal" \
  -d '{"project_slug":"quest-fpv-groundstation","task_id":"<task_id>","author":"claude","body":"Tehtud: <lühikokkuvõte muudatusest, commit hash kui asjakohane>","resolved":true}'

# b) originaalne soov lahendatuks
curl -s -X PATCH "https://lsdkrmyrgyrayimwndaw.supabase.co/rest/v1/task_comments?id=eq.<id>" \
  -H "apikey: <sama key>" -H "Authorization: Bearer <sama key>" \
  -H "Content-Type: application/json" \
  -d '{"resolved":true}'
```
Kui soovi ei saa (veel) täita — vasta ikkagi lõimes selgitusega miks, aga jäta
`resolved:false`, et see jääks tracker'is silmatorkavaks kuni päriselt lahendatud.

**Tabel eeldab, et migratsioon on käivitatud:** `supabase_task_comments.sql`
(repo juurkataloogis). Kui `task_comments` päring annab 404/tabelit pole,
see samm on tegemata — teavita kasutajat.

---

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
