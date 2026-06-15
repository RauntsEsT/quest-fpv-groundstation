#!/bin/bash
# Quest FPV Ground Station — RPi5 täielik seadistus
#
# Kasutus (fresh Raspberry Pi OS Bookworm 64-bit peal):
#   bash setup_rpi5.sh
#
# Pärast käivitamist: sudo reboot
# Pärast reboot-i käivitub teenus automaatselt.

set -e

REPO_URL="https://github.com/RauntsEsT/quest-fpv-groundstation.git"
INSTALL_DIR="$HOME/quest-fpv-groundstation"
SERVICE="quest-groundstation"
CONFIG="/boot/firmware/config.txt"
CMDLINE="/boot/firmware/cmdline.txt"

echo ""
echo "╔══════════════════════════════════════════════════════╗"
echo "║     Quest FPV Ground Station — RPi5 Setup           ║"
echo "╚══════════════════════════════════════════════════════╝"
echo ""

# ── 1. Süsteemi uuendamine ────────────────────────────────────────────────
echo "[1/7] Süsteemi uuendamine..."
sudo apt-get update -qq
sudo apt-get upgrade -y -qq

# ── 2. Süsteemipaketid ────────────────────────────────────────────────────
echo "[2/7] Pakettide paigaldamine..."
sudo apt-get install -y -qq \
    git \
    python3-pip \
    python3-venv \
    python3-lgpio \
    ffmpeg \
    v4l-utils \
    libv4l-dev \
    libgpiod2

# ── 3. Repo kloonamine / uuendamine ──────────────────────────────────────
echo "[3/7] Repo allalaadimine..."
if [ -d "$INSTALL_DIR/.git" ]; then
    echo "  Repo juba olemas, tõmban uuendused..."
    git -C "$INSTALL_DIR" pull --ff-only
else
    git clone "$REPO_URL" "$INSTALL_DIR"
fi

# ── 4. Python venv + pip paketid ─────────────────────────────────────────
echo "[4/7] Python venv + paketid..."
python3 -m venv "$INSTALL_DIR/venv" --system-site-packages
"$INSTALL_DIR/venv/bin/pip" install -q --upgrade pip
"$INSTALL_DIR/venv/bin/pip" install -q -r "$INSTALL_DIR/groundstation/requirements.txt"

# ── 5. UART seadistus ────────────────────────────────────────────────────
echo "[5/7] UART seadistamine..."

# enable_uart=1 — aktiveerib GPIO14(TX)/GPIO15(RX) = /dev/ttyAMA0
if ! grep -q "^enable_uart=1" "$CONFIG"; then
    echo "enable_uart=1" | sudo tee -a "$CONFIG" > /dev/null
    echo "  + enable_uart=1 (Crossfire CRSF / tuleviku telemetria)"
fi

# dtoverlay=uart0 — UART0 GPIO14/GPIO15 = /dev/ttyAMA0 (Crossfire)
if ! grep -q "^dtoverlay=uart0" "$CONFIG"; then
    echo "dtoverlay=uart0" | sudo tee -a "$CONFIG" > /dev/null
    echo "  + dtoverlay=uart0 (/dev/ttyAMA0 — GPIO14/15)"
fi

# dtoverlay=uart2 — UART2 GPIO4/GPIO5 = /dev/ttyAMA2 (Foxeer VRX)
if ! grep -q "^dtoverlay=uart2" "$CONFIG"; then
    echo "dtoverlay=uart2" | sudo tee -a "$CONFIG" > /dev/null
    echo "  + dtoverlay=uart2 (/dev/ttyAMA2 — GPIO4/5 — Foxeer VRX)"
fi

# Eemalda serial konsool cmdline.txt-st (et UART vaba oleks)
if grep -q "console=serial0" "$CMDLINE"; then
    sudo sed -i 's/console=serial0,[0-9]* //' "$CMDLINE"
    echo "  - serial0 konsool eemaldatud cmdline.txt-st"
fi

# Kasutajaõigused
sudo usermod -a -G dialout,video,gpio "$USER"
echo "  + Kasutaja $USER gruppides: dialout, video, gpio"

# ── 6. Systemd teenus ────────────────────────────────────────────────────
echo "[6/7] Systemd teenuse loomine..."

