---
name: fpv-expert
description: "FPV RC süsteemide tehniline ekspert — protokollid, kanal mapping, tarkvarad, failsafe, FC integratsioon"
metadata: 
  node_type: memory
  type: reference
  originSessionId: 56a9bcfa-c9d5-4ae0-a133-59a4eb3f2ce0
---

# FPV RC Süsteemide Tehniline Ekspert

Kasuta seda eksperti kui vajad täpset tehnilist infot FPV puldi tarkvarade, protokollide, kanal mappingu või FC integratsiooniga seotud küsimustes.

---

## PROTOKOLLID — Kuidas täpselt töötavad

### PPM (Pulse Position Modulation)
- Üks traat kuni 8 kanaliga
- Iga kanal = 300–500µs sünkropuls + varieeruv lõhe (1000–2000µs)
- Kanali väärtus = puls + lõhe vahemik (1000=min, 1500=center, 2000=max)
- Frame 20ms (50Hz), lõpus sync gap 5000–20000µs
- Polaarsus konfigureeritav (positiivne/inverteeritud)
- **EI** sisalda telemeetriat, ühepoolne
- RPi5 genereerimine: lgpio GPIO kirjutused + C busy-wait ajastus (mitte PWM hardware)

### CRSF (Crossfire Serial Protocol)
- Kasutatakse TBS Crossfire JA ExpressLRS FC-ühenduses
- Baudrate: **416 666** (Crossfire) / **420 000** (ELRS)
- 8N1 formaat, kuni 64 baiti/frame
- Sync byte: `0xC8` (FC) / `0xEA` (RC remote)
- RC channels frame type `0x16`: 16 kanalit × 11 bitti, ~22 baiti
- Center väärtus: **992 ticks = 1500µs**
- Konversioon: `µs = (ticks - 992) × 5/8 + 1500`
- CRC8 polünoom: 0xD5
- Täiseduplex UART (FC TX ↔ RX TX, FC RX ↔ RX TX)

### SBUS
- 100 000 baud, 8E2, **inverteeritud** loogika
- 25 baiti/frame, 16 kanalit × 11 bitti pakitud
- Kanal raw range 192–1792 → µs 1000–2000
- Frame rate 14ms (71Hz) / 7ms FastSBUS
- Header `0x0F`, footer `0x00`
- F4 FC vajab hardware inverterit SBUS pad-il

### iBUS (Flysky)
- 115 200 baud, half-duplex (servo+telemetria samal tral)
- 7ms frame (~143Hz), 14 kanalit, direct µs väärtused
- Telemetria: kuni 10 sensorit, receiver on bus master

---

## EDGETX / OPENTX

### Signaali ahel (3 etappi)
1. **Inputs** — füüsilised kontrollid → tarkvara sisendid (rate, expo, offset, trim)
2. **Mixes** — sisendid kombineeritakse kanaliteks (kaalud, kõverad, tingimused, viivitused)
3. **Outputs** — viimased per-kanal korrektsioonid (subtrim, min/max endpoints, invertimine) → RF moodul

### Kanal mapping EdgeTX-is
- `SYS → Settings → Default Channel Order`: AETR (FrSky/Betaflight standard) või TAER (Spektrum)
- PPM väljund: konfigureeritav frame pikkus, puls pikkus, polaarsus
- Kanal range: konfigureeritav millisekeundites

### EdgeTX Companion vs EdgeTX Buddy
- **Buddy** (buddy.edgetx.org): ainult firmware flash + SD card seadistus
- **Companion** (desktop): mudeli muutmine, backup, simulatsioon, firmware build+flash

### Firmware update
- F4/F2: USB DFU bootloader (T1+T4 trim hoida → USB ühenda)
- H7: UF2 meetod (T1+T4 → USB mass storage → kopeeri .uf2)

---

## EXPRESSLRS (ELRS)

### Sagedusvahemikud
- **2.4 GHz**: kuni 1000Hz (FLRC), kompaktsed antennid, kuni 1W
- **900 MHz**: kuni 200Hz (SX127x) / 1000Hz (LR1121 FSK), parem penetratsioon
- **LR1121**: dual-band (2.4GHz + sub-GHz), enables GemX crossband

