#!/usr/bin/env bash
# MSI BatteryGuard – Ubuntu/Debian Installer
# Automates INSTALL.md steps 1–6 for MSI Thin A15 B7UCX (and compatible MSI laptops)
set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'

info()    { echo -e "${CYAN}[INFO]${NC}  $*"; }
ok()      { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}  $*"; }
die()     { echo -e "${RED}[ERROR]${NC} $*" >&2; exit 1; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo -e "${CYAN}"
echo "  ╔══════════════════════════════════════╗"
echo "  ║   MSI BatteryGuard – Installer       ║"
echo "  ║   Ubuntu / Debian                    ║"
echo "  ╚══════════════════════════════════════╝"
echo -e "${NC}"

# ── Sanity checks ─────────────────────────────────────────────────────────────

[[ "$EUID" -ne 0 ]] || die "Do NOT run this script as root. It will call sudo when needed."
command -v apt-get &>/dev/null || die "apt-get not found. This installer targets Ubuntu/Debian only."

# ── Step 1: Build dependencies ────────────────────────────────────────────────

info "Step 1/6 – Installing build dependencies…"
sudo apt-get update -qq
sudo apt-get install -y git dkms "linux-headers-$(uname -r)" python3-pip python3-tk
ok "Build dependencies installed."

# ── Step 2: msi-ec DKMS kernel module ────────────────────────────────────────

info "Step 2/6 – Installing msi-ec kernel module via DKMS…"

MSI_EC_DIR="$SCRIPT_DIR/msi-ec-src"

if [[ ! -d "$MSI_EC_DIR/.git" ]]; then
    info "  Cloning msi-ec repository…"
    git clone --depth=1 https://github.com/BeardOverflow/msi-ec.git "$MSI_EC_DIR"
else
    info "  msi-ec source already present, pulling latest…"
    git -C "$MSI_EC_DIR" pull --ff-only
fi

cd "$MSI_EC_DIR"
sudo make dkms-install
cd "$SCRIPT_DIR"

# Load the module now (don't require a reboot)
info "  Loading msi_ec module…"
sudo modprobe -r msi_ec 2>/dev/null || true
sudo modprobe msi_ec && ok "msi_ec module loaded." || warn "Module load failed – a reboot may be required."

# Persist across boots
echo "msi-ec" | sudo tee /etc/modules-load.d/msi-ec.conf >/dev/null
ok "msi-ec will load automatically on every boot."

# ── Step 3: Verify EC detection ───────────────────────────────────────────────

info "Step 3/6 – Verifying EC detection…"
if dmesg | grep -q "msi_ec"; then
    ok "msi_ec detected in dmesg."
else
    warn "msi_ec not seen in dmesg – module may need a reboot to initialise."
fi

BAT_PATH=""
for p in /sys/class/power_supply/BAT0 /sys/class/power_supply/BAT1; do
    if [[ -f "$p/charge_control_end_threshold" ]]; then
        BAT_PATH="$p"
        break
    fi
done

if [[ -n "$BAT_PATH" ]]; then
    THRESHOLD=$(cat "$BAT_PATH/charge_control_end_threshold")
    ok "Battery found at $BAT_PATH  (current threshold: ${THRESHOLD}%)"
else
    warn "charge_control_end_threshold not found yet – may appear after reboot."
fi

# ── Step 4: udev rule ─────────────────────────────────────────────────────────

info "Step 4/6 – Installing udev rule…"
sudo cp "$SCRIPT_DIR/99-msi-battery.rules" /etc/udev/rules.d/
sudo udevadm control --reload-rules
sudo udevadm trigger
ok "udev rule installed."

# Add user to plugdev group
if ! groups "$USER" | grep -q '\bplugdev\b'; then
    info "  Adding $USER to the 'plugdev' group…"
    sudo usermod -aG plugdev "$USER"
    warn "You must log out and back in (or run: newgrp plugdev) for group membership to take effect."
else
    ok "$USER is already in the 'plugdev' group."
fi

# ── Step 5: Python dependencies ───────────────────────────────────────────────

info "Step 5/6 – Installing Python dependencies…"
pip3 install --user customtkinter pillow
ok "Python packages installed."

# ── Step 6: Install the app ───────────────────────────────────────────────────

info "Step 6/6 – Installing MSI BatteryGuard…"

# Install script system-wide
sudo cp "$SCRIPT_DIR/msi-batteryguard.py" /usr/local/bin/msi-batteryguard
sudo chmod +x /usr/local/bin/msi-batteryguard

# Install desktop entry for the current user
mkdir -p "$HOME/.local/share/applications"
cp "$SCRIPT_DIR/batteryguard.desktop" "$HOME/.local/share/applications/"
ok "App installed to /usr/local/bin/msi-batteryguard"
ok "Desktop entry installed to ~/.local/share/applications/"

# ── Done ──────────────────────────────────────────────────────────────────────

echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║  Installation complete!                          ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════╝${NC}"
echo ""
echo "  Run the app:     python3 /usr/local/bin/msi-batteryguard"
echo "  Or launch from:  Applications menu → MSI BatteryGuard"
echo ""

if groups "$USER" | grep -qv '\bplugdev\b' 2>/dev/null; then
    warn "Remember to log out and back in so the plugdev group takes effect."
fi
