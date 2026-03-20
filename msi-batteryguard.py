#!/usr/bin/env python3
"""
MSI BatteryGuard – Battery charge threshold controller for MSI laptops on Linux.
Requires the msi-ec kernel module: https://github.com/BeardOverflow/msi-ec
"""

import os
import sys
import subprocess
import customtkinter as ctk
from pathlib import Path

# ─── Constants ────────────────────────────────────────────────────────────────

APP_NAME       = "MSI BatteryGuard"
APP_VERSION    = "1.0.0"
SYSFS_BASES    = [
    "/sys/class/power_supply/BAT0",
    "/sys/class/power_supply/BAT1",
]
AUTOSTART_FILE = Path.home() / ".config/autostart/msi-batteryguard.desktop"
SCRIPT_PATH    = Path(os.path.abspath(__file__))
REFRESH_MS     = 5000   # live battery level poll interval (5 seconds)

# ─── Autostart helpers ────────────────────────────────────────────────────────

def is_autostart_enabled() -> bool:
    return AUTOSTART_FILE.exists()

def enable_autostart():
    AUTOSTART_FILE.parent.mkdir(parents=True, exist_ok=True)
    AUTOSTART_FILE.write_text(
        "[Desktop Entry]\n"
        "Type=Application\n"
        f"Name={APP_NAME}\n"
        f"Exec=/usr/bin/python3 {SCRIPT_PATH}\n"
        "Icon=battery\n"
        "Terminal=false\n"
        "Hidden=false\n"
        "X-GNOME-Autostart-enabled=true\n"
    )

def disable_autostart():
    AUTOSTART_FILE.unlink(missing_ok=True)

# ─── Battery path detection ───────────────────────────────────────────────────

def find_battery_path() -> Path | None:
    """Return the first battery sysfs path that has a charge_control_end_threshold file."""
    for base in SYSFS_BASES:
        p = Path(base)
        if (p / "charge_control_end_threshold").exists():
            return p
    return None

def read_sysfs(path: Path) -> str | None:
    try:
        return path.read_text().strip()
    except Exception:
        return None