### Packet rates (2.4 GHz)
LoRa: 50/100/150/250/333/500Hz | FLRC: 500/1000Hz | Full res: 100/333Hz

### Kanal resolutsioon
- CH1–4 (peamised): alati 10-bit (1024 sammu), igal paketil
- AUX (5–12): Hybrid/Wide switch mode (1–7 bit), üks AUX paketi kohta

### Binding
- **Binding phrase** (peamine): sama fraas TX ja RX firmwares → auto-bind käivitusel
- **Traditsiooniline**: LUA script → Bind nupp + RX bind mode
- Binding phrase ≠ krüpteerimine — ainult FHSS seemnestab

### WiFi update
- Hotspot: "ExpressLRS TX Module" / "ExpressLRS RX", parool: **expresslrs**
- IP: **10.0.0.1**, timeout RX-il: **60 sekundit** (siis RX loob ise hotspot)
- Home network: http://elrs_tx.local

### Model Match
- RX saab unikaalse ID (0–63)
- Vale ID: RX ühendab TX-iga aga **ei saada FC-le midagi** → FC läheb kohe failsafe'i
- ELRS failsafe: CRSF frameide puudumine >100ms → Betaflight Stage 1

---

## TBS CROSSFIRE

### Erinevused ELRS-ist
| | Crossfire | ELRS |
|---|---|---|
| OTA protokoll | Proprietary, krüpteeritud | Avatud (LoRa/FLRC/FSK) |
| Maks kiirus | 150Hz | 1000Hz |
| Latentsus | ~6.7ms | ~1ms (F1000) |
| Maks range | 40+km | 30+km (2.4G), 50+km (900M) |
| Hind | $$$ | $ |

### TBS Agent tarkvara
- **AgentM** (web, Chrome/Edge): TX/RX firmware update
- **Agent Lite** (LUA skript radiol): bind, power, output mapping — EI vaja arvutit
- OTA receiver update: vananenud RX firmware uuendatakse automaatselt bindimise käigus

### Model Match Crossfire'il
- Crossfire TX seotud kindla puldimudeli numbriga
- RPi-l pole sama "mudeli konteksti" → RX võib ühenduse tagasi lükata
- **Lahendus**: SYS → Tools → Crossfire / TBS Agent Lite → **Model Match: OFF**

### PPM channel mapping (Quest FPV Groundstation meie süsteemis)
TBS Crossfire Micro TX v2 FW V6.42 — **SWAPIB PPM CH3/CH4!** Kinnitatud MSP kalibratsiooni mõõtmisega 2026-06-09:
```
PPM CH1 (index0) → CRSF CH1 → FC Roll (INAV CH1 AETR)
PPM CH2 (index1) → CRSF CH2 → FC Pitch (INAV CH2 AETR)
PPM CH3 (index2) → CRSF CH4 → FC Yaw (INAV CH4 AETR)  ← SWAP!
PPM CH4 (index3) → CRSF CH3 → FC Throttle (INAV CH3 AETR)  ← SWAP!
PPM CH5 (index4) → CRSF CH5 → AUX1/ARM
```
INAV Channel Map: **AETR** (standard).
channel_mapper.py: `"ch3_throttle": 3, "ch4_yaw": 2`  (kompenseerib Crossfire swapi)
Failsafe safe state: PPM[2]=1500(yaw center), PPM[3]=1000(throttle min)
FAILSAFE_CHANNELS: `[0.0, 0.0, 0.0, -1.0, -1.0*12]` (index2=yaw ctr, index3=thr min)

---

## KANAL MAPPING JA ORDERING

### Standardid
| CH | FrSky/EdgeTX (AETR) | Spektrum (TAER) |
|----|---------------------|-----------------|
| 1  | Aileron (Roll)      | Throttle        |
| 2  | Elevator (Pitch)    | Aileron         |
| 3  | Throttle            | Elevator        |
| 4  | Rudder (Yaw)        | Rudder          |
| 5+ | AUX                 | AUX             |

