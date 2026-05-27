#!/bin/bash
# Quest FPV Ground Station — RPi5 setup
# Käivita värske Raspberry Pi OS Bookworm (64-bit) peal
# Kasutus: bash setup_rpi5.sh

set -e

REPO_URL="https://github.com/RauntsEsT/quest-fpv-groundstation.git"
INSTALL_DIR="$HOME/quest-fpv-groundstation"
SERVICE="quest-groundstation"
CONFIG="/boot/firmware/config.txt"
CMDLINE="/boot/firmware/cmdline.txt"

echo "=== Quest FPV Ground Station — RPi5 Setup ==="

# ── 1. Süsteemi uuendamine ────────────────────────────────────────────────────
echo ""
echo "[1/6] Süsteemi uuendamine..."
sudo apt-get update -qq
sudo apt-get upgrade -y -qq

# ── 2. Süsteemipaketid ────────────────────────────────────────────────────────
echo "[2/6] Pakettide paigaldamine (ffmpeg, v4l-utils, python3-venv, git)..."
sudo apt-get install -y -qq \
    git \
    python3-pip \
    python3-venv \
    ffmpeg \
    v4l-utils \
    libv4l-dev

# ── 3. Repo kloonamine / uuendamine ──────────────────────────────────────────
echo "[3/6] Repo allalaadimine..."
if [ -d "$INSTALL_DIR/.git" ]; then
    echo "  Repo juba olemas, tõmban uuendused..."
    git -C "$INSTALL_DIR" pull --ff-only
else
    git clone "$REPO_URL" "$INSTALL_DIR"
fi

# ── 4. Python venv + pip paketid ─────────────────────────────────────────────
echo "[4/6] Python venv + paketid..."
python3 -m venv "$INSTALL_DIR/venv"
"$INSTALL_DIR/venv/bin/pip" install -q --upgrade pip
"$INSTALL_DIR/venv/bin/pip" install -q -r "$INSTALL_DIR/groundstation/requirements.txt"

# ── 5. UART seadistus ELRS jaoks (RPi5, /dev/ttyAMA0) ────────────────────────
echo "[5/6] UART seadistamine..."

# enable_uart=1 — aktiveerib GPIO14(TX)/GPIO15(RX) = /dev/ttyAMA0
if ! grep -q "^enable_uart=1" "$CONFIG"; then
    echo "enable_uart=1" | sudo tee -a "$CONFIG" > /dev/null
    echo "  + enable_uart=1 lisatud config.txt-sse"
fi

# dtoverlay=uart0 — tagab et UART0 on GPIO14/15 peal (RPi5 jaoks vajalik)
if ! grep -q "^dtoverlay=uart0" "$CONFIG"; then
    echo "dtoverlay=uart0" | sudo tee -a "$CONFIG" > /dev/null
    echo "  + dtoverlay=uart0 lisatud config.txt-sse"
fi

# Eemalda serial konsool cmdline.txt-st (et ELRS saaks porti kasutada)
if grep -q "console=serial0" "$CMDLINE"; then
    sudo sed -i 's/console=serial0,[0-9]* //' "$CMDLINE"
    echo "  - serial0 konsool eemaldatud cmdline.txt-st"
fi

# Lisa kasutaja õigete gruppidesse
sudo usermod -a -G dialout,video "$USER"
echo "  Kasutaja $USER lisatud: dialout, video"

# ── 6. Systemd autostart teenus ──────────────────────────────────────────────
echo "[6/6] Systemd teenuse loomine..."

sudo tee /etc/systemd/system/${SERVICE}.service > /dev/null << EOF
[Unit]
Description=Quest FPV Ground Station
After=network.target
Wants=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$INSTALL_DIR/groundstation
ExecStart=$INSTALL_DIR/venv/bin/python3 main.py
Restart=on-failure
RestartSec=5
StandardOutput=journal
StandardError=journal
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable "$SERVICE"

# ── Lõpp ─────────────────────────────────────────────────────────────────────
RPI_IP=$(hostname -I | awk '{print $1}')

echo ""
echo "╔══════════════════════════════════════════════════════╗"
echo "║        Setup valmis! Taaskäivita RPi:                ║"
echo "║                                                      ║"
echo "║   sudo reboot                                        ║"
echo "║                                                      ║"
echo "║  Pärast reboot käivitub teenus automaatselt.         ║"
echo "╚══════════════════════════════════════════════════════╝"
echo ""
echo "Kasulikud käsud pärast reboot:"
echo "  sudo systemctl status $SERVICE     # staatus"
echo "  journalctl -u $SERVICE -f          # live logid"
echo "  sudo systemctl restart $SERVICE    # taaskäivitus"
echo ""
echo "Web UI:"
echo "  http://${RPI_IP}:8080              # RPi ekraan / Quest brauser"
echo ""
echo "Riistvara:"
echo "  ELRS TX:    /dev/ttyAMA0 @ 420000 baud (GPIO14=TX, GPIO15=RX)"
echo "  Video:      /dev/video0  (USB capture card)"
echo "  Controller: UDP port 5005 (Quest saadab siia)"
echo "  Video stream: UDP port 5006 (Quest võtab siit)"
