"""Shared hardware-access helpers for Vantage.

These functions read/write the Lenovo VPC platform sysfs attributes and the
touchpad kernel-input device. The write helpers are used by the privileged
helper (vantage_helper.py); reads are used directly by the client and are
unprivileged. Writes require root.
"""
import glob
import os

VPC_GLOB = "/sys/bus/platform/devices/VPC2004:*"

# Feature key -> VPC sysfs attribute filename.
# Note: camera_power is intentionally omitted. On some models (e.g. Yoga Pro 7i
# Gen 11) the bit holds its value but does NOT actually gate the camera — that's
# done by a hardware privacy key/EC — so exposing a software toggle is misleading.
VPC_ATTRS = {
    "conservation_mode": "conservation_mode",
    "usb_charging": "usb_charging",
    "fan_mode": "fan_mode",
    "fn_lock": "fn_lock",
}

# Keyboard-backlight LED (Lenovo platform LED, e.g. platform::kbd_backlight).
KBD_LED_GLOB = "/sys/class/leds/*kbd_backlight*"


def vpc_dir():
    """Return the resolved VPC2004 device directory, or None if absent."""
    matches = glob.glob(VPC_GLOB)
    return matches[0] if matches else None


def vpc_path(attr):
    base = vpc_dir()
    if not base:
        return None
    path = os.path.join(base, attr)
    return path if os.path.exists(path) else None


def read_attr(attr):
    """Read a VPC attribute as a stripped string, or None if unavailable."""
    path = vpc_path(attr)
    if not path:
        return None
    try:
        with open(path) as fh:
            return fh.read().strip()
    except OSError:
        return None


def write_attr(attr, value):
    """Write a value to a VPC attribute. Requires root. Returns True on success."""
    path = vpc_path(attr)
    if not path:
        return False
    with open(path, "w") as fh:
        fh.write(str(value))
    return True


def touchpad_inhibit_path():
    """Locate the touchpad's kernel-input 'inhibited' attribute (Wayland-safe)."""
    for name_file in glob.glob("/sys/class/input/event*/device/name"):
        try:
            with open(name_file) as fh:
                name = fh.read().strip()
        except OSError:
            continue
        if "touchpad" in name.lower():
            return os.path.join(os.path.dirname(name_file), "inhibited")
    return None


def read_touchpad_inhibited():
    path = touchpad_inhibit_path()
    if not path or not os.path.exists(path):
        return None
    try:
        with open(path) as fh:
            return fh.read().strip()
    except OSError:
        return None


def write_touchpad_inhibited(value):
    path = touchpad_inhibit_path()
    if not path:
        return False
    with open(path, "w") as fh:
        fh.write("1" if value else "0")
    return True


DMI_DIR = "/sys/class/dmi/id"


def read_dmi(field):
    """Read a DMI/SMBIOS field (e.g. product_version). Returns None if missing.

    Note: *_serial and *_uuid fields are root-only (mode 0400); reading those
    requires running through the privileged helper.
    """
    try:
        with open(os.path.join(DMI_DIR, field)) as fh:
            val = fh.read().strip()
        return val or None
    except OSError:
        return None


def read_dmi_serial():
    """Read the system serial number (root-only). Returns None if unavailable."""
    return read_dmi("product_serial")


def read_fan_rpms():
    """Return [(label, rpm_int), ...] for every readable hwmon fan, or [].

    Lenovo laptops expose fan tachometers via a hwmon node (e.g.
    'lenovo_wmi_other' with fan1_input/fan2_input). Empty/non-numeric inputs
    (such as acpi_fan's stub) are skipped. Unprivileged.
    """
    fans = []
    for inp in sorted(glob.glob("/sys/class/hwmon/hwmon*/fan*_input")):
        try:
            with open(inp) as fh:
                txt = fh.read().strip()
            rpm = int(txt)
        except (OSError, ValueError):
            continue
        label = None
        try:
            with open(inp[:-len("_input")] + "_label") as fh:
                label = fh.read().strip() or None
        except OSError:
            pass
        fans.append((label, rpm))
    return fans


BATTERY_GLOB = "/sys/class/power_supply/BAT*"


def _read_int(path):
    try:
        with open(path) as fh:
            return int(fh.read().strip())
    except (OSError, ValueError):
        return None


def read_battery():
    """Return a dict of battery health/status, or None if no battery.

    health_pct = energy_full / energy_full_design (charge_* on batteries that
    report in charge units). All unprivileged sysfs reads.
    """
    matches = sorted(glob.glob(BATTERY_GLOB))
    base = matches[0] if matches else None
    if not base:
        return None
    info = {}
    for full, design in (("energy_full", "energy_full_design"),
                         ("charge_full", "charge_full_design")):
        f = _read_int(os.path.join(base, full))
        d = _read_int(os.path.join(base, design))
        if f and d:
            info["health_pct"] = f / d * 100.0
            break
    cyc = _read_int(os.path.join(base, "cycle_count"))
    if cyc is not None:
        info["cycle_count"] = cyc
    for key in ("capacity", "status"):
        try:
            with open(os.path.join(base, key)) as fh:
                info[key] = fh.read().strip()
        except OSError:
            pass
    return info or None


def kbd_led_dir():
    """Return the keyboard-backlight LED directory, or None if absent."""
    matches = glob.glob(KBD_LED_GLOB)
    return matches[0] if matches else None


def read_kbd_backlight():
    """Return (brightness, max_brightness) as strings, or (None, None)."""
    base = kbd_led_dir()
    if not base:
        return None, None
    try:
        with open(os.path.join(base, "brightness")) as fh:
            cur = fh.read().strip()
        with open(os.path.join(base, "max_brightness")) as fh:
            mx = fh.read().strip()
        return cur, mx
    except OSError:
        return None, None


def write_kbd_backlight(value):
    """Set the keyboard-backlight brightness. Requires root. Clamped to [0, max]."""
    base = kbd_led_dir()
    if not base:
        return False
    try:
        with open(os.path.join(base, "max_brightness")) as fh:
            mx = int(fh.read().strip())
    except (OSError, ValueError):
        mx = None
    level = int(value)
    if level < 0:
        level = 0
    if mx is not None and level > mx:
        level = mx
    with open(os.path.join(base, "brightness"), "w") as fh:
        fh.write(str(level))
    return True