### Betaflight channel map konfigureerimine
Receiver tab → Channel Map: "AETR1234" (FrSky) või "TAER1234" (Spektrum)

---

## BETAFLIGHT FAILSAFE (2 etappi)

### Signaali kaotuse tuvastamine
- Serial (CRSF/SBUS): >100ms pakettide puudumine
- PPM: >300ms invalid puls

### Stage 1 (Channel Fallback)
- Kestus: `failsafe_delay` (vaikimisi 1.5s BF4.5)
- Kanalid: Hold (viimane positsioon) / Set (eelmääratud) / Auto (THR→0, rest→center)
- PID aktiivsed — võimalik taastumine

### Stage 2 (Failsafe Procedure)
- **DROP** (racing vaikimisi): kohene disarm + mootori stopp
- **AUTO-LAND**: level lend → laskumine → disarm
- **GPS_RESCUE**: lennatakse koju, maandumine

### CLI parameetrid
```
failsafe_delay           # Stage 1 kestus (0.1s sammud)
failsafe_procedure       # DROP / AUTO-LAND / GPS_RESCUE
failsafe_throttle        # Gaas AUTO-LAND ajal
failsafe_recovery_delay  # Taastumine nõuab signaali (500ms vaikimisi)
```

---

## INAV RECEIVER KONFIGURATSIOON

```bash
set receiver_type = SERIAL
set serialrx_provider = CRSF    # või SBUS, FPORT, jne
set sbus_inversion = OFF
set serialrx_halfduplex = ON    # F.Port jaoks
```

---

## KOMPANION RAKENDUSED

| Rakendus | Platvorm | Eesmärk |
|----------|----------|---------|
| EdgeTX Buddy | Veebi (Chromium) | Firmware flash, SD card |
| EdgeTX Companion | Desktop | Mudeli muutmine, backup, simulatsioon |
| ExpressLRS Configurator | Desktop | ELRS TX/RX firmware build+flash |
| ELRS LUA Script | Radiol | Runtime parameetrid, bind, VTX |
| TBS AgentM | Veebi (Chrome) | Crossfire/Tracer firmware |
| TBS Agent Lite (LUA) | Radiol | Bind, power, konfiguratsioon |
| Betaflight Configurator | Desktop/Veebi | FC seadistamine |
| INAV Configurator | Desktop | FC seadistamine (navigatsioon) |

---

## KRIITILISED NUMBRID

| Parameeter | Väärtus |
|------------|---------|
| PPM pulse width | 1000–2000µs |
| PPM sync gap | 5000–20000µs |
| PPM frame rate | 50Hz (20ms) |
| SBUS baudrate | 100 000 baud, 8E2 |
| SBUS frame | 25 baiti |
| CRSF baudrate (Crossfire) | 416 666 baud |
| CRSF baudrate (ELRS) | 420 000 baud |
| CRSF center | 992 ticks = 1500µs |
| CRSF channel resolution | 11-bit (2048 sammu) |
| CRSF CRC | 0xD5 (x^7+x^6+x^4+x^2+x^0) |
| iBUS baudrate | 115 200 baud |
| ELRS max (2.4G) | 1000Hz FLRC F1000 |
| ELRS WiFi parool | "expresslrs" |
| ELRS WiFi IP | 10.0.0.1 |
| ELRS WiFi timeout | 60 sekundit |
| BF Stage 1 vaikimisi | 1.5s (BF4.5) |
| BF signal loss (serial) | 100ms |
| BF signal loss (PPM) | 300ms |

---

## ALLIKAD
- ExpressLRS dokumentatsioon: expresslrs.org
- TBS CRSF spec: github.com/tbs-fpv/tbs-crsf-spec
- EdgeTX manuaal: manual.edgetx.org
- Betaflight failsafe: betaflight.com/docs/wiki/guides/current/Failsafe
- Oscar Liang FPV juhendid: oscarliang.com
- INAV Rx dokumentatsioon: github.com/iNavFlight/inav/blob/master/docs/Rx.md
