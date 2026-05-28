# Quest FPV Ground Station — RPi5 Wiring Diagram

---

## Foxeer Wildfire — 9-Pin Connector Pinout

```
Foxeer Wildfire 9-pin kaabel (pin 1 = esimene, modulist väljuv pool)

  ┌───┬────┬───┬─────┬─────┬─────┬──────┬──────┬──────┐
  │ 1 │  2 │ 3 │  4  │  5  │  6  │  7   │  8   │  9   │
  └───┴────┴───┴─────┴─────┴─────┴──────┴──────┴──────┘
   5V  RSSI GND  AudL  AudR  VID  Chan3  Chan2  Chan1
                                  (CS)   (CLK)  (DATA)
```

| Pin | Nimetus        | Suund      | Ühendus                        | Märkus                          |
|-----|----------------|------------|--------------------------------|---------------------------------|
| 1   | 5V             | ← sisend   | RPi5 Pin 2 (5V)                | ~350mA, parem väline 5V allikas |
| 2   | RSSI / NC      | → väljund  | ADS1115 A0                     | Analoog 0–3.3V, signaalitugevus |
| 3   | GND            | —          | RPi5 Pin 6 (GND)               | Ühine maandus!                  |
| 4   | Audio L        | → väljund  | EasyCap valge RCA (valikuline) | Audio vasakkanal                |
| 5   | Audio R        | → väljund  | EasyCap punane RCA (valikuline)| Audio paremkanal                |
| 6   | Video Out      | → väljund  | EasyCap kollane RCA            | Composite video ~1Vpp           |
| 7   | Chan3 / **CS** | ← sisend   | RPi5 Pin 24 (GPIO8)            | SPI Chip Select (active LOW)    |
| 8   | Chan2 / **CLK**| ← sisend   | RPi5 Pin 23 (GPIO11)           | SPI kell                        |
| 9   | Chan1 / **DATA**| ← sisend  | RPi5 Pin 19 (GPIO10)           | SPI MOSI / RTC6715 DATA         |

---

## Foxeer Wildfire + EasyCap + RPi5 — Täielik skeem

### Signaalide ahel

```
Foxeer Wildfire 8-pin                  EasyCap                 RPi5
┌────────────────────┐                ┌──────────────┐
│ Pin 1 (5V)  ◄──────┼── RPi Pin 2 ──┤              │
│ Pin 3 (GND) ◄──────┼── RPi Pin 6   │              │
│                    │                │              │
│ Pin 5 (Video) ─────┼───────────────►│ Yellow RCA   │──USB──► /dev/video0
│ Pin 4 (Audio) ─────┼───────────────►│ White  RCA   │         (valikuline)
│                    │                └──────────────┘
│ Pin 2 (RSSI)  ─────┼───────────────────────────────────► ADS1115 A0
│                    │
│ Pin 9 (Data)  ◄────┼── RPi Pin 19 (GPIO10)  ┐
│ Pin 7 (CS)    ◄────┼── RPi Pin 24 (GPIO8)   ├─ SPI kanalivalik
│ Pin 8 (CLK)   ◄────┼── RPi Pin 23 (GPIO11)  ┘   (RTC6715)
└────────────────────┘
```

### Detailne ühendustabel

