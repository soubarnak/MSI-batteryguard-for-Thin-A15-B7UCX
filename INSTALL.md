# MSI BatteryGuard – Installation Guide

## Target Hardware
**MSI Thin A15 B7UCX** (AMD Ryzen 7000 series)

---

## Step 1 – Install Build Dependencies

```bash
sudo apt update
sudo apt install -y git dkms linux-headers-$(uname -r) python3-pip
```

> On Arch/Manjaro: `sudo pacman -S git dkms linux-headers python`
> On Fedora: `sudo dnf install git dkms kernel-devel python3-pip`

---

## Step 2 – Install the msi-ec Kernel Module (via DKMS)

```bash
git clone https://github.com/BeardOverflow/msi-ec.git
cd msi-ec
sudo apt install -y linux-headers-$(uname -r)   # also triggers DKMS auto-build
# If DKMS didn't auto-build during headers install, run:
sudo make dkms-install
```

This installs the upstream DKMS module which supports `16RKIMS1.111` (your EC firmware).
It lives in `updates/dkms/` which takes precedence over the outdated built-in kernel module.
DKMS rebuilds it automatically on every kernel update.

### Load the module now (without rebooting)

```bash
sudo modprobe -r msi_ec 2>/dev/null; sudo modprobe msi_ec
```

### Verify it loaded and found your EC

```bash
dmesg | grep msi_ec | tail -5
ls /sys/class/power_supply/BAT1/charge_control_end_threshold
cat /sys/class/power_supply/BAT1/charge_control_end_threshold
# Should print 60 (MSI default battery care threshold)
```

### Make it load on every boot

```bash
echo "msi-ec" | sudo tee /etc/modules-load.d/msi-ec.conf
```

---

## Step 3 – EC ID (MSI Thin A15 B7UCX)

Your laptop's EC firmware ID is **`16RKIMS1.111`**. This is confirmed supported
by the upstream DKMS module (CONF_G2_6, charge register `0xd7`).

Verify the DKMS version is active (not the outdated built-in):

```bash
modinfo msi_ec | grep filename
# Should show: .../updates/dkms/msi-ec.ko.xz   (NOT kernel/drivers/...)
```

---

## Step 4 – Install udev Rule (write without sudo every time)

```bash
sudo cp 99-msi-battery.rules /etc/udev/rules.d/
sudo udevadm control --reload-rules
sudo udevadm trigger
```

Verify permissions:

```bash
ls -l /sys/class/power_supply/BAT0/charge_control_end_threshold
# Should be writable by group 'plugdev' or your user
```

Add yourself to the `plugdev` group if needed:

```bash
sudo usermod -aG plugdev $USER
# Then log out and back in
```

---

## Step 5 – Install Python Dependencies

```bash
pip3 install --user customtkinter pillow
```

---

## Step 6 – Install the App

```bash
# Copy desktop entry
cp batteryguard.desktop ~/.local/share/applications/

# Make the script executable
chmod +x msi-batteryguard.py

# Optional: install system-wide
sudo cp msi-batteryguard.py /usr/local/bin/msi-batteryguard
```

---

## Step 7 – Run

```bash
python3 msi-batteryguard.py
```

Or launch from your application menu: **MSI BatteryGuard**

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `lsmod` shows no msi_ec | Run `sudo modprobe msi-ec` and check `dmesg` |
| Threshold file not found | Module loaded but EC not supported – check dmesg |
| Permission denied writing threshold | udev rule not applied – repeat Step 4 |
| App shows "BAT path not found" | Run `ls /sys/class/power_supply/` and report |
