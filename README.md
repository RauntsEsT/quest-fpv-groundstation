# Quest FPV Ground Station

Meta Quest VR headset + controllers → WiFi → Raspberry Pi ground station → FPV drone control

## System Architecture

```
[Meta Quest]
  Controllers → Quest App → WiFi UDP ──────────┐
  Headset Display ← WiFi video stream ←─────────┤
                                                  │
[Ground Station - Raspberry Pi]                   │
  WiFi ←────────────────────────────────────────┘
  ├── ELRS TX (UART/USB) ← CRSF protocol ← stick inputs
  ├── USB Capture Card ← analog VRX ← drone VTX
  └── Video: v4l2 → ffmpeg encode → WiFi stream → Quest

[Drone]
  ├── ELRS RX → FC (Betaflight)
  └── VTX → analog video → VRX
```

## Hardware

### Ground Station
- Raspberry Pi 4
- Makita 18V battery → BEC → 5V rail
- 5V → Analog VRX (5.8GHz)
- 5V → ELRS TX module (UART)
- USB capture card (VRX video output)

### Controller
- Meta Quest 2/3
- Meta Quest controllers (joysticks → stick inputs)

## Components

| Folder | Description |
|--------|-------------|
| `groundstation/` | Raspberry Pi Python middleware |
| `quest-app/` | Meta Quest Unity application |
| `docs/` | Wiring diagrams, setup guides |

## Setup

See `docs/setup.md` for full setup instructions.