| Komponent       | Pin # | Viik/nimi    | →  | RPi5 Pin     | GPIO    | Märkus                          |
|-----------------|-------|--------------|----|--------------|---------|----------------------------------|
| Foxeer Wildfire | 1     | 5V           | ←  | Pin 2 või 4  | 5V      | ~350mA, kaalumisel väline toide |
| Foxeer Wildfire | 3     | GND          | ←  | Pin 6        | GND     | Ühine maandus kõigile           |
| Foxeer Wildfire | 6     | Video Out    | →  | EasyCap RCA  | —       | Composite video (kollane RCA)   |
| Foxeer Wildfire | 4     | Audio L      | →  | EasyCap RCA  | —       | Audio L (valge RCA, valikuline) |
| Foxeer Wildfire | 5     | Audio R      | →  | EasyCap RCA  | —       | Audio R (punane RCA, valikuline)|
| EasyCap         | —     | USB-A        | →  | RPi USB 3.0  | —       | Ilmub `/dev/video0`             |
| Foxeer Wildfire | 2     | RSSI         | →  | ADS1115 A0   | —       | 0–3.3V analoogsignaal           |
| ADS1115         | —     | SDA          | ↔  | Pin 3        | GPIO2   | I2C andmed                      |
| ADS1115         | —     | SCL          | ↔  | Pin 5        | GPIO3   | I2C kell                        |
| ADS1115         | —     | VDD          | ←  | Pin 1        | 3V3     | 3.3V toide                      |
| ADS1115         | —     | GND          | ←  | Pin 6        | GND     |                                 |
| ADS1115         | —     | ADDR         | ←  | GND          | —       | I2C aadress 0x48                |
| Foxeer Wildfire | 9     | Chan1 (DATA) | ←  | Pin 19       | GPIO10  | SPI MOSI / RTC6715 DATA         |
| Foxeer Wildfire | 7     | Chan3 (CS)   | ←  | Pin 24       | GPIO8   | SPI Chip Select (active LOW)    |
| Foxeer Wildfire | 8     | Chan2 (CLK)  | ←  | Pin 23       | GPIO11  | SPI kell                        |

### EasyCap — praktilised nõuanded

```
EasyCap sisend:
  ┌─────────────────────────────────────────────┐
  │  [YELLOW RCA]  ◄── VRX Video Out            │  ← ainult see on vajalik!
  │  [WHITE  RCA]  ◄── Audio L  (ei kasutata)   │
  │  [RED    RCA]  ◄── Audio R  (ei kasutata)   │
  │  [USB-A]       ──► RPi5 USB port            │
  └─────────────────────────────────────────────┘

Linux draiver: uvcvideo (automaatne, ei vaja seadistust)
Kontrolli: v4l2-ctl --list-devices
           → EasyCap (usb-...): /dev/video0

ffmpeg test:
  ffplay -f v4l2 -i /dev/video0

Kui EasyCap näitab mustvalget pilti:
  → VRX ja capture card peavad kasutama sama videostandardi (PAL/NTSC)
  → Proovi: ffmpeg -f v4l2 -standard PAL -i /dev/video0 ...
```

### VRX toide — hoiatused

```
⚠  RPi5 Pin 2/4 (5V) on otse ühendatud USB toitega.
   Maksimaalne vool: ~600mA kõigi seadmete peale kokku.

   Kui VRX tarbib rohkem kui ~200mA → kasuta välise 5V toiteallikat!
   Välise toite puhul ühenda ainult GND RPi külge (ühine maandus).

Tüüpilised VRX voolud:
   Eachine ROTG02 / RC832:  ~200mA  → RPi 5V PIN sobib
   Foxeer wildfire:         ~350mA  → piiripealne, parem väline toide
   Diversiteedi VRX:        ~450mA  → kasuta välist toidet
```

---

## RPi5 40-Pin GPIO Header

```
              3V3  [ 1] [ 2]  5V
   I2C SDA  GPIO2  [ 3] [ 4]  5V
   I2C SCL  GPIO3  [ 5] [ 6]  GND
  VRX-UART  GPIO4  [ 7] [ 8]  GPIO14  ELRS TX → TX
              GND  [ 9] [10]  GPIO15  ELRS RX ← TX
             GPIO17 [11] [12]  GPIO18
             GPIO27 [13] [14]  GND
             GPIO22 [15] [16]  GPIO23
              3V3  [17] [18]  GPIO24
  SPI MOSI  GPIO10 [19] [20]  GND
  SPI MISO  GPIO9  [21] [22]  GPIO25
  SPI CLK   GPIO11 [23] [24]  GPIO8   SPI CS / VRX-UART TX
              GND  [25] [26]  GPIO7
       ID_SD GPIO0  [27] [28]  GPIO1   ID_SC
  VRX-UART  GPIO5  [29] [30]  GND
  BTN UP    GPIO6  [31] [32]  GPIO12  FC-TELEM TX →
  BTN DOWN  GPIO13 [33] [34]  GND
  BTN ENTER GPIO19 [35] [36]  GPIO16
             GPIO26 [37] [38]  GPIO20
              GND  [39] [40]  GPIO21
                                       FC-TELEM (UART5 alt): GPIO12/13
```