sudo tee /etc/systemd/system/${SERVICE}.service > /dev/null << EOF
[Unit]
Description=Quest FPV Ground Station
After=network.target network-online.target systemd-udev-settle.service
Wants=network-online.target
StartLimitIntervalSec=60
StartLimitBurst=5

[Service]
Type=simple
User=$USER
WorkingDirectory=$INSTALL_DIR/groundstation
ExecStartPre=/bin/sleep 5
ExecStart=$INSTALL_DIR/venv/bin/python3 main.py
Restart=on-failure
RestartSec=10
TimeoutStartSec=60
StandardOutput=journal
StandardError=journal
Environment=PYTHONUNBUFFERED=1
Environment=PYTHONFAULTHANDLER=1

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable "$SERVICE"
echo "  + Teenus $SERVICE lubatud (käivitub automaatselt)"

# ── 7. Vaikimisi config.json ─────────────────────────────────────────────
echo "[7/7] Vaikimisi konfiguratsioon..."
CONFIG_JSON="$INSTALL_DIR/groundstation/config.json"
if [ ! -f "$CONFIG_JSON" ]; then
    cat > "$CONFIG_JSON" << 'EOF'
{
  "vrx": {
    "driver": "foxeer_uart",
    "options": {"port": "/dev/ttyAMA2"},
    "band": "F",
    "channel": 2
  },
  "tx": {
    "type": "ppm",
    "gpio_pin": 18,
    "port": "/dev/ttyAMA0",
    "baud": 400000
  },
  "telemetry": {
    "drivers": ["crsf"],
    "crsf": {"port": "/dev/ttyAMA0", "baud": 400000}
  },
  "controller": {
    "axes": {
      "ch1_roll":     {"src": "rx",  "invert": false, "expo": 0.3, "rate": 1.0},
      "ch2_pitch":    {"src": "ry",  "invert": true,  "expo": 0.3, "rate": 1.0},
      "ch3_throttle": {"src": "ly",  "invert": false, "expo": 0.0, "rate": 1.0},
      "ch4_yaw":      {"src": "lx",  "invert": false, "expo": 0.3, "rate": 1.0}
    },
    "dead_zone": 0.05,
    "buttons": {
      "ch5":  {"src": "btn_a", "mode": "toggle",    "on": 1.0, "off": -1.0},
      "ch6":  {"src": "btn_b", "mode": "toggle",    "on": 1.0, "off": -1.0},
      "ch7":  {"src": "btn_x", "mode": "momentary", "on": 1.0, "off": -1.0},
      "ch8":  {"src": "btn_y", "mode": "momentary", "on": 1.0, "off": -1.0}
    },
    "failsafe": {
      "ch1": 0.0, "ch2": 0.0, "ch3": -1.0, "ch4": 0.0,
      "ch5": -1.0, "ch6": -1.0, "ch7": -1.0, "ch8": -1.0
    }
  }
}
EOF
    echo "  + config.json loodud"
else
    echo "  config.json juba olemas, ei ülekirjuta"
fi

# ── Kokkuvõte ─────────────────────────────────────────────────────────────
RPI_IP=$(hostname -I | awk '{print $1}')

echo ""
echo "╔══════════════════════════════════════════════════════╗"
echo "║  Setup valmis! Taaskäivita:  sudo reboot            ║"
echo "╚══════════════════════════════════════════════════════╝"
echo ""
echo "Riistvara ühendused:"
echo "  PPM TX:    GPIO18 (pin 12) → Crossfire pin 1 (PPM)"
echo "  CRSF:      GPIO14 (pin 8)  → Crossfire pin 5 (1kΩ kaudu)"
echo "             GPIO15 (pin 10) → Crossfire pin 5 (otse)"
echo "  Foxeer VRX:GPIO4  (pin 7)  → VRX RX pad"
echo "             GPIO15 (pin 29) → VRX TX pad (valikuline)"
echo "  Video:     USB capture card → /dev/video0"
echo ""
echo "Pärast reboot:"
echo "  Web UI:    http://${RPI_IP}:8080"
echo "  Staatus:   journalctl -u $SERVICE -f"
echo "  Restart:   sudo systemctl restart $SERVICE"
