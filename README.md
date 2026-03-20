# MSI BatteryGuard

A minimal, modern Linux GUI for controlling the battery charge threshold on **MSI Thin A15 B7UCX** only.

## What it does

Sets the maximum charge level your battery will reach. Keeping it at 60–80% significantly extends long-term battery lifespan. The setting is written directly to the **EC microcontroller** and **persists across reboots** and OS reinstalls — exactly like MSI Center on Windows.

## Quick start

Follow **INSTALL.md** step by step, then:

```bash
python3 msi-batteryguard.py
```

## How it works

```
Slider → Apply button → writes to /sys/class/power_supply/BAT0/charge_control_end_threshold
                                    ↓
                         msi-ec kernel module → EC microcontroller (stored in firmware)
```

## Usage

| Control | Action |
|---|---|
| Slider | Select your desired charge limit (20–100%) |
| **Apply Threshold** | Write the selected value to the EC |
| **Restore to 100%** | Remove the limit (full charging) |

## Recommended thresholds

| Use case | Threshold |
|---|---|
| Daily desktop use (plugged in often) | **60–70%** |
| Mixed use | **80%** |
| Travel / away from power | **100%** |

## Requirements

- Linux kernel module: `msi-ec` (see INSTALL.md)
- Python 3.10+
- `customtkinter` (`pip install customtkinter`)

## Files

| File | Purpose |
|---|---|
| `msi-batteryguard.py` | Main application |
| `batteryguard.desktop` | App menu entry |
| `99-msi-battery.rules` | udev rule for passwordless writes |
| `INSTALL.md` | Full setup guide |
# MSI-batteryguard-for-Thin-A15-B7UCX