---

## Module Connections

### 1. ELRS TX Module (ExpressLRS, CRSF protocol)

| RPi5 Pin | GPIO   | Direction | ELRS Pin | Notes              |
|----------|--------|-----------|----------|--------------------|
| Pin 8    | GPIO14 | RPi → TX  | RX       | 3.3V logic         |
| Pin 10   | GPIO15 | TX → RPi  | TX       | 3.3V logic         |
| Pin 6    | GND    | —         | GND      | Common ground      |
| Pin 4    | 5V     | —         | 5V       | If TX needs 5V pwr |

**Software:** `/dev/ttyAMA0` @ **420000 baud**, CRSF protocol  
**config.txt:** `enable_uart=1` + `dtoverlay=uart0` (already set by setup script)

---

### 2. USB Capture Card (Analog VRX video → RPi)

Plug directly into RPi5 USB 3.0 port. No GPIO wiring needed.

```
Analog VRX video out → RCA/BNC → USB Capture Card → USB-A → RPi5
```

**Software:** appears as `/dev/video0`, ffmpeg streams to UDP port 5006

---

### 3A. Foxeer Wildfire / Analog VRX — RTC6715 SPI (automatic channel control)

| RPi5 Pin | GPIO   | Direction | VRX Pin              | Foxeer Wildfire Pin      | Notes                     |
|----------|--------|-----------|----------------------|--------------------------|---------------------------|
| Pin 23   | GPIO11 | RPi → VRX | CLK                  | **Pin 8 (Chan2 / CLK)**  | SPI clock, bit-bang       |
| Pin 19   | GPIO10 | RPi → VRX | DATA                 | **Pin 9 (Chan1 / DATA)** | SPI MOSI                  |
| Pin 24   | GPIO8  | RPi → VRX | CS                   | **Pin 7 (Chan3 / CS)**   | Chip select (active LOW)  |
| Pin 6    | GND    | —         | GND                  | **Pin 3 (GND)**          |                           |
| Pin 2    | 5V     | —         | VCC (5V)             | **Pin 1 (5V)**           | ~350mA, kaalumisel väline |

**Software:** `vrx.driver = "rtc6715"` in `config.json`

> **Note:** GPIO8/10/11 are the hardware SPI0 pins. This driver uses bit-banging
> so hardware SPI does not need to be enabled. Do NOT enable SPI overlay in config.txt.

---

### 3B. RSSI Reading for RTC6715 — ADS1115 ADC (via I2C)

Connect ADS1115 to read analog RSSI voltage from VRX.

| RPi5 Pin | GPIO  | Direction  | ADS1115 Pin | Notes                    |
|----------|-------|------------|-------------|--------------------------|
| Pin 3    | GPIO2 | bidirect.  | SDA         | I2C data                 |
| Pin 5    | GPIO3 | bidirect.  | SCL         | I2C clock                |
| Pin 1    | 3V3   | —          | VDD         | 3.3V power               |
| Pin 6    | GND   | —          | GND         |                          |
| —        | —     | VRX → ADC  | A0          | RSSI antenna A (0–3.3V)  |
| —        | —     | VRX → ADC  | A1          | RSSI antenna B (0–3.3V)  |

**I2C address:** `0x48` (ADDR pin → GND)  
**Software:** enable I2C in config.txt: `dtparam=i2c_arm=on`

---

### 3C. Analog VRX — Button Emulation (NPN transistor, manual channel only)

Use this if your VRX has only UP/DOWN/ENTER buttons (no SPI). Requires 3× NPN transistor (BC547 / 2N2222).

```
RPi GPIO ──[1kΩ]──► NPN Base (BC547)
                     NPN Collector ──► VRX Button pin
                     NPN Emitter  ──► GND
```

| RPi5 Pin | GPIO   | VRX Button | Transistor |
|----------|--------|------------|------------|
| Pin 31   | GPIO6  | UP         | NPN #1     |
| Pin 33   | GPIO13 | DOWN       | NPN #2     |
| Pin 35   | GPIO19 | ENTER      | NPN #3     |