def write_threshold(bat_path: Path, value: int) -> tuple[bool, str]:
    """
    Write threshold value to sysfs.
    First tries direct write (works if udev rule is in place),
    then falls back to pkexec for privilege escalation.
    """
    threshold_file = str(bat_path / "charge_control_end_threshold")

    # Try direct write first (udev rule grants permission)
    try:
        (bat_path / "charge_control_end_threshold").write_text(str(value))
        return True, "direct"
    except PermissionError:
        pass

    # Fallback: pkexec (PolicyKit – shows a native auth dialog, no terminal)
    try:
        result = subprocess.run(
            ["pkexec", "tee", threshold_file],
            input=str(value),
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            return True, "pkexec"
        return False, result.stderr.strip() or "pkexec failed"
    except FileNotFoundError:
        try:
            result = subprocess.run(
                ["sudo", "tee", threshold_file],
                input=str(value),
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0:
                return True, "sudo"
            return False, "Permission denied – see INSTALL.md Step 4"
        except Exception as e:
            return False, str(e)
    except subprocess.TimeoutExpired:
        return False, "Auth dialog timed out"
    except Exception as e:
        return False, str(e)

# ─── GUI Application ──────────────────────────────────────────────────────────

class BatteryGuardApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self._dark_mode = True
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.title(APP_NAME)
        self.geometry("460x510")
        self.resizable(False, False)

        self.bat_path = find_battery_path()
        self._build_ui()
        self._refresh_info()
        self._schedule_refresh()

    # ── UI construction ────────────────────────────────────────────────────

    def _build_ui(self):
        # ── Header ────────────────────────────────────────────────────────
        self.header = ctk.CTkFrame(self, fg_color="#1a1a2e", corner_radius=0)
        self.header.pack(fill="x")

        # Title row with theme toggle on the right
        title_row = ctk.CTkFrame(self.header, fg_color="transparent")
        title_row.pack(fill="x", padx=18, pady=(14, 2))

        ctk.CTkLabel(
            title_row,
            text="⚡ MSI BatteryGuard",
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color="#00d4ff",
        ).pack(side="left")

        self.btn_theme = ctk.CTkButton(
            title_row,
            text="☀ Light",
            width=72,
            height=26,
            font=ctk.CTkFont(size=11),
            fg_color="#2a2a3e",
            hover_color="#3a3a55",
            border_color="#444466",
            border_width=1,
            corner_radius=6,
            command=self._toggle_theme,
        )
        self.btn_theme.pack(side="right")

        ctk.CTkLabel(
            self.header,
            text="Charge threshold controller  •  MSI Thin A15 B7UCX",
            font=ctk.CTkFont(size=11),
            text_color="#888888",
        ).pack(pady=(0, 14))

        # ── Status card ───────────────────────────────────────────────────
        card = ctk.CTkFrame(self, corner_radius=12)
        card.pack(fill="x", padx=24, pady=(16, 8))

        row1 = ctk.CTkFrame(card, fg_color="transparent")
        row1.pack(fill="x", padx=16, pady=(12, 4))

        ctk.CTkLabel(row1, text="Battery", font=ctk.CTkFont(size=12),
                     text_color="#aaaaaa").pack(side="left")
        self.lbl_bat_path = ctk.CTkLabel(row1, text="Detecting…",
                                          font=ctk.CTkFont(size=12, weight="bold"))
        self.lbl_bat_path.pack(side="right")

        row2 = ctk.CTkFrame(card, fg_color="transparent")
        row2.pack(fill="x", padx=16, pady=4)

        ctk.CTkLabel(row2, text="Current charge", font=ctk.CTkFont(size=12),
                     text_color="#aaaaaa").pack(side="left")
        self.lbl_current = ctk.CTkLabel(row2, text="–",
                                         font=ctk.CTkFont(size=12, weight="bold"))
        self.lbl_current.pack(side="right")

        row3 = ctk.CTkFrame(card, fg_color="transparent")
        row3.pack(fill="x", padx=16, pady=(4, 12))

        ctk.CTkLabel(row3, text="Active threshold", font=ctk.CTkFont(size=12),
                     text_color="#aaaaaa").pack(side="left")
        self.lbl_threshold = ctk.CTkLabel(row3, text="–",
                                           font=ctk.CTkFont(size=12, weight="bold"),
                                           text_color="#00d4ff")
        self.lbl_threshold.pack(side="right")

        # ── Slider section ────────────────────────────────────────────────
        slider_frame = ctk.CTkFrame(self, fg_color="transparent")
        slider_frame.pack(fill="x", padx=24, pady=(8, 0))

        ctk.CTkLabel(slider_frame, text="Set charge limit",
                     font=ctk.CTkFont(size=13, weight="bold")).pack(anchor="w")

        self.slider_value_var = ctk.IntVar(value=80)

        slider_row = ctk.CTkFrame(slider_frame, fg_color="transparent")
        slider_row.pack(fill="x", pady=(6, 0))

        ctk.CTkLabel(slider_row, text="20", text_color="#666666",
                     font=ctk.CTkFont(size=11)).pack(side="left")

        self.slider = ctk.CTkSlider(
            slider_row,
            from_=20,
            to=100,
            number_of_steps=80,
            variable=self.slider_value_var,
            command=self._on_slider_move,
            button_color="#00d4ff",
            button_hover_color="#00aacc",
            progress_color="#00d4ff",
        )
        self.slider.pack(side="left", padx=10, fill="x", expand=True)

        ctk.CTkLabel(slider_row, text="100", text_color="#666666",
                     font=ctk.CTkFont(size=11)).pack(side="left")

        # Large live value display
        self.lbl_slider_val = ctk.CTkLabel(
            slider_frame,
            text="80%",
            font=ctk.CTkFont(size=36, weight="bold"),
            text_color="#00d4ff",
        )
        self.lbl_slider_val.pack(pady=(4, 0))

        ctk.CTkLabel(
            slider_frame,
            text="Recommended: 60–80% for daily use  •  100% for travel",
            font=ctk.CTkFont(size=10),
            text_color="#666666",
        ).pack(pady=(0, 8))

        # ── Buttons ───────────────────────────────────────────────────────
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=24, pady=(4, 8))

        self.btn_apply = ctk.CTkButton(
            btn_frame,
            text="Apply Threshold",
            font=ctk.CTkFont(size=14, weight="bold"),
            height=44,
            fg_color="#00d4ff",
            hover_color="#00aacc",
            text_color="#000000",
            corner_radius=10,
            command=self._apply_threshold,
        )
        self.btn_apply.pack(side="left", fill="x", expand=True, padx=(0, 6))

        self.btn_restore = ctk.CTkButton(
            btn_frame,
            text="Restore to 100%",
            font=ctk.CTkFont(size=13),
            height=44,
            fg_color="#2b2b3b",
            hover_color="#3a3a50",
            border_color="#555555",
            border_width=1,
            corner_radius=10,
            command=self._restore_full,
        )
        self.btn_restore.pack(side="left", fill="x", expand=True, padx=(6, 0))

        # ── Status bar ────────────────────────────────────────────────────
        self.lbl_status = ctk.CTkLabel(
            self,
            text="Ready.",
            font=ctk.CTkFont(size=11),
            text_color="#888888",
            wraplength=420,
        )
        self.lbl_status.pack(pady=(0, 4))

        # ── Bottom row: autostart + theme label ───────────────────────────
        bottom = ctk.CTkFrame(self, fg_color="transparent")
        bottom.pack(fill="x", padx=24, pady=(0, 12))

        self.autostart_var = ctk.BooleanVar(value=is_autostart_enabled())
        ctk.CTkCheckBox(
            bottom,
            text="Launch at login",
            variable=self.autostart_var,
            command=self._toggle_autostart,
            font=ctk.CTkFont(size=11),
            text_color="#888888",
            checkbox_width=16,
            checkbox_height=16,
            checkmark_color="#00d4ff",
            fg_color="#00d4ff",
            hover_color="#00aacc",
            border_color="#555555",
        ).pack(side="left")

        self.lbl_refresh = ctk.CTkLabel(
            bottom,
            text="● live",
            font=ctk.CTkFont(size=10),
            text_color="#444444",
        )
        self.lbl_refresh.pack(side="right")

    # ── Theme toggle ───────────────────────────────────────────────────────

    def _toggle_theme(self):
        self._dark_mode = not self._dark_mode
        if self._dark_mode:
            ctk.set_appearance_mode("dark")
            self.btn_theme.configure(text="☀ Light")
            self.header.configure(fg_color="#1a1a2e")
        else:
            ctk.set_appearance_mode("light")
            self.btn_theme.configure(text="🌙 Dark")
            self.header.configure(fg_color="#dde8f5")

    # ── Live refresh ───────────────────────────────────────────────────────

    def _schedule_refresh(self):
        """Poll battery capacity every REFRESH_MS milliseconds."""
        self._poll_capacity()
        self.after(REFRESH_MS, self._schedule_refresh)

    def _poll_capacity(self):
        """Update only the charge label — lightweight, non-disruptive."""
        if not self.bat_path:
            return
        cap = read_sysfs(self.bat_path / "capacity")
        status = read_sysfs(self.bat_path / "status") or ""
        if cap:
            icon = {"Charging": "⚡", "Full": "✓", "Discharging": "▼"}.get(status, "")
            self.lbl_current.configure(text=f"{icon} {cap}%".strip())
        # Flash the live indicator
        self.lbl_refresh.configure(text_color="#00cc88")
        self.after(400, lambda: self.lbl_refresh.configure(text_color="#444444"))

    # ── Event handlers ─────────────────────────────────────────────────────

    def _on_slider_move(self, value):
        self.lbl_slider_val.configure(text=f"{int(value)}%")

    def _apply_threshold(self):
        value = self.slider_value_var.get()
        self._set_threshold(value)

    def _restore_full(self):
        self.slider_value_var.set(100)
        self.lbl_slider_val.configure(text="100%")
        self._set_threshold(100)

    def _set_threshold(self, value: int):
        if not self.bat_path:
            self._status("✗ Battery sysfs path not found. Is msi-ec loaded?", error=True)
            return

        self.btn_apply.configure(state="disabled", text="Applying…")
        self.btn_restore.configure(state="disabled")
        self.update()

        ok, method = write_threshold(self.bat_path, value)

        self.btn_apply.configure(state="normal", text="Apply Threshold")
        self.btn_restore.configure(state="normal")

        if ok:
            msg = (
                f"✓ Threshold set to {value}% – saved in EC microcontroller"
                f" (via {method}). Persists across OS reboots."
            )
            self._status(msg, error=False)
            self._refresh_info()
        else:
            self._status(f"✗ Failed to write threshold: {method}", error=True)

    def _refresh_info(self):
        if not self.bat_path:
            self.lbl_bat_path.configure(text="Not found", text_color="#ff4444")
            self.lbl_current.configure(text="–")
            self.lbl_threshold.configure(text="–")
            self._status(
                "✗ No supported battery sysfs found. "
                "Load msi-ec: sudo modprobe msi-ec",
                error=True,
            )
            self.btn_apply.configure(state="disabled")
            self.btn_restore.configure(state="disabled")
            return

        self.lbl_bat_path.configure(text=self.bat_path.name, text_color="#00ff88")

        cap = read_sysfs(self.bat_path / "capacity")
        status = read_sysfs(self.bat_path / "status") or ""
        if cap:
            icon = {"Charging": "⚡", "Full": "✓", "Discharging": "▼"}.get(status, "")
            self.lbl_current.configure(text=f"{icon} {cap}%".strip())
        else:
            self.lbl_current.configure(text="–")

        thr = read_sysfs(self.bat_path / "charge_control_end_threshold")
        if thr:
            self.lbl_threshold.configure(text=f"{thr}%")
            try:
                self.slider_value_var.set(int(thr))
                self.lbl_slider_val.configure(text=f"{thr}%")
            except ValueError:
                pass
        else:
            self.lbl_threshold.configure(text="–")

    def _toggle_autostart(self):
        if self.autostart_var.get():
            enable_autostart()
            self._status("✓ Will launch automatically at login.", error=False)
        else:
            disable_autostart()
            self._status("Autostart disabled.", error=False)

    def _status(self, msg: str, error: bool = False):
        color = "#ff6666" if error else "#00cc88"
        self.lbl_status.configure(text=msg, text_color=color)

# ─── Entry point ─────────────────────────────────────────────────────────────

def main():
    if not any(Path(b).exists() for b in SYSFS_BASES):
        pass  # GUI will show the error

    app = BatteryGuardApp()
    app.mainloop()

if __name__ == "__main__":
    main()