**Software:** `vrx.driver = "button"` in `config.json`

> **⚠ Conflict:** GPIO13 is shared with UART5 (FC Telemetry option).
> Do not use button emulation simultaneously with FC telemetry on UART5.

---

### 3D. Foxeer Wildfire — RSSI (ADS1115 via I2C)

Foxeer Wildfire **Pin 2 (RSSI)** annab analoogsignaali signaalitugevuse kohta.  
Kuna RPi5-l pole analoog-sisendeid, kasutame ADS1115 ADC-d.

| Foxeer Pin | Nimetus | → | ADS1115 | Märkus                    |
|------------|---------|---|---------|---------------------------|
| Pin 2      | RSSI    | → | A0      | 0–3.3V analoogsignaal     |
| Pin 3      | GND     | — | GND     | Ühine maandus             |

> ADS1115 ühendus RPi-ga on kirjeldatud sektsioonis **3B** (I2C, GPIO2/3).

---

### 4. Flight Controller Telemetry

Connect FC telemetry output to RPi. Supports MAVLink, MSP, CRSF, SmartPort, LTM, HoTT.

#### Option A — UART4 (GPIO8/GPIO9) — `/dev/ttyAMA4`

> **⚠ Conflict:** GPIO8 is also SPI0 CS (RTC6715 VRX). Only use UART4 if NOT using RTC6715 driver.

| RPi5 Pin | GPIO  | Direction  | FC Pin  | Notes                   |
|----------|-------|------------|---------|-------------------------|
| Pin 24   | GPIO8 | RPi → FC   | RX      | Telem UART TX (UART4)   |
| Pin 21   | GPIO9 | FC → RPi   | TX      | Telem UART RX (UART4)   |
| Pin 6    | GND   | —          | GND     |                         |

**config.txt:** `dtoverlay=uart4`  
**config.json:** default port for MAVLink/MSP etc. is `/dev/ttyAMA4`

#### Option B — UART5 (GPIO12/GPIO13) — `/dev/ttyAMA5` ✅ (recommended with RTC6715)

| RPi5 Pin | GPIO   | Direction  | FC Pin  | Notes                   |
|----------|--------|------------|---------|-------------------------|
| Pin 32   | GPIO12 | RPi → FC   | RX      | Telem UART TX (UART5)   |
| Pin 33   | GPIO13 | FC → RPi   | TX      | Telem UART RX (UART5)   |
| Pin 6    | GND    | —          | GND     |                         |

**config.txt:** `dtoverlay=uart5`  
**config.json:** change port to `/dev/ttyAMA5` in Telemetry settings tab

> **⚠ Conflict:** GPIO13 is also used by Button Emulation VRX (DOWN button).
> Do not combine button emulation with UART5.

---

### 5. Digital VRX (Walksnail / HDZero / DJI O3)

No GPIO wiring — digital VRX connects via **HDMI** to USB capture card.

```
Digital VRX HDMI out → HDMI-to-USB capture card → USB-A → RPi5
```

**Software:** `vrx.driver = "walksnail"` / `"hdzero"` / `"dji_o3"` in `config.json`

---

## Compatible Configurations (Pin Conflict Matrix)

| VRX Driver    | FC Telemetry Port | Notes                              |
|---------------|-------------------|------------------------------------|
| `rtc6715`     | `/dev/ttyAMA5`    | ✅ No conflicts (UART5 = GPIO12/13) |
| `foxeer_uart` | `/dev/ttyAMA4`    | ✅ No conflicts (UART4 = GPIO8/9)   |
| `foxeer_uart` | `/dev/ttyAMA5`    | ✅ No conflicts                     |
| `button`      | `/dev/ttyAMA4`    | ✅ No conflicts (UART4 = GPIO8/9)   |
| `dummy`       | any               | ✅ No hardware needed               |
| `walksnail`   | any               | ✅ USB only, no GPIO                |
| `rtc6715`     | `/dev/ttyAMA4`    | ❌ GPIO8 conflict (SPI CS + UART4 TX)|
| `button`      | `/dev/ttyAMA5`    | ❌ GPIO13 conflict (BTN_DOWN + UART5 RX)|

---

## Full System Block Diagram

```
                        ┌─────────────────────────────────────┐
                        │         Raspberry Pi 5              │
                        │                                     │
 ELRS TX Module ────────│ GPIO14/15  (UART0  /dev/ttyAMA0)   │
                        │                                     │
 Analog VRX (SPI) ──────│ GPIO8/10/11 (SPI0 bit-bang)        │
 ADS1115 RSSI    ───────│ GPIO2/3     (I2C1  0x48)           │
                        │                                     │
 Foxeer VRX ────────────│ GPIO4/5    (UART3  /dev/ttyAMA3)   │
                        │                                     │
 FC Telemetry ──────────│ GPIO12/13  (UART5  /dev/ttyAMA5) ✅│
           OR ──────────│ GPIO8/9    (UART4  /dev/ttyAMA4)   │
                        │                                     │
 Button VRX ────────────│ GPIO6/13/19 (GPIO out via NPN)     │
                        │                                     │
 USB Capture Card ──────│ USB 3.0 port  → /dev/video0        │
                        │                                     │
 Android / Quest 3 ─────│ WiFi UDP 5005 (controller in)      │
                    ─────│ WiFi TCP 8080 (Web UI)             │
                    ─────│ WiFi UDP 5006 (video stream out)   │
                        └─────────────────────────────────────┘
```

---

## /boot/firmware/config.txt Overlays

Add the overlays for the UARTs you use:

```ini
# Always required for ELRS (primary UART)
enable_uart=1
dtoverlay=uart0

# Foxeer Wildfire VRX on GPIO4/5
dtoverlay=uart3

# FC Telemetry Option A (conflicts with RTC6715 SPI)
# dtoverlay=uart4

# FC Telemetry Option B — recommended with RTC6715
dtoverlay=uart5

# I2C for ADS1115 RSSI (usually enabled by default)
dtparam=i2c_arm=on
```

---

## Voltage & Logic Level Notes

- RPi5 GPIO is **3.3V logic** — do NOT connect 5V signals directly
- Most ELRS TX modules operate at 3.3V UART — check your module
- If FC outputs 5V UART: use a **3.3V/5V bidirectional level shifter**
- VRX power: check your VRX datasheet — some need 5V, some 3.3V
- ADS1115 RSSI input: max **3.3V** (matches AREF when powered from 3V3)

---

## Quick Reference

| Function          | GPIO   | Phys Pin | Port / Protocol         |
|-------------------|--------|----------|-------------------------|
| ELRS UART TX      | GPIO14 | 8        | /dev/ttyAMA0 @ 420000   |
| ELRS UART RX      | GPIO15 | 10       | /dev/ttyAMA0 @ 420000   |
| Foxeer VRX TX     | GPIO4  | 7        | /dev/ttyAMA3 @ 115200   |
| Foxeer VRX RX     | GPIO5  | 29       | /dev/ttyAMA3 @ 115200   |
| RTC6715 CS        | GPIO8  | 24       | SPI0 (bit-bang)         |
| RTC6715 MOSI      | GPIO10 | 19       | SPI0 (bit-bang)         |
| RTC6715 CLK       | GPIO11 | 23       | SPI0 (bit-bang)         |
| ADS1115 SDA       | GPIO2  | 3        | I2C1 addr 0x48          |
| ADS1115 SCL       | GPIO3  | 5        | I2C1 addr 0x48          |
| FC Telem TX       | GPIO12 | 32       | /dev/ttyAMA5 (UART5) ✅ |
| FC Telem RX       | GPIO13 | 33       | /dev/ttyAMA5 (UART5) ✅ |
| BTN VRX UP        | GPIO6  | 31       | GPIO out (NPN)          |
| BTN VRX DOWN      | GPIO13 | 33       | GPIO out (NPN) ⚠        |
| BTN VRX ENTER     | GPIO19 | 35       | GPIO out (NPN)          |
| USB Capture Card  | —      | USB 3.0  | /dev/video0             |
