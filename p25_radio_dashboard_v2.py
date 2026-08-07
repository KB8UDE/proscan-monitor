import argparse
import csv
import ctypes
import json
import os
import queue
import re
import sys
import threading
import time
from dataclasses import dataclass, field
from typing import Optional

import tkinter as tk
from tkinter import ttk


APP_DIR = os.path.dirname(os.path.abspath(sys.executable if getattr(sys, "frozen", False) else __file__))
RESOURCE_DIR = getattr(sys, "_MEIPASS", APP_DIR)
CONFIG_PATH = os.path.join(APP_DIR, "p25_radio_dashboard_config.json")
LOGO_PATH = os.path.join(RESOURCE_DIR, "harris_logo_header.png")
ICON_DIR = os.path.join(RESOURCE_DIR, "icons")
SYSTEM_NAMES_PATH = os.path.join(APP_DIR, "DSDPlus.networks")
SITE_NAMES_PATH = os.path.join(APP_DIR, "DSDPlus.sites")

THEMES = {
    "dark": {
        "app_bg": "#121d21",
        "header_bg": "#d8dcde",
        "header_fg": "#0a0d0f",
        "panel_bg": "#121f24",
        "control_bg": "#ffffff",
        "panel_fg": "#f4f7f8",
        "muted_fg": "#d5dbdf",
        "table_bg": "#142126",
        "table_heading": "#17252b",
        "table_fg": "#eef2f3",
        "canvas_bg": "#121f24",
        "bar_track": "#304047",
        "home_bar": "#4a8ff0",
        "site_bar": "#5aa14d",
        "accent": "#2f7f36",
        "accent_alt": "#4b8ff0",
        "warning": "#9b6a16",
        "border": "#405058",
        "footer_bg": "#142126",
        "indicator_off_bg": "#25303a",
        "indicator_off_fg": "#aab6c0",
        "indicator_on_bg": "#2e7d4f",
        "indicator_on_fg": "#f3f7fa",
        "call_on_bg": "#9b6a16",
        "call_on_fg": "#fff4db",
    },
    "light": {
        "app_bg": "#f4f4f4",
        "header_bg": "#f4f4f4",
        "header_fg": "#151a1f",
        "panel_bg": "#ffffff",
        "control_bg": "#ffffff",
        "panel_fg": "#111820",
        "muted_fg": "#151a1f",
        "table_bg": "#ffffff",
        "table_heading": "#f2f2f2",
        "table_fg": "#172029",
        "canvas_bg": "#ffffff",
        "bar_track": "#cfcfcf",
        "home_bar": "#4a86de",
        "site_bar": "#55a055",
        "accent": "#348b3f",
        "accent_alt": "#2f65c8",
        "warning": "#b57918",
        "border": "#c9c9c9",
        "footer_bg": "#f4f4f4",
        "indicator_off_bg": "#d8dde2",
        "indicator_off_fg": "#3b4650",
        "indicator_on_bg": "#2f874f",
        "indicator_on_fg": "#ffffff",
        "call_on_bg": "#b57918",
        "call_on_fg": "#ffffff",
    },
}

SAMPLE_BLOCK = """Current Site Status:     LATCHED
Received Net Status:     TRUE (WACN 0xBEE00, SystemID 0x348)
Received RFSS Status:    TRUE (RFSS 0x03, SiteID 0x01)

Hunt Home Site Information:
Current site is:        RFSS 3 Site ID 1 LRA 0
Home Effective RSSI is:  -88dBm (raw value is -99dBm)
Current network is:      WACN BEE00 System ID 348
CC frequency is:         853662500
Current status is:        PREFERRED (+10dB)  VALID ALLOWED


01 WACN BEE00 SYS 348 SITE 0B LRA 00 RFSS 03 :***         :-120dBm (sample -120dBm) freq 773956250
02 WACN BEE00 SYS 348 SITE 03 LRA 00 RFSS 03 :***         :-122dBm (sample -123dBm) freq 774731250
03 WACN BEE00 SYS 348 SITE 1C LRA 00 RFSS 03 :***         :-121dBm (sample -123dBm) freq 771481250
04 WACN BEE00 SYS 348 SITE 30 LRA 00 RFSS 03 :****        :-113dBm (sample -114dBm) freq 774406250
05 WACN BEE00 SYS 348 SITE 0A LRA 00 RFSS 03 :****        :-119dBm (sample -121dBm) freq 772756250
06 WACN BEE00 SYS 348 SITE 09 LRA 00 RFSS 03 :***         :-120dBm (sample -120dBm) freq 774206250
07 WACN BEE00 SYS 348 SITE 24 LRA 00 RFSS 03 :****        :-111dBm (sample -111dBm) freq 773431250  effective -107dBm
08 WACN BEE00 SYS 348 SITE 52 LRA 00 RFSS 03 :***         :-123dBm (sample -124dBm) freq 853462500
"""


SITE_RE = re.compile(
    r"^\s*(?P<index>\d+)\s+WACN\s+(?P<wacn>[0-9A-Fa-f]+)\s+SYS\s+(?P<system>[0-9A-Fa-f]+)\s+"
    r"SITE\s+(?P<site>[0-9A-Fa-f]+)\s+LRA\s+(?P<lra>[0-9A-Fa-f]+)\s+RFSS\s+(?P<rfss>[0-9A-Fa-f]+)\s+"
    r":(?P<bars>\*+)\s*:\s*(?P<rssi>-?\d+)dBm\s+\(sample\s+(?P<sample>-?\d+)dBm\)\s+"
    r"freq\s+(?P<freq>\d+)(?:\s+effective\s+(?P<effective>-?\d+)dBm)?",
    re.IGNORECASE,
)

XG75_SITE_RE = re.compile(
    r"^\s*(?P<index>\d+)\s+SITE\s+(?P<site>[0-9A-Fa-f]+)\s+LRA\s+(?P<lra>[0-9A-Fa-f]+)\s+"
    r"RFSS\s+(?P<rfss>[0-9A-Fa-f]+)\s+SYS\s+(?P<system>[0-9A-Fa-f]+)\s+"
    r":(?P<bars>\*+)\s*:\s*(?P<rssi>-?\d+)dBm\s+\(sample\s+(?P<sample>-?\d+)dBm\)\s+"
    r"freq\s+(?P<freq>\d+)(?:\s+effective\s+(?P<effective>-?\d+)dBm)?",
    re.IGNORECASE,
)

NO_SIGNAL_SITE_RE = re.compile(
    r"^\s*(?P<index>\d+)\s+WACN\s+(?P<wacn>[0-9A-Fa-f]+)\s+SYS\s+(?P<system>[0-9A-Fa-f]+)\s+"
    r"SITE\s+(?P<site>[0-9A-Fa-f]+)\s+LRA\s+(?P<lra>[0-9A-Fa-f]+)\s+RFSS\s+(?P<rfss>[0-9A-Fa-f]+)\s+"
    r":(?P<bars>\**)\s*:\s*\*no signal\*\s*freq\s*(?P<freq>\d+)",
    re.IGNORECASE,
)

XG75_NO_SIGNAL_SITE_RE = re.compile(
    r"^\s*(?P<index>\d+)\s+SITE\s+(?P<site>[0-9A-Fa-f]+)\s+LRA\s+(?P<lra>[0-9A-Fa-f]+)\s+"
    r"RFSS\s+(?P<rfss>[0-9A-Fa-f]+)\s+SYS\s+(?P<system>[0-9A-Fa-f]+)\s+"
    r":(?P<bars>\**)\s*:\s*\*no signal\*\s*freq\s*(?P<freq>\d+)",
    re.IGNORECASE,
)

PROSCAN1_SITE_RE = re.compile(
    r"^\s*(?P<valid>VALID)?\s*(?P<index>\d+)\s+WACN\s+(?P<wacn>[0-9A-Fa-f]+)\s+SYS\s+(?P<system>[0-9A-Fa-f]+)\s+"
    r"SITE\s+(?P<site>[0-9A-Fa-f]+)\s+LRA\s+(?P<lra>[0-9A-Fa-f]+)\s+RFSS\s+(?P<rfss>[0-9A-Fa-f]+)\s+"
    r"(?P<allowed>ALLOWED|NOT ALLOWED)\s+(?P<site_class>FS|NET)\s+(?P<reality>REAL|OTHER)\s+(?P<rx>Rx|Tx)\s+"
    r"(?P<preference>NO PREFERENCE|PREFERRED)(?:\s+\([^)]+\))?\s+"
    r"(?:(?P<rssi>-?\d+)dBm\s+\(sample\s+(?P<sample>-?\d+)dBm\)\s+|(?P<no_signal>\*no signal\*))"
    r"freq\s*(?P<freq>\d+)(?:\s+effective\s+(?P<effective>-?\d+)dBm)?",
    re.IGNORECASE,
)

XG75_PROSCAN1_SITE_RE = re.compile(
    r"^\s*(?P<valid>VALID)?\s*(?P<index>\d+)\s+SITE\s+(?P<site>[0-9A-Fa-f]+)\s+LRA\s+(?P<lra>[0-9A-Fa-f]+)\s+"
    r"RFSS\s+(?P<rfss>[0-9A-Fa-f]+)\s+SYS\s+(?P<system>[0-9A-Fa-f]+)\s+"
    r"(?P<allowed>ALLOWED|NOT ALLOWED)\s+(?P<site_class>FS|NET)\s+(?P<reality>REAL|OTHER)\s+(?P<rx>Rx|Tx)\s+"
    r"(?P<preference>NO PREFERENCE|PREFERRED)(?:\s+\([^)]+\))?\s+"
    r"(?:(?P<rssi>-?\d+)dBm\s+\(sample\s+(?P<sample>-?\d+)dBm\)\s+|(?P<no_signal>\*no signal\*))"
    r"freq\s*(?P<freq>\d+)(?:\s+effective\s+(?P<effective>-?\d+)dBm)?",
    re.IGNORECASE,
)


@dataclass
class SiteReading:
    index: int
    wacn: str
    system_id: str
    site: str
    lra: str
    rfss: str
    radio_bars: int
    rssi: Optional[int]
    sample_rssi: Optional[int]
    frequency_hz: int
    effective_rssi: Optional[int] = None
    no_signal: bool = False
    valid: bool = False
    allowed: str = ""
    site_class: str = ""
    reality: str = ""
    rx: str = ""
    preference: str = ""


@dataclass
class RadioState:
    current_site_status: str = "Unknown"
    net_status: str = "Unknown"
    rfss_status: str = "Unknown"
    wacn: str = ""
    system_id: str = ""
    current_rfss: str = ""
    current_site: str = ""
    current_lra: str = ""
    home_effective_rssi: Optional[int] = None
    home_raw_rssi: Optional[int] = None
    control_channel_hz: Optional[int] = None
    current_status: str = ""
    current_valid: Optional[bool] = None
    ccscan: bool = False
    working_channel: bool = False
    preferred: bool = False
    last_good_rfss: str = ""
    last_good_site: str = ""
    last_good_lra: str = ""
    last_good_frequency_hz: Optional[int] = None
    trunked_only_error: bool = False
    sites: list[SiteReading] = field(default_factory=list)
    raw_text: str = ""
    updated_at: float = field(default_factory=time.time)


def hex_clean(value: str) -> str:
    return value.replace("0x", "").replace("0X", "").upper()


def hex_to_decimal_text(value: str) -> str:
    if not value:
        return "?"
    try:
        return str(int(value, 16))
    except ValueError:
        return value


def hex_prefixed_text(value: str) -> str:
    if not value:
        return "?"
    return f"0x{hex_clean(value)}"


def mhz(freq_hz: Optional[int]) -> str:
    if freq_hz is None or freq_hz == 4_294_967_295:
        return "Unknown"
    return f"{freq_hz / 1_000_000:.6f} MHz"


def dbm(value: Optional[int]) -> str:
    if value is None:
        return "Unknown"
    return f"{value} dBm"


def mhz_short(freq_hz: Optional[int]) -> str:
    if freq_hz is None or freq_hz == 4_294_967_295:
        return "Unknown"
    return f"{freq_hz / 1_000_000:.4f} MHz"


def site_display(site: str) -> str:
    if not site:
        return "SITE ?"
    return f"SITE {hex_to_decimal_text(site).zfill(2)}"


def rssi_quality(value: Optional[int]) -> str:
    if value is None:
        return ""
    if value >= -80:
        return "Very Good"
    if value >= -95:
        return "Good"
    if value >= -110:
        return "Fair"
    return "Weak"


def radio_bars_quality(bars: int, no_signal: bool = False) -> str:
    if no_signal:
        return "0%"
    if bars <= 0:
        return ""
    return f"{min(100, round((bars / 12) * 100))}%"


def rounded_rect(canvas: tk.Canvas, x1: int, y1: int, x2: int, y2: int, radius: int, **kwargs) -> None:
    points = [
        x1 + radius, y1,
        x2 - radius, y1,
        x2, y1,
        x2, y1 + radius,
        x2, y2 - radius,
        x2, y2,
        x2 - radius, y2,
        x1 + radius, y2,
        x1, y2,
        x1, y2 - radius,
        x1, y1 + radius,
        x1, y1,
    ]
    canvas.create_polygon(points, smooth=True, **kwargs)


class RoundedPanel(tk.Canvas):
    def __init__(self, parent: tk.Widget, radius: int = 7, **kwargs):
        super().__init__(parent, bd=0, highlightthickness=0, **kwargs)
        self.radius = radius
        self.panel_bg = "#ffffff"
        self.border = "#d0d0d0"
        self.inner = tk.Frame(self, bd=0, highlightthickness=0)
        self.inner_window = self.create_window(1, 1, anchor=tk.NW, window=self.inner)
        self.bind("<Configure>", lambda _event: self.redraw())

    def set_theme(self, outer_bg: str, panel_bg: str, border: str) -> None:
        self.panel_bg = panel_bg
        self.border = border
        self.configure(bg=outer_bg)
        self.inner.configure(bg=panel_bg)
        self.redraw()

    def redraw(self) -> None:
        width = max(self.winfo_width(), 4)
        height = max(self.winfo_height(), 4)
        self.delete("panel")
        rounded_rect(self, 0, 0, width - 1, height - 1, self.radius, fill=self.panel_bg, outline=self.border, width=1, tags="panel")
        self.tag_lower("panel")
        self.coords(self.inner_window, 1, 1)
        self.itemconfigure(self.inner_window, width=width - 2, height=height - 2)


def signal_text(site: SiteReading, value: Optional[int]) -> str:
    if site.no_signal:
        return "No signal"
    return dbm(value)


def site_key(site: SiteReading) -> tuple[str, str, str, str, str]:
    return (site.wacn, site.system_id, site.rfss, site.site, site.lra)


def parse_radio_block(text: str) -> RadioState:
    state = RadioState(raw_text=text, updated_at=time.time())

    if re.search(r"ProScan only works on trunked systems", text, re.IGNORECASE):
        state.current_site_status = "Not Trunked"
        state.net_status = "FALSE"
        state.rfss_status = "FALSE"
        state.trunked_only_error = True
        return state

    match = re.search(r"Current Site Status:\s*(.+)", text)
    if match:
        state.current_site_status = match.group(1).strip().title()

    match = re.search(r"Received Net Status:\s*(\w+)\s+\(WACN\s+0x([0-9A-Fa-f]+),\s*SystemID\s+0x([0-9A-Fa-f]+)\)", text)
    if match:
        state.net_status = match.group(1).strip().upper()
        state.wacn = hex_clean(match.group(2))
        state.system_id = hex_clean(match.group(3))
    else:
        match = re.search(r"Received Net Status:\s*(\w+)", text)
        if match:
            state.net_status = match.group(1).strip().upper()

    match = re.search(r"Received RFSS Status:\s*(\w+)\s+\(RFSS\s+0x([0-9A-Fa-f]+),\s*SiteID\s+0x([0-9A-Fa-f]+)\)", text)
    if match:
        state.rfss_status = match.group(1).strip().upper()
        state.current_rfss = hex_clean(match.group(2))
        state.current_site = hex_clean(match.group(3))
    else:
        match = re.search(r"Received RFSS Status:\s*(\w+)", text)
        if match:
            state.rfss_status = match.group(1).strip().upper()

    match = re.search(r"Current site is:\s*RFSS\s+([0-9A-Fa-f]+)\s+Site ID\s+([0-9A-Fa-f]+)\s+LRA\s+([0-9A-Fa-f]+)", text)
    if match:
        state.current_rfss = match.group(1).zfill(2).upper()
        state.current_site = match.group(2).zfill(2).upper()
        state.current_lra = match.group(3).zfill(2).upper()

    match = re.search(r"Home Effective RSSI is:\s*(-?\d+)dBm\s+\(raw value is\s+(-?\d+)dBm\)", text)
    if match:
        state.home_effective_rssi = int(match.group(1))
        state.home_raw_rssi = int(match.group(2))

    match = re.search(r"Current network is:\s*WACN\s+([0-9A-Fa-f]+)\s+System ID\s+([0-9A-Fa-f]+)", text)
    if match:
        state.wacn = hex_clean(match.group(1))
        state.system_id = hex_clean(match.group(2))

    match = re.search(r"CC frequency is:\s*(\d+)", text)
    if match:
        state.control_channel_hz = int(match.group(1))

    match = re.search(r"Current status is:\s*(.+)", text)
    if match:
        state.current_status = " ".join(match.group(1).split())

    state.ccscan = bool(re.search(r"\*+\s*CCSCAN\s*\*+", text, re.IGNORECASE))
    state.working_channel = bool(re.search(r"\*+\s*on working channel\s*\*+", text, re.IGNORECASE))
    state.preferred = "PREFERRED" in state.current_status.upper()
    status_words = state.current_status.upper()
    if "INVALID" in status_words:
        state.current_valid = False
    elif re.search(r"\bVALID\b", status_words):
        state.current_valid = True
    if state.net_status == "Unknown" and state.wacn and state.system_id:
        state.net_status = "TRUE"
    if state.rfss_status == "Unknown" and state.current_rfss and state.current_site:
        state.rfss_status = "TRUE"
    if state.current_site_status == "Unknown" and state.control_channel_hz is not None and not state.ccscan:
        state.current_site_status = "Latched"

    match = re.search(
        r"Last Good Site was:\s*RFSS\s+([0-9A-Fa-f]+)\s+Site ID\s+([0-9A-Fa-f]+)\s+LRA\s+([0-9A-Fa-f]+)\s+freq\s+(\d+)",
        text,
        re.IGNORECASE,
    )
    if match:
        state.last_good_rfss = hex_clean(match.group(1)).zfill(2)
        state.last_good_site = hex_clean(match.group(2)).zfill(2)
        state.last_good_lra = hex_clean(match.group(3)).zfill(2)
        state.last_good_frequency_hz = int(match.group(4))

    for line in text.splitlines():
        site_match = SITE_RE.match(line)
        xg75_site_match = XG75_SITE_RE.match(line)
        no_signal_match = NO_SIGNAL_SITE_RE.match(line)
        xg75_no_signal_match = XG75_NO_SIGNAL_SITE_RE.match(line)
        proscan1_match = PROSCAN1_SITE_RE.match(line)
        xg75_proscan1_match = XG75_PROSCAN1_SITE_RE.match(line)
        if not site_match and not xg75_site_match and not no_signal_match and not xg75_no_signal_match and not proscan1_match and not xg75_proscan1_match:
            continue
        groups = (site_match or xg75_site_match or no_signal_match or xg75_no_signal_match or proscan1_match or xg75_proscan1_match).groupdict()
        wacn = hex_clean(groups.get("wacn") or state.wacn)
        system_id = hex_clean(groups["system"])
        site = hex_clean(groups["site"]).zfill(2)
        lra = hex_clean(groups["lra"]).zfill(2)
        rfss = hex_clean(groups["rfss"]).zfill(2)
        frequency_hz = int(groups["freq"])
        is_placeholder = wacn == "FFFFFFFF" and system_id == "FFFF" and site == "FF" and rfss == "FF" and frequency_hz == 0
        is_zero_placeholder = system_id == "00" and site == "00" and rfss == "00" and frequency_hz == 0
        if is_placeholder:
            continue
        if is_zero_placeholder:
            continue
        site_class = groups.get("site_class", "")
        preference = groups.get("preference", "")
        if (proscan1_match or xg75_proscan1_match) and state.control_channel_hz is None and site_class.upper() == "FS" and preference.upper() == "PREFERRED":
            state.control_channel_hz = frequency_hz
        state.sites.append(
            SiteReading(
                index=int(groups["index"]),
                wacn=wacn,
                system_id=system_id,
                site=site,
                lra=lra,
                rfss=rfss,
                radio_bars=len(groups.get("bars") or ""),
                rssi=int(groups["rssi"]) if groups.get("rssi") else None,
                sample_rssi=int(groups["sample"]) if groups.get("sample") else None,
                frequency_hz=frequency_hz,
                effective_rssi=int(groups["effective"]) if groups.get("effective") else None,
                no_signal=bool(no_signal_match or xg75_no_signal_match or groups.get("no_signal")),
                valid=bool(groups.get("valid")),
                allowed=groups.get("allowed", "").upper(),
                site_class=site_class.upper(),
                reality=groups.get("reality", "").upper(),
                rx=groups.get("rx", ""),
                preference=preference.upper(),
            )
        )

    return state


def load_auto_start_default() -> bool:
    return bool(load_config().get("auto_start", True))


def load_theme_default() -> str:
    theme = str(load_config().get("theme", "dark")).lower()
    return theme if theme in ("dark", "light") else "dark"


def load_display_mode_default() -> str:
    mode = str(load_config().get("display_mode", "gui")).lower()
    return mode if mode in ("gui", "tui") else "gui"


def save_auto_start(value: bool) -> None:
    save_config_value("auto_start", bool(value))


def load_config() -> dict[str, object]:
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as config_file:
            data = json.load(config_file)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError, TypeError):
        return {}


def save_config_value(key: str, value: object) -> None:
    try:
        data = load_config()
        data[key] = value
        with open(CONFIG_PATH, "w", encoding="utf-8") as config_file:
            json.dump(data, config_file, indent=2)
    except OSError:
        pass


def clean_csv_hex(value: str) -> str:
    return hex_clean(str(value or "").strip()).zfill(2)


def first_present(row: dict[str, str], names: tuple[str, ...]) -> str:
    lowered = {key.strip().lower(): value for key, value in row.items() if key is not None}
    for name in names:
        value = lowered.get(name)
        if value not in (None, ""):
            return str(value).strip()
    return ""


def parse_network_id(value: str) -> tuple[str, str]:
    cleaned = str(value or "").strip().strip('"')
    if "." in cleaned:
        wacn, system_id = cleaned.split(".", 1)
        return clean_csv_hex(wacn), clean_csv_hex(system_id)
    parts = cleaned.split()
    if len(parts) >= 2:
        return clean_csv_hex(parts[0]), clean_csv_hex(parts[1])
    return "", ""


def clean_csv_decimal_site_part(value: str) -> str:
    cleaned = str(value or "").strip()
    if not cleaned:
        return ""
    try:
        return f"{int(cleaned, 10):02X}"
    except ValueError:
        return clean_csv_hex(cleaned)


def parse_site_id(value: str) -> tuple[str, str]:
    cleaned = str(value or "").strip().strip('"')
    if "." in cleaned:
        rfss, site = cleaned.split(".", 1)
        return clean_csv_decimal_site_part(rfss), clean_csv_decimal_site_part(site)
    parts = cleaned.split()
    if len(parts) >= 2:
        return clean_csv_decimal_site_part(parts[0]), clean_csv_decimal_site_part(parts[1])
    return "", clean_csv_decimal_site_part(cleaned) if cleaned else ""


def dsdplus_rows(path: str) -> list[list[str]]:
    rows: list[list[str]] = []
    if not os.path.exists(path):
        return rows
    with open(path, "r", encoding="utf-8-sig", newline="") as csv_file:
        for raw_line in csv_file:
            line = raw_line.strip()
            if not line or line.startswith(";") or line.startswith("#"):
                continue
            parsed = next(csv.reader([line], skipinitialspace=True), [])
            parsed = [field.strip().strip('"') for field in parsed]
            if parsed:
                rows.append(parsed)
    return rows


def load_system_names() -> dict[tuple[str, str], str]:
    names: dict[tuple[str, str], str] = {}
    rows = dsdplus_rows(SYSTEM_NAMES_PATH)
    if not rows:
        return names

    header = [field.lower() for field in rows[0]]
    has_header = any(field in header for field in ("protocol", "networkid", "network_id", "wacn", "name"))
    if has_header:
        for values in rows[1:]:
            row = dict(zip(header, values))
            protocol = first_present(row, ("protocol", "type", "mode"))
            if protocol and protocol.upper() != "P25":
                continue
            network_id = first_present(row, ("networkid", "network_id", "network id", "network"))
            wacn, system_id = parse_network_id(network_id)
            if not wacn:
                wacn = clean_csv_hex(first_present(row, ("wacn",)))
            if not system_id:
                system_id = clean_csv_hex(first_present(row, ("system_id", "systemid", "system", "sys")))
            name = first_present(row, ("name", "system_name", "system name", "label", "networkname", "network_name"))
            if wacn and system_id and name:
                names[(wacn, system_id)] = name
        return names

    for values in rows:
        if len(values) < 3:
            continue
        protocol = values[0].upper()
        if protocol != "P25":
            continue
        wacn, system_id = parse_network_id(values[1])
        name = values[2].strip()
        if wacn and system_id and name:
            names[(wacn, system_id)] = name
    return names


def load_site_names() -> dict[tuple[str, str, str, str], str]:
    names: dict[tuple[str, str, str, str], str] = {}
    rows = dsdplus_rows(SITE_NAMES_PATH)
    if not rows:
        return names

    header = [field.lower() for field in rows[0]]
    has_header = any(field in header for field in ("protocol", "networkid", "network_id", "rfss", "site", "name"))
    if has_header:
        for values in rows[1:]:
            row = dict(zip(header, values))
            protocol = first_present(row, ("protocol", "type", "mode"))
            if protocol and protocol.upper() != "P25":
                continue
            network_id = first_present(row, ("networkid", "network_id", "network id", "network"))
            wacn, system_id = parse_network_id(network_id)
            if not wacn:
                wacn = clean_csv_hex(first_present(row, ("wacn",)))
            if not system_id:
                system_id = clean_csv_hex(first_present(row, ("system_id", "systemid", "system", "sys")))
            site_id = first_present(row, ("siteid", "site_id", "site id", "site"))
            rfss, site = parse_site_id(site_id)
            if not rfss:
                rfss = clean_csv_decimal_site_part(first_present(row, ("rfss", "rfss_id", "rfss id")))
            if not site:
                site = clean_csv_decimal_site_part(first_present(row, ("site", "site_id", "site id")))
            name = first_present(row, ("name", "site_name", "site name", "label", "sitename"))
            if wacn and system_id and rfss and site and name:
                names[(wacn, system_id, rfss, site)] = name
        return names

    for values in rows:
        if len(values) < 4:
            continue
        protocol = values[0].upper()
        if protocol != "P25":
            continue
        wacn, system_id = parse_network_id(values[1])
        rfss, site = parse_site_id(values[2])
        name = values[3].strip()
        if wacn and system_id and rfss and site and name:
            names[(wacn, system_id, rfss, site)] = name
    return names


def list_com_ports() -> list[str]:
    if os.name != "nt":
        return []
    try:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        buffer_len = 65536
        buffer = ctypes.create_unicode_buffer(buffer_len)
        result = kernel32.QueryDosDeviceW(None, buffer, buffer_len)
        if not result:
            raise ctypes.WinError(ctypes.get_last_error())
        names = buffer[:result].split("\x00")
        ports = sorted(
            [name for name in names if re.fullmatch(r"COM\d+", name)],
            key=lambda item: int(item[3:]),
        )
        if ports:
            return ports
    except Exception:
        pass
    return [f"COM{index}" for index in range(1, 33)]


class SerialPoller(threading.Thread):
    def __init__(self, args: argparse.Namespace, outbox: queue.Queue):
        super().__init__(daemon=True)
        self.args = args
        self.outbox = outbox
        self.stop_event = threading.Event()
        self.command_index = 0

    def stop(self) -> None:
        self.stop_event.set()

    def run(self) -> None:
        if self.args.mock:
            self.run_mock()
            return

        try:
            ser = open_serial(self.args)
        except Exception as exc:
            self.outbox.put(("error", f"Could not open {self.args.port}: {exc}"))
            return

        with ser:
            self.outbox.put(("connection", True))
            try:
                while not self.stop_event.is_set():
                    try:
                        block = self.poll_once(ser, self.next_command())
                        if block.strip():
                            self.outbox.put(("state", parse_radio_block(block)))
                    except Exception as exc:
                        self.outbox.put(("error", f"Serial poll failed: {exc}"))
                    self.stop_event.wait(self.args.interval)
            finally:
                self.outbox.put(("connection", False))

    def run_mock(self) -> None:
        self.outbox.put(("connection", True))
        while not self.stop_event.is_set():
            self.outbox.put(("state", parse_radio_block(SAMPLE_BLOCK)))
            self.stop_event.wait(self.args.interval)
        self.outbox.put(("connection", False))

    def next_command(self) -> str:
        if self.args.alternate_commands:
            command = self.args.commands[self.command_index % len(self.args.commands)]
            self.command_index += 1
            return command
        return self.args.command

    def poll_once(self, ser, command: str) -> str:
        ser.reset_input_buffer()
        if command:
            ser.write(command.encode(self.args.encoding))
        ser.write(b"\r")
        ser.flush()

        deadline = time.time() + self.args.response_timeout
        chunks: list[str] = []
        while time.time() < deadline and not self.stop_event.is_set():
            data = ser.read(256)
            if data:
                decoded = data.decode(self.args.encoding, errors="replace")
                chunks.append(decoded)
                response = "".join(chunks)
                if re.search(r"(^|[\r\n])\*\s*$", response):
                    break
            else:
                time.sleep(0.03)
        return re.sub(r"[\r\n]\*\s*$", "", "".join(chunks)).strip()


def open_serial(args: argparse.Namespace):
    try:
        import serial
    except ImportError:
        if os.name == "nt":
            return Win32Serial(
                port=args.port,
                baudrate=args.baud,
                timeout=args.read_timeout,
                rtscts=args.rtscts,
                xonxoff=args.xonxoff,
                dsrdtr=args.dsrdtr,
            )
        raise RuntimeError("pyserial is not installed. Run: python -m pip install pyserial")

    return serial.Serial(
        port=args.port,
        baudrate=args.baud,
        bytesize=serial.EIGHTBITS,
        parity=serial.PARITY_NONE,
        stopbits=serial.STOPBITS_ONE,
        timeout=args.read_timeout,
        rtscts=args.rtscts,
        xonxoff=args.xonxoff,
        dsrdtr=args.dsrdtr,
    )


class DCB(ctypes.Structure):
    _fields_ = [
        ("DCBlength", ctypes.c_uint32),
        ("BaudRate", ctypes.c_uint32),
        ("fFlags", ctypes.c_uint32),
        ("wReserved", ctypes.c_uint16),
        ("XonLim", ctypes.c_uint16),
        ("XoffLim", ctypes.c_uint16),
        ("ByteSize", ctypes.c_ubyte),
        ("Parity", ctypes.c_ubyte),
        ("StopBits", ctypes.c_ubyte),
        ("XonChar", ctypes.c_char),
        ("XoffChar", ctypes.c_char),
        ("ErrorChar", ctypes.c_char),
        ("EofChar", ctypes.c_char),
        ("EvtChar", ctypes.c_char),
        ("wReserved1", ctypes.c_uint16),
    ]


class COMMTIMEOUTS(ctypes.Structure):
    _fields_ = [
        ("ReadIntervalTimeout", ctypes.c_uint32),
        ("ReadTotalTimeoutMultiplier", ctypes.c_uint32),
        ("ReadTotalTimeoutConstant", ctypes.c_uint32),
        ("WriteTotalTimeoutMultiplier", ctypes.c_uint32),
        ("WriteTotalTimeoutConstant", ctypes.c_uint32),
    ]


class Win32Serial:
    GENERIC_READ = 0x80000000
    GENERIC_WRITE = 0x40000000
    OPEN_EXISTING = 3
    INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value
    PURGE_RXCLEAR = 0x0008
    PURGE_TXCLEAR = 0x0004

    def __init__(self, port: str, baudrate: int, timeout: float, rtscts: bool, xonxoff: bool, dsrdtr: bool):
        self.kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self.handle = None
        port_name = port if port.startswith("\\\\.\\") else f"\\\\.\\{port}"
        self.handle = self.kernel32.CreateFileW(
            port_name,
            self.GENERIC_READ | self.GENERIC_WRITE,
            0,
            None,
            self.OPEN_EXISTING,
            0,
            None,
        )
        if self.handle == self.INVALID_HANDLE_VALUE:
            self.handle = None
            raise ctypes.WinError(ctypes.get_last_error())

        self.configure(baudrate, timeout, rtscts, xonxoff, dsrdtr)

    def configure(self, baudrate: int, timeout: float, rtscts: bool, xonxoff: bool, dsrdtr: bool) -> None:
        dcb = DCB()
        dcb.DCBlength = ctypes.sizeof(DCB)
        if not self.kernel32.GetCommState(self.handle, ctypes.byref(dcb)):
            raise ctypes.WinError(ctypes.get_last_error())

        f_binary = 1 << 0
        f_tx_continue_on_xoff = 1 << 7
        f_out_x = 1 << 8
        f_in_x = 1 << 9
        f_outx_cts_flow = 1 << 2
        f_outx_dsr_flow = 1 << 3
        dtr_control_enable = 1 << 4
        rts_control_enable = 1 << 12
        rts_control_handshake = 2 << 12

        flags = f_binary | f_tx_continue_on_xoff
        if xonxoff:
            flags |= f_out_x | f_in_x
        if rtscts:
            flags |= f_outx_cts_flow | rts_control_handshake
        else:
            flags |= rts_control_enable
        if dsrdtr:
            flags |= f_outx_dsr_flow | dtr_control_enable
        else:
            flags |= dtr_control_enable

        dcb.BaudRate = baudrate
        dcb.fFlags = flags
        dcb.ByteSize = 8
        dcb.Parity = 0
        dcb.StopBits = 0
        dcb.XonChar = b"\x11"
        dcb.XoffChar = b"\x13"
        dcb.XonLim = 2048
        dcb.XoffLim = 512

        if not self.kernel32.SetCommState(self.handle, ctypes.byref(dcb)):
            raise ctypes.WinError(ctypes.get_last_error())

        timeout_ms = max(1, int(timeout * 1000))
        timeouts = COMMTIMEOUTS(
            ReadIntervalTimeout=50,
            ReadTotalTimeoutMultiplier=0,
            ReadTotalTimeoutConstant=timeout_ms,
            WriteTotalTimeoutMultiplier=0,
            WriteTotalTimeoutConstant=timeout_ms,
        )
        if not self.kernel32.SetCommTimeouts(self.handle, ctypes.byref(timeouts)):
            raise ctypes.WinError(ctypes.get_last_error())

    def write(self, data: bytes) -> int:
        written = ctypes.c_uint32(0)
        buffer = ctypes.create_string_buffer(data)
        if not self.kernel32.WriteFile(self.handle, buffer, len(data), ctypes.byref(written), None):
            raise ctypes.WinError(ctypes.get_last_error())
        return written.value

    def read(self, size: int) -> bytes:
        read = ctypes.c_uint32(0)
        buffer = ctypes.create_string_buffer(size)
        if not self.kernel32.ReadFile(self.handle, buffer, size, ctypes.byref(read), None):
            raise ctypes.WinError(ctypes.get_last_error())
        return buffer.raw[: read.value]

    def flush(self) -> None:
        if not self.kernel32.FlushFileBuffers(self.handle):
            raise ctypes.WinError(ctypes.get_last_error())

    def reset_input_buffer(self) -> None:
        if not self.kernel32.PurgeComm(self.handle, self.PURGE_RXCLEAR | self.PURGE_TXCLEAR):
            raise ctypes.WinError(ctypes.get_last_error())

    def close(self) -> None:
        if self.handle is not None:
            self.kernel32.CloseHandle(self.handle)
            self.handle = None

    def __enter__(self):
        return self

    def __exit__(self, _exc_type, _exc, _tb):
        self.close()


class Dashboard(tk.Tk):
    def __init__(self, args: argparse.Namespace):
        super().__init__()
        self.title("Harris ProScan Monitor")
        self.geometry("1560x900")
        self.minsize(1280, 760)
        self.args = args
        self.queue: queue.Queue = queue.Queue()
        self.poller: Optional[SerialPoller] = None
        self.status_var = tk.StringVar(value="")
        self.time_var = tk.StringVar(value="--:--:--")
        self.port_var = tk.StringVar(value=args.port)
        self.theme_var = tk.StringVar(value=load_theme_default())
        self.display_mode = tk.StringVar(value=load_display_mode_default())
        self.light_mode = tk.BooleanVar(value=self.theme_var.get() == "light")
        self.net_var = tk.StringVar(value="Unknown")
        self.system_name_var = tk.StringVar(value="")
        self.site_var = tk.StringVar(value="SITE ?")
        self.site_name_var = tk.StringVar(value="")
        self.current_site_card_var = tk.StringVar(value="SITE ?")
        self.current_site_card_sub_var = tk.StringVar(value="")
        self.cc_var = tk.StringVar(value="Unknown")
        self.cc_sub_var = tk.StringVar(value="")
        self.home_var = tk.StringVar(value="Unknown")
        self.home_quality_var = tk.StringVar(value="")
        self.footer_left_var = tk.StringVar(value="Monitoring")
        self.footer_right_var = tk.StringVar(value="Connected")
        self.auto_start = tk.BooleanVar(value=args.auto_start)
        self.state = RadioState()
        self.last_control_channel_hz: Optional[int] = None
        self.last_parsed_at: Optional[float] = None
        self.serial_connected = False
        self.last_error = ""
        self.table_headings: dict[str, str] = {}
        self.sort_column = "site_id"
        self.sort_descending = False
        self.site_metadata_cache: dict[tuple[str, str, str, str, str], dict[str, object]] = {}
        self.system_names = load_system_names()
        self.site_names = load_site_names()
        self.show_system_names = bool(self.system_names)
        self.show_site_names = bool(self.site_names)
        self.logo_image: Optional[tk.PhotoImage] = None
        self.icon_images: dict[str, tk.PhotoImage] = {}
        self.graphic_root: Optional[tk.Widget] = None
        self.tui_overlay: Optional[tk.Frame] = None
        self.tui_text: Optional[tk.Text] = None
        self.tui_footer_dot: Optional[tk.Label] = None
        self.tui_footer_left: Optional[tk.Label] = None
        self.tui_footer_right: Optional[tk.Label] = None
        self.themed_frames: list[tk.Widget] = []
        self.header_widgets: list[tk.Widget] = []
        self.footer_widgets: list[tk.Widget] = []
        self.card_frames: list[tk.Widget] = []
        self.rounded_panels: list[RoundedPanel] = []
        self.card_value_labels: list[tk.Widget] = []
        self.card_muted_labels: list[tk.Widget] = []
        self.card_icon_canvases: list[tuple[tk.Canvas, str]] = []
        self.indicator_icon_canvases: list[tuple[tk.Canvas, str]] = []
        self.indicator_pills: list[tk.Canvas] = []
        self.header_check_canvases: list[tuple[tk.Canvas, tk.BooleanVar]] = []
        self.header_button_canvases: list[tuple[tk.Canvas, str, str]] = []
        self.port_canvas: Optional[tk.Canvas] = None
        self.control_widgets: list[tk.Widget] = []
        self.footer_dot: Optional[tk.Label] = None
        self.site_status_indicator: Optional[tk.Label] = None
        self.call_indicator: Optional[tk.Label] = None
        self.net_indicator: Optional[tk.Label] = None
        self.rfss_indicator: Optional[tk.Label] = None
        self.preferred_indicator: Optional[tk.Label] = None

        self.configure(bg="#101418")
        self.create_widgets()
        if self.auto_start.get():
            self.start_polling()
        self.after(100, self.drain_queue)
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def create_widgets(self) -> None:
        style = ttk.Style(self)
        style.theme_use("clam")

        outer = ttk.Frame(self, padding=12)
        outer.pack(fill=tk.BOTH, expand=True)
        self.graphic_root = outer
        self.themed_frames.append(outer)

        top = ttk.Frame(outer, style="Header.TFrame", padding=(16, 10))
        top.pack(fill=tk.X, pady=(0, 8))
        brand = ttk.Frame(top, style="Header.TFrame")
        brand.pack(side=tk.LEFT)
        self.header_widgets.extend([top, brand])
        try:
            self.logo_image = tk.PhotoImage(file=LOGO_PATH)
            logo_label = tk.Label(brand, image=self.logo_image)
            logo_label.pack(side=tk.LEFT, padx=(0, 28))
            self.header_widgets.append(logo_label)
        except tk.TclError:
            ttk.Label(brand, text="HARRIS", style="Header.TLabel").pack(side=tk.LEFT, padx=(0, 28))
        ttk.Label(brand, text="ProScan Monitor", style="Header.TLabel").pack(side=tk.LEFT)
        top_controls = ttk.Frame(top, style="Header.TFrame")
        top_controls.pack(side=tk.RIGHT)
        self.header_widgets.append(top_controls)
        self.start_button = self.add_header_button(top_controls, "Start", "play", self.start_polling)
        self.start_button.grid(row=0, column=0, padx=(0, 8))
        self.stop_button = self.add_header_button(top_controls, "Stop", "stop", self.stop_polling)
        self.stop_button.grid(row=0, column=1, padx=(0, 24))
        ttk.Label(top_controls, text="COM Port:", style="HeaderSmall.TLabel").grid(row=0, column=2, padx=(0, 8), sticky=tk.E)
        ports = list_com_ports()
        if self.port_var.get() not in ports:
            ports.insert(0, self.port_var.get())
        self.port_select = tk.Frame(top_controls, bg=THEMES[self.theme_var.get()]["header_bg"])
        self.port_menu = tk.Menu(self.port_select, tearoff=False)
        for port in ports:
            self.port_menu.add_command(label=port, command=lambda value=port: self.select_port(value))
        self.port_canvas = tk.Canvas(self.port_select, width=138, height=44, highlightthickness=0, cursor="hand2")
        self.port_canvas.pack()
        self.port_canvas.bind("<Button-1>", self.show_port_menu)
        self.port_select.grid(row=0, column=3, padx=(0, 16), sticky=tk.W)
        self.auto_check = self.add_header_checkbox(top_controls, "Auto start", self.auto_start, self.toggle_auto_start_from_header)
        self.auto_check.grid(row=0, column=4, padx=(0, 18), sticky=tk.W)
        self.theme_check = self.add_header_checkbox(top_controls, "Light mode", self.light_mode, self.toggle_theme_from_header)
        self.theme_check.grid(row=0, column=5, padx=(0, 16), sticky=tk.W)
        ttk.Separator(top_controls, orient=tk.VERTICAL).grid(row=0, column=6, sticky=tk.NS, padx=(0, 18))
        ttk.Label(top_controls, text="Last Updated:", style="HeaderSmall.TLabel").grid(row=0, column=7, padx=(0, 8), sticky=tk.E)
        ttk.Label(top_controls, textvariable=self.time_var, width=8, style="HeaderSmall.TLabel").grid(row=0, column=8, sticky=tk.E)
        self.control_widgets.extend([self.start_button, self.stop_button, self.port_select, self.auto_check, self.theme_check])

        cards = ttk.Frame(outer)
        cards.pack(fill=tk.X, pady=(0, 12))
        self.themed_frames.append(cards)
        for column in range(4):
            cards.grid_columnconfigure(column, minsize=310, weight=1, uniform="cards")
        self.add_card(cards, "Current site", self.current_site_card_var, 0, self.current_site_card_sub_var, "pin")
        self.add_card(cards, "Network", self.net_var, 1, self.system_name_var, "network")
        self.add_card(cards, "Control channel", self.cc_var, 2, self.cc_sub_var, "wave")
        self.add_card(cards, "Home RSSI", self.home_var, 3, self.home_quality_var, "bars")

        indicators = ttk.Frame(outer)
        indicators.pack(fill=tk.X, pady=(0, 10))
        self.themed_frames.append(indicators)
        for column in range(5):
            indicators.grid_columnconfigure(column, minsize=185, weight=1, uniform="indicators")
        self.site_status_indicator = self.add_indicator(indicators, "Latched", "lock", 0)
        self.call_indicator = self.add_indicator(indicators, "Call", "phone", 1)
        self.net_indicator = self.add_indicator(indicators, "Net", "share", 2)
        self.rfss_indicator = self.add_indicator(indicators, "RFSS", "tree", 3)
        self.preferred_indicator = self.add_indicator(indicators, "Preferred", "star", 4)

        body = ttk.Frame(outer)
        body.pack(fill=tk.BOTH, expand=True)
        self.themed_frames.append(body)

        upper = ttk.Frame(body)
        upper.pack(fill=tk.BOTH, expand=True)
        self.themed_frames.append(upper)

        self.neighbors_panel = RoundedPanel(upper, radius=7)
        self.neighbors_panel.pack(fill=tk.BOTH, expand=True)
        self.rounded_panels.append(self.neighbors_panel)
        neighbors_title = ttk.Label(self.neighbors_panel.inner, text="ProScan Neighbors", style="CardTitle.TLabel")
        neighbors_title.pack(anchor=tk.W, padx=16, pady=(12, 0))
        self.card_muted_labels.append(neighbors_title)
        self.canvas = tk.Canvas(self.neighbors_panel.inner, height=205, bg="#101418", highlightthickness=0)
        self.canvas.pack(fill=tk.X, padx=1, pady=(0, 10))
        self.canvas.bind("<Configure>", lambda _event: self.draw_signal_bars())

        columns = ("rfss_id", "site_id", "lra", "site_name", "rssi", "control", "spacing", "quality", "valid", "status")
        self.tree = ttk.Treeview(self.neighbors_panel.inner, columns=columns, show="headings", height=8)
        headings = {
            "rfss_id": "RFSS ID",
            "site_id": "Site ID",
            "lra": "LRA",
            "site_name": "Site Name",
            "rssi": "RSSI (dBm)",
            "control": "Control Channel (MHz)",
            "spacing": "Channel Spacing (kHz)",
            "quality": "Signal Quality",
            "valid": "Valid",
            "status": "CC Type",
        }
        self.table_headings = headings
        widths = {
            "rfss_id": 70,
            "site_id": 80,
            "lra": 60,
            "site_name": 200,
            "rssi": 90,
            "control": 165,
            "spacing": 165,
            "quality": 110,
            "valid": 80,
            "status": 120,
        }
        for col in columns:
            self.tree.heading(col, text=headings[col], command=lambda column=col: self.sort_table_by(column))
            self.tree.column(col, width=widths[col], minwidth=widths[col], anchor=tk.CENTER, stretch=True)
        self.tree.pack(fill=tk.X, padx=16, pady=(0, 1))

        footer = ttk.Frame(outer, style="Footer.TFrame", padding=(4, 10))
        footer.pack(fill=tk.X, pady=(8, 0))
        self.themed_frames.append(footer)
        dot = tk.Label(footer, text="●", font=("Segoe UI", 13))
        dot.pack(side=tk.LEFT, padx=(0, 8))
        self.footer_dot = dot
        self.footer_widgets.append(dot)
        ttk.Label(footer, textvariable=self.footer_left_var, style="Footer.TLabel").pack(side=tk.LEFT)
        copyright_frame = ttk.Frame(footer, style="Footer.TFrame")
        copyright_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.footer_widgets.append(copyright_frame)
        copyright_inner = ttk.Frame(copyright_frame, style="Footer.TFrame")
        copyright_inner.pack(anchor=tk.CENTER)
        self.footer_widgets.append(copyright_inner)
        copyright_symbol = ttk.Label(copyright_inner, text="©", style="Footer.TLabel", cursor="hand2")
        copyright_symbol.pack(side=tk.LEFT)
        copyright_symbol.bind("<Button-1>", lambda _event: self.toggle_display_mode())
        ttk.Label(copyright_inner, text="2026 Crazy Frog's CB Jamboroo", style="Footer.TLabel").pack(side=tk.LEFT)
        ttk.Label(footer, textvariable=self.footer_right_var, style="Footer.TLabel").pack(side=tk.RIGHT)
        self.create_tui_overlay()
        self.apply_theme()
        self.apply_display_mode()

    def add_card(self, parent: ttk.Frame, label: str, variable: tk.StringVar, column: int, subvariable: Optional[tk.StringVar] = None, icon: str = "") -> None:
        panel = RoundedPanel(parent, radius=7, height=122)
        panel.grid(row=0, column=column, sticky=tk.EW, padx=(0, 0 if column == 3 else 12))
        panel.grid_propagate(False)
        self.rounded_panels.append(panel)
        frame = panel.inner
        self.card_frames.append(frame)
        label_widget = ttk.Label(frame, text=label, style="CardTitle.TLabel")
        label_widget.place(x=18, y=16)
        self.card_muted_labels.append(label_widget)

        icon_canvas = tk.Canvas(frame, width=54, height=54, highlightthickness=0)
        icon_canvas.place(x=22, y=72, anchor=tk.W)
        self.card_icon_canvases.append((icon_canvas, icon))

        value_widget = ttk.Label(frame, textvariable=variable, style="Value.TLabel")
        value_widget.place(x=98, y=68, anchor=tk.W)
        self.card_value_labels.append(value_widget)
        if subvariable is not None:
            sublabel = ttk.Label(frame, textvariable=subvariable, style="SubValue.TLabel")
            sublabel.place(x=98, y=92, anchor=tk.W)
            self.card_muted_labels.append(sublabel)

    def add_header_button(self, parent: ttk.Frame, label: str, kind: str, command) -> tk.Canvas:
        canvas = tk.Canvas(parent, width=112, height=44, highlightthickness=0, cursor="hand2")
        canvas.bind("<Button-1>", lambda _event: command())
        self.header_button_canvases.append((canvas, label, kind))
        return canvas

    def draw_header_button(self, canvas: tk.Canvas, label: str, kind: str) -> None:
        colors = self.current_theme()
        canvas.configure(bg=colors["header_bg"])
        canvas.delete("all")
        fg = "#1f7a32" if kind == "play" else "#b51f28"
        rounded_rect(canvas, 2, 2, 110, 42, 8, fill=colors["control_bg"], outline=colors["border"], width=1)
        if kind == "play":
            canvas.create_polygon(23, 15, 23, 29, 35, 22, fill=fg, outline=fg)
        else:
            canvas.create_rectangle(23, 17, 33, 27, fill=fg, outline=fg)
        canvas.create_text(65, 22, text=label, fill=fg, font=("Segoe UI", 11, "bold"))

    def draw_port_selector(self) -> None:
        if self.port_canvas is None:
            return
        colors = self.current_theme()
        self.port_select.configure(bg=colors["header_bg"])
        self.port_canvas.configure(bg=colors["header_bg"])
        self.port_canvas.delete("all")
        rounded_rect(self.port_canvas, 2, 2, 136, 42, 7, fill=colors["control_bg"], outline=colors["border"], width=1)
        self.port_canvas.create_text(18, 22, text=self.port_var.get(), anchor=tk.W, fill=colors["header_fg"], font=("Segoe UI", 11, "bold"))
        self.port_canvas.create_polygon(113, 18, 125, 18, 119, 25, fill=colors["muted_fg"], outline=colors["muted_fg"])

    def add_header_checkbox(self, parent: ttk.Frame, label: str, variable: tk.BooleanVar, command) -> ttk.Frame:
        frame = ttk.Frame(parent, style="Header.TFrame")
        canvas = tk.Canvas(frame, width=22, height=22, highlightthickness=0, cursor="hand2")
        canvas.pack(side=tk.LEFT, padx=(0, 7))
        text = ttk.Label(frame, text=label, style="HeaderSmall.TLabel", cursor="hand2")
        text.pack(side=tk.LEFT)
        self.header_widgets.append(frame)
        self.header_check_canvases.append((canvas, variable))
        for widget in (frame, canvas, text):
            widget.bind("<Button-1>", lambda _event, callback=command: callback())
        return frame

    def draw_header_checkbox(self, canvas: tk.Canvas, variable: tk.BooleanVar) -> None:
        colors = self.current_theme()
        canvas.configure(bg=colors["header_bg"])
        canvas.delete("all")
        if variable.get():
            rounded_rect(canvas, 2, 2, 20, 20, 4, fill=colors["accent_alt"], outline=colors["accent_alt"], width=1)
            canvas.create_line(6, 11, 10, 15, 17, 7, fill="#ffffff", width=2)
        else:
            rounded_rect(canvas, 2, 2, 20, 20, 4, fill=colors["header_bg"], outline=colors["border"], width=1)

    def create_tui_overlay(self) -> None:
        self.tui_overlay = tk.Frame(self)
        self.tui_text = tk.Text(self.tui_overlay, wrap=tk.NONE, borderwidth=0, highlightthickness=0, padx=24, pady=18)
        self.tui_text.configure(font=("Consolas", 10, "bold"), state=tk.DISABLED)
        self.tui_text.pack(fill=tk.BOTH, expand=True)

        footer = tk.Frame(self.tui_overlay)
        footer.pack(fill=tk.X, padx=18, pady=(0, 12))
        self.tui_footer_dot = tk.Label(footer, text="●", font=("Segoe UI", 13))
        self.tui_footer_dot.pack(side=tk.LEFT, padx=(0, 8))
        self.tui_footer_left = tk.Label(footer, textvariable=self.footer_left_var, font=("Segoe UI", 10))
        self.tui_footer_left.pack(side=tk.LEFT)
        copyright_frame = tk.Frame(footer)
        copyright_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)
        copyright_inner = tk.Frame(copyright_frame)
        copyright_inner.pack(anchor=tk.CENTER)
        copyright_symbol = tk.Label(copyright_inner, text="©", font=("Segoe UI", 10), cursor="hand2")
        copyright_symbol.pack(side=tk.LEFT)
        copyright_symbol.bind("<Button-1>", lambda _event: self.toggle_display_mode())
        tk.Label(copyright_inner, text="2026 Crazy Frog's CB Jamboroo", font=("Segoe UI", 10)).pack(side=tk.LEFT)
        self.tui_footer_right = tk.Label(footer, textvariable=self.footer_right_var, font=("Segoe UI", 10))
        self.tui_footer_right.pack(side=tk.RIGHT)

    def apply_tui_theme(self) -> None:
        if self.tui_overlay is None:
            return
        colors = self.current_theme()
        self.tui_overlay.configure(bg=colors["canvas_bg"])
        if self.tui_text is not None:
            self.tui_text.configure(bg=colors["canvas_bg"], fg=colors["table_fg"], insertbackground=colors["table_fg"])
        self.configure_tui_children(self.tui_overlay)

    def configure_tui_children(self, widget: tk.Widget) -> None:
        colors = self.current_theme()
        for child in widget.winfo_children():
            if child is self.tui_text:
                continue
            if isinstance(child, tk.Frame):
                child.configure(bg=colors["footer_bg"])
            elif isinstance(child, tk.Label):
                child.configure(bg=colors["footer_bg"], fg=colors["table_fg"])
            self.configure_tui_children(child)

    def toggle_display_mode(self) -> None:
        self.display_mode.set("tui" if self.display_mode.get() == "gui" else "gui")
        save_config_value("display_mode", self.display_mode.get())
        self.apply_display_mode()

    def apply_display_mode(self) -> None:
        if self.tui_overlay is None:
            return
        if self.display_mode.get() == "tui":
            self.tui_overlay.place(x=0, y=0, relwidth=1, relheight=1)
            self.tui_overlay.lift()
            self.render_tui()
        else:
            self.tui_overlay.place_forget()

    def tui_box(self, title: str, lines: list[str], width: int) -> list[str]:
        inner = width - 2
        top = "+" + "-" * inner + "+"
        body = [top, "|" + title[:inner].ljust(inner) + "|"]
        for line in lines:
            body.append("|" + line[:inner].ljust(inner) + "|")
        while len(body) < 5:
            body.append("|" + " " * inner + "|")
        body.append(top)
        return body

    def render_tui(self) -> None:
        if self.tui_text is None or self.display_mode.get() != "tui":
            return
        colors = self.current_theme()
        rows = self.tui_lines()
        self.tui_text.configure(state=tk.NORMAL, bg=colors["canvas_bg"], fg=colors["table_fg"], insertbackground=colors["table_fg"])
        self.tui_text.delete("1.0", tk.END)
        self.tui_text.insert("1.0", "\n".join(rows))
        self.tui_text.configure(state=tk.DISABLED)

    def tui_lines(self) -> list[str]:
        width = 156
        header = (
            f"HARRIS  ProScan Monitor"
            f"{'':<48}"
            f"[ Start ]  [ Stop ]   COM Port: {self.port_var.get():<5}   "
            f"Auto start: {'YES' if self.auto_start.get() else 'NO':<3}   "
            f"Light mode: {'YES' if self.light_mode.get() else 'NO':<3}   "
            f"Last Updated: {self.time_var.get()}"
        )
        lines = [header[:width], "=" * width, ""]

        card_width = 37
        card_gap = " "
        cards = [
            self.tui_box("Current site", [self.current_site_card_var.get(), self.current_site_card_sub_var.get()], card_width),
            self.tui_box("Network", [self.net_var.get(), self.system_name_var.get()], card_width),
            self.tui_box("Control channel", [self.cc_var.get(), self.cc_sub_var.get()], card_width),
            self.tui_box("Home RSSI", [self.home_var.get(), self.home_quality_var.get()], card_width),
        ]
        for row in zip(*cards):
            lines.append(card_gap.join(row))
        lines.append("")

        indicator_width = 29
        latched = self.is_latched()
        indicators = [
            self.tui_box("Latched", ["YES" if latched else "NO"], indicator_width),
            self.tui_box("Call", ["ACTIVE" if latched and self.state.working_channel else "NONE"], indicator_width),
            self.tui_box("Net", ["CONNECTED" if self.state.net_status == "TRUE" else "NO"], indicator_width),
            self.tui_box("RFSS", [hex_to_decimal_text(self.state.current_rfss)], indicator_width),
            self.tui_box("Preferred", ["YES" if latched and self.state.preferred else "NO"], indicator_width),
        ]
        for row in zip(*indicators):
            lines.append(card_gap.join(row))
        lines.append("")

        lines.append("+ " + "ProScan Neighbors".ljust(width - 4) + " +")
        lines.append("| RSSI (dBm)".ljust(width - 1) + "|")
        for label, value, kind, no_signal in self.signal_rows()[:13]:
            shown = "*no signal*" if no_signal else (str(value) if value is not None else "")
            bar = self.tui_rssi_bar(value, no_signal)
            suffix = " (Current)" if kind == "home" else ""
            lines.append(f"| {label:<8} {shown:>10} {bar:<80}{suffix:<20}".ljust(width - 1) + "|")
        if len(lines) < 22:
            lines.extend(["|" + " " * (width - 2) + "|"] * (22 - len(lines)))
        lines.append("|" + "-" * (width - 2) + "|")

        headers = ["RFSS", "Site", "LRA", "Site Name", "RSSI", "Control MHz", "Spacing", "Quality", "Valid", "CC Type"]
        table_widths = [6, 8, 5, 27, 7, 17, 9, 9, 8, 8]
        lines.append("| " + self.tui_table_row(headers, table_widths) + " |")
        lines.append("| " + self.tui_table_rule(table_widths) + " |")
        for site in self.sorted_neighbor_sites()[:10]:
            values = list(self.site_table_values(site))
            lines.append("| " + self.tui_table_row(values, table_widths) + " |")
        lines.append("+" + "-" * (width - 2) + "+")
        return lines

    def signal_rows(self) -> list[tuple[str, Optional[int], str, bool]]:
        rows: list[tuple[str, Optional[int], str, bool]] = []
        if self.state.current_site and self.state.home_effective_rssi is not None:
            rows.append((site_display(self.state.current_site), self.state.home_effective_rssi, "home", False))
        for site in self.sorted_neighbor_sites():
            if site.site_class == "FS" and site.no_signal:
                continue
            value = site.effective_rssi if site.effective_rssi is not None else site.rssi
            rows.append((site_display(site.site), value, "site", site.no_signal))
        return rows

    def tui_rssi_bar(self, value: Optional[int], no_signal: bool) -> str:
        if no_signal or value is None:
            return ""
        clamped = max(-130, min(-50, value))
        cells = max(1, round(((clamped + 130) / 80) * 40))
        return ("#" if value == self.state.home_effective_rssi else "=") * cells

    def tui_table_row(self, values: list[str], widths: list[int]) -> str:
        cells = []
        for value, width in zip(values, widths):
            text = str(value)
            cells.append(text[:width].ljust(width))
        return "  ".join(cells)

    def tui_table_rule(self, widths: list[int]) -> str:
        return "  ".join("-" * width for width in widths)

    def current_theme(self) -> dict[str, str]:
        return THEMES[self.theme_var.get()]

    def toggle_theme(self) -> None:
        self.theme_var.set("light" if self.light_mode.get() else "dark")
        save_config_value("theme", self.theme_var.get())
        self.apply_theme()
        self.draw_signal_bars()

    def apply_theme(self) -> None:
        colors = self.current_theme()
        style = ttk.Style(self)
        self.configure(bg=colors["app_bg"])
        style.configure("TFrame", background=colors["app_bg"])
        style.configure("Header.TFrame", background=colors["header_bg"])
        style.configure("Footer.TFrame", background=colors["footer_bg"])
        style.configure("Panel.TFrame", background=colors["panel_bg"], borderwidth=1, relief=tk.SOLID)
        style.configure("TLabel", background=colors["app_bg"], foreground=colors["table_fg"])
        style.configure("Header.TLabel", background=colors["header_bg"], foreground=colors["header_fg"], font=("Segoe UI", 21, "bold"))
        style.configure("HeaderSmall.TLabel", background=colors["header_bg"], foreground=colors["header_fg"], font=("Segoe UI", 10, "bold"))
        style.configure("Footer.TLabel", background=colors["footer_bg"], foreground=colors["table_fg"], font=("Segoe UI", 10))
        style.configure("CardTitle.TLabel", background=colors["panel_bg"], foreground=colors["panel_fg"], font=("Segoe UI", 14, "bold"))
        style.configure("Muted.TLabel", background=colors["panel_bg"], foreground=colors["muted_fg"], font=("Segoe UI", 10, "bold"))
        style.configure("Value.TLabel", background=colors["panel_bg"], foreground=colors["panel_fg"], font=("Segoe UI", 14, "bold"))
        style.configure("SubValue.TLabel", background=colors["panel_bg"], foreground=colors["panel_fg"], font=("Segoe UI", 11, "bold"))
        style.configure("Indicator.TLabel", background=colors["panel_bg"], foreground=colors["panel_fg"], font=("Segoe UI", 11, "bold"))
        style.configure("IndicatorIcon.TLabel", background=colors["panel_bg"], foreground=colors["muted_fg"], font=("Segoe UI", 15, "bold"))
        style.configure("TCheckbutton", background=colors["header_bg"], foreground=colors["header_fg"])
        style.configure("Start.TButton", foreground="#1f7a32", font=("Segoe UI", 10, "bold"))
        style.configure("Stop.TButton", foreground="#b51f28", font=("Segoe UI", 10, "bold"))
        style.configure("Treeview", background=colors["table_bg"], fieldbackground=colors["table_bg"], foreground=colors["table_fg"], rowheight=27, bordercolor=colors["border"], font=("Segoe UI", 9))
        style.configure("Treeview.Heading", background=colors["table_heading"], foreground=colors["table_fg"], font=("Segoe UI", 9, "bold"), padding=(4, 7))
        style.map("Treeview", background=[("selected", colors["home_bar"])], foreground=[("selected", colors["panel_fg"])])
        style.map(
            "Treeview.Heading",
            background=[("active", colors["table_heading"]), ("pressed", colors["table_heading"])],
            foreground=[("active", colors["table_fg"]), ("pressed", colors["table_fg"])],
        )

        for frame in self.themed_frames:
            try:
                frame.configure(style="TFrame")
            except tk.TclError:
                frame.configure(bg=colors["app_bg"])
        for widget in self.header_widgets:
            try:
                widget.configure(style="Header.TFrame")
            except tk.TclError:
                widget.configure(bg=colors["header_bg"], fg=colors["header_fg"])
        for widget in self.footer_widgets:
            try:
                widget.configure(style="Footer.TFrame")
            except tk.TclError:
                widget.configure(bg=colors["footer_bg"], fg=colors["accent"])
        self.port_menu.configure(bg=colors["panel_bg"], fg=colors["panel_fg"], activebackground=colors["bar_track"], activeforeground=colors["panel_fg"])
        for canvas, label, kind in self.header_button_canvases:
            self.draw_header_button(canvas, label, kind)
        self.draw_port_selector()
        for canvas, variable in self.header_check_canvases:
            self.draw_header_checkbox(canvas, variable)
        for frame in self.card_frames:
            try:
                frame.configure(style="Panel.TFrame")
            except tk.TclError:
                try:
                    frame.configure(bg=colors["panel_bg"])
                except tk.TclError:
                    pass
        for panel in self.rounded_panels:
            panel.set_theme(colors["app_bg"], colors["panel_bg"], colors["border"])
        for canvas, icon in self.card_icon_canvases:
            self.draw_card_icon(canvas, icon)
        for canvas, icon in self.indicator_icon_canvases:
            self.draw_indicator_icon(canvas, icon)
        if hasattr(self, "canvas"):
            self.canvas.configure(bg=colors["canvas_bg"])
        self.apply_tui_theme()
        self.update_indicator_colors()
        self.update_footer_status()
        self.render_tui()

    def load_icon_image(self, family: str, icon: str, size: int) -> Optional[tk.PhotoImage]:
        filename = f"{family}_{self.theme_var.get()}_{icon}_{size}.png"
        path = os.path.join(ICON_DIR, filename)
        if not os.path.exists(path):
            return None
        image = self.icon_images.get(path)
        if image is not None:
            return image
        try:
            image = tk.PhotoImage(file=path)
        except tk.TclError:
            return None
        self.icon_images[path] = image
        return image

    def draw_card_icon(self, canvas: tk.Canvas, icon: str) -> None:
        colors = self.current_theme()
        canvas.configure(bg=colors["panel_bg"])
        canvas.delete("all")
        image = self.load_icon_image("card", icon, 54)
        if image is not None:
            canvas.create_image(27, 27, image=image)
            return
        fg = colors["panel_fg"]
        badge = colors["bar_track"] if self.theme_var.get() == "dark" else "#f2f2f2"
        rounded_rect(canvas, 4, 4, 50, 50, 7, outline=colors["border"], fill=badge, width=1)
        if icon == "pin":
            canvas.create_oval(20, 13, 34, 27, fill=fg, outline=fg)
            canvas.create_polygon(20, 24, 34, 24, 27, 40, fill=fg, outline=fg)
            canvas.create_oval(24, 17, 30, 23, fill=badge, outline=badge)
        elif icon == "network":
            points = [(27, 15), (16, 34), (38, 34)]
            for x1, y1 in points:
                canvas.create_oval(x1 - 4, y1 - 4, x1 + 4, y1 + 4, fill=fg, outline=fg)
            canvas.create_line(27, 19, 16, 30, fill=fg, width=2)
            canvas.create_line(27, 19, 38, 30, fill=fg, width=2)
            canvas.create_line(16, 34, 38, 34, fill=fg, width=2)
        elif icon == "wave":
            canvas.create_line(12, 30, 20, 30, 24, 16, 30, 40, 34, 25, 42, 25, fill=fg, width=2)
        elif icon == "bars":
            for x, h in ((16, 12), (27, 22), (38, 32)):
                canvas.create_rectangle(x, 42 - h, x + 6, 42, fill=fg, outline=fg)

    def add_indicator(self, parent: ttk.Frame, label: str, icon: str, column: int) -> tk.Canvas:
        panel = RoundedPanel(parent, radius=5, height=48)
        panel.grid(row=0, column=column, sticky=tk.EW, padx=(0, 0 if column == 4 else 10))
        panel.grid_propagate(False)
        self.rounded_panels.append(panel)
        frame = panel.inner
        self.card_frames.append(frame)
        frame.grid_rowconfigure(0, minsize=46, weight=1)
        frame.grid_columnconfigure(1, weight=1)
        icon_canvas = tk.Canvas(frame, width=26, height=26, highlightthickness=0)
        icon_canvas.grid(row=0, column=0, padx=(16, 14), sticky=tk.W)
        self.indicator_icon_canvases.append((icon_canvas, icon))
        text_label = ttk.Label(frame, text=label, style="Indicator.TLabel")
        text_label.grid(row=0, column=1, sticky=tk.W)
        self.card_muted_labels.append(text_label)
        pill = tk.Canvas(frame, width=108, height=28, highlightthickness=0)
        pill.grid(row=0, column=2, padx=(12, 16), sticky=tk.E)
        self.indicator_pills.append(pill)
        return pill

    def draw_indicator_icon(self, canvas: tk.Canvas, icon: str) -> None:
        colors = self.current_theme()
        canvas.configure(bg=colors["panel_bg"])
        canvas.delete("all")
        image = self.load_icon_image("indicator", icon, 26)
        if image is not None:
            canvas.create_image(13, 13, image=image)
            return
        fg = colors["panel_fg"]
        if icon == "lock":
            canvas.create_arc(7, 3, 19, 17, start=0, extent=180, outline=fg, width=2)
            canvas.create_rectangle(5, 12, 21, 24, fill=fg, outline=fg)
            canvas.create_rectangle(11, 16, 15, 21, fill=colors["panel_bg"], outline=colors["panel_bg"])
        elif icon == "phone":
            canvas.create_polygon(6, 8, 10, 5, 14, 11, 12, 14, 16, 18, 19, 16, 24, 20, 21, 24, 17, 24, 10, 19, 5, 12, fill=fg, outline=fg)
        elif icon == "share":
            points = [(19, 6), (7, 13), (19, 20)]
            canvas.create_line(10, 13, 16, 9, fill=fg, width=2)
            canvas.create_line(10, 13, 16, 18, fill=fg, width=2)
            for x, y in points:
                canvas.create_oval(x - 4, y - 4, x + 4, y + 4, fill=fg, outline=fg)
        elif icon == "tree":
            for x, y in ((13, 5), (7, 18), (19, 18)):
                canvas.create_rectangle(x - 4, y - 4, x + 4, y + 4, outline=fg, width=2)
            canvas.create_line(13, 8, 13, 13, fill=fg, width=2)
            canvas.create_line(13, 13, 7, 15, fill=fg, width=2)
            canvas.create_line(13, 13, 19, 15, fill=fg, width=2)
        elif icon == "star":
            canvas.create_polygon(13, 3, 16, 10, 24, 10, 18, 15, 20, 23, 13, 18, 6, 23, 8, 15, 2, 10, 10, 10, fill=fg, outline=fg)

    def set_indicator(self, indicator: Optional[tk.Label], active: bool, text: str = "") -> None:
        if indicator is None:
            return
        colors = self.current_theme()
        indicator.configure(bg=colors["panel_bg"])
        indicator.delete("all")
        fill = colors["indicator_on_bg"] if active else colors["indicator_off_bg"]
        fg = colors["indicator_on_fg"] if active else colors["indicator_off_fg"]
        rounded_rect(indicator, 1, 2, 107, 26, 5, fill=fill, outline="", width=1)
        indicator.create_text(54, 14, text=text, fill=fg, font=("Segoe UI", 9, "bold"))

    def set_call_indicator(self, active: bool, available: bool = True) -> None:
        if self.call_indicator is None:
            return
        colors = self.current_theme()
        if active:
            self.call_indicator.configure(bg=colors["panel_bg"])
            self.call_indicator.delete("all")
            rounded_rect(self.call_indicator, 1, 2, 107, 26, 5, fill=colors["call_on_bg"], outline="", width=1)
            self.call_indicator.create_text(54, 14, text="ACTIVE", fill=colors["call_on_fg"], font=("Segoe UI", 9, "bold"))
        else:
            self.set_indicator(self.call_indicator, available, "NONE")

    def update_indicator_colors(self) -> None:
        latched = self.is_latched()
        self.set_site_status_indicator(self.state.current_site_status)
        self.set_call_indicator(latched and self.state.working_channel, latched)
        self.set_indicator(self.net_indicator, self.state.net_status == "TRUE", "CONNECTED" if self.state.net_status == "TRUE" else "NO")
        self.set_indicator(self.rfss_indicator, self.state.rfss_status == "TRUE", hex_to_decimal_text(self.state.current_rfss))
        self.set_indicator(self.preferred_indicator, latched and self.state.preferred, "YES" if latched and self.state.preferred else "NO")

    def is_latched(self) -> bool:
        return self.state.current_site_status.strip().lower() == "latched"

    def set_site_status_indicator(self, status: str) -> None:
        if self.site_status_indicator is None:
            return
        normalized = status.strip() or "Unknown"
        active = normalized.lower() == "latched"
        self.set_indicator(self.site_status_indicator, active, "YES" if active else "NO")

    def sort_table_by(self, column: str) -> None:
        if self.sort_column == column:
            self.sort_descending = not self.sort_descending
        else:
            self.sort_column = column
            self.sort_descending = False
        self.apply_table_sort()

    def table_sort_value(self, column: str, value: str):
        text = str(value or "").strip()
        if column in ("rfss_id", "lra", "rssi"):
            try:
                return int(text)
            except ValueError:
                return 0
        if column == "site_id":
            match = re.search(r"(\d+)", text)
            return int(match.group(1)) if match else 0
        if column == "control":
            match = re.search(r"(\d+(?:\.\d+)?)", text)
            return float(match.group(1)) if match else 0.0
        if column == "spacing":
            try:
                return float(text)
            except ValueError:
                return 0.0
        if column == "quality":
            match = re.search(r"(\d+)", text)
            return int(match.group(1)) if match else -1
        if column == "valid":
            return 1 if text.upper() == "VALID" else 0
        return text.casefold()

    def site_table_values(self, site: SiteReading) -> tuple[str, ...]:
        site_name = self.site_names.get((site.wacn, site.system_id, site.rfss, site.site), "")
        value = site.effective_rssi if site.effective_rssi is not None else site.rssi
        return (
            hex_to_decimal_text(site.rfss),
            site_display(site.site),
            hex_to_decimal_text(site.lra),
            site_name,
            "" if value is None else str(value),
            mhz_short(site.frequency_hz),
            "12.5",
            radio_bars_quality(site.radio_bars, site.no_signal),
            "VALID" if site.valid else "INVALID",
            "FDMA",
        )

    def sorted_neighbor_sites(self) -> list[SiteReading]:
        columns = tuple(self.table_headings.keys())
        column_index = columns.index(self.sort_column) if self.sort_column in columns else columns.index("site_id")
        sites = [
            site
            for site in self.state.sites
            if site.site_class != "FS" and not (site.site == self.state.current_site and site.rfss == self.state.current_rfss)
        ]
        return sorted(
            sites,
            key=lambda site: self.table_sort_value(self.sort_column, self.site_table_values(site)[column_index]),
            reverse=self.sort_descending,
        )

    def apply_table_sort(self) -> None:
        if not hasattr(self, "tree") or not self.sort_column:
            return
        rows = list(self.tree.get_children(""))
        if not rows:
            return
        rows.sort(
            key=lambda row_id: self.table_sort_value(self.sort_column, self.tree.set(row_id, self.sort_column)),
            reverse=self.sort_descending,
        )
        for index, row_id in enumerate(rows):
            self.tree.move(row_id, "", index)
        for column, heading in self.table_headings.items():
            marker = " ▼" if self.sort_descending else " ▲"
            self.tree.heading(column, text=f"{heading}{marker if column == self.sort_column else ''}", command=lambda col=column: self.sort_table_by(col))

    def reload_dsd_names(self) -> None:
        self.system_names = load_system_names()
        self.site_names = load_site_names()
        self.show_system_names = bool(self.system_names)
        self.show_site_names = bool(self.site_names)

    def start_polling(self) -> None:
        if self.poller and self.poller.is_alive():
            return
        self.reload_dsd_names()
        self.args.port = self.port_var.get() or self.args.port
        self.serial_connected = False
        self.last_error = ""
        self.poller = SerialPoller(self.args, self.queue)
        self.poller.start()
        self.update_footer_status()

    def stop_polling(self) -> None:
        if self.poller and self.poller.is_alive():
            self.poller.stop()
        self.serial_connected = False
        self.update_footer_status()

    def save_auto_start_choice(self) -> None:
        save_auto_start(self.auto_start.get())

    def toggle_auto_start_from_header(self) -> None:
        self.auto_start.set(not self.auto_start.get())
        self.save_auto_start_choice()
        self.apply_theme()

    def toggle_theme_from_header(self) -> None:
        self.light_mode.set(not self.light_mode.get())
        self.toggle_theme()

    def select_port(self, value: str) -> None:
        self.port_var.set(value)
        self.on_port_selected()
        self.draw_port_selector()

    def show_port_menu(self, event) -> None:
        self.port_menu.tk_popup(event.x_root, event.y_root)

    def on_port_selected(self, _event=None) -> None:
        selected = self.port_var.get()
        if selected:
            self.args.port = selected

    def drain_queue(self) -> None:
        while True:
            try:
                kind, payload = self.queue.get_nowait()
            except queue.Empty:
                break

            if kind == "error":
                self.last_error = str(payload)
                if self.last_error.startswith("Could not open"):
                    self.serial_connected = False
                self.cc_var.set(str(payload))
            elif kind == "connection":
                self.serial_connected = bool(payload)
            elif kind == "state":
                self.last_parsed_at = time.time()
                self.last_error = ""
                self.state = payload
                self.merge_persistent_site_metadata()
                self.render_state()

        self.update_footer_status()
        self.after(100, self.drain_queue)

    def update_footer_status(self) -> None:
        colors = self.current_theme()
        poller_running = bool(self.poller and self.poller.is_alive() and not self.poller.stop_event.is_set())
        now = time.time()
        recent_window = max(6.0, self.args.interval * 3 + self.args.response_timeout)
        recently_parsed = self.last_parsed_at is not None and now - self.last_parsed_at <= recent_window

        if self.last_error:
            left_text = "Error"
            dot_color = colors["warning"]
        elif not poller_running:
            left_text = "Stopped"
            dot_color = colors["muted_fg"]
        elif recently_parsed:
            left_text = "Receiving"
            dot_color = colors["accent"]
        elif self.serial_connected:
            left_text = "Waiting for data"
            dot_color = colors["warning"]
        else:
            left_text = "Opening port"
            dot_color = colors["warning"]

        if self.state.trunked_only_error and recently_parsed:
            left_text = "Not trunked"

        if self.serial_connected:
            right_text = f"Connected to {self.port_var.get() or self.args.port}"
        elif poller_running:
            right_text = f"Opening {self.port_var.get() or self.args.port}"
        else:
            right_text = "Disconnected"

        self.footer_left_var.set(left_text)
        self.footer_right_var.set(right_text)
        if self.footer_dot is not None:
            self.footer_dot.configure(bg=colors["footer_bg"], fg=dot_color)
        if self.tui_footer_dot is not None:
            self.tui_footer_dot.configure(bg=colors["footer_bg"], fg=dot_color)

    def merge_persistent_site_metadata(self) -> None:
        if self.state.trunked_only_error:
            return

        for site in self.state.sites:
            if site.site_class or site.preference or site.allowed or site.reality or site.rx or site.valid or site.radio_bars or site.no_signal:
                existing = self.site_metadata_cache.get(site_key(site), {})
                has_status_metadata = bool(site.site_class or site.preference or site.allowed or site.reality or site.rx)
                self.site_metadata_cache[site_key(site)] = {
                    "valid": site.valid if has_status_metadata else existing.get("valid", site.valid),
                    "allowed": site.allowed or existing.get("allowed", ""),
                    "site_class": site.site_class or existing.get("site_class", ""),
                    "reality": site.reality or existing.get("reality", ""),
                    "rx": site.rx or existing.get("rx", ""),
                    "preference": site.preference or existing.get("preference", ""),
                    "radio_bars": site.radio_bars or existing.get("radio_bars", 0),
                    "no_signal": site.no_signal or bool(existing.get("no_signal", False)),
                }

        for site in self.state.sites:
            cached = self.site_metadata_cache.get(site_key(site))
            if not cached:
                continue
            site.valid = bool(cached["valid"])
            site.allowed = str(cached["allowed"])
            site.site_class = str(cached["site_class"])
            site.reality = str(cached["reality"])
            site.rx = str(cached["rx"])
            site.preference = str(cached["preference"])
            if not site.radio_bars:
                site.radio_bars = int(cached.get("radio_bars") or 0)
            site.no_signal = bool(cached.get("no_signal")) if not site.radio_bars else site.no_signal

    def render_state(self) -> None:
        status = self.state.current_site_status
        age = time.strftime("%H:%M:%S", time.localtime(self.state.updated_at))
        self.time_var.set(age)

        if self.state.control_channel_hz is not None:
            self.last_control_channel_hz = self.state.control_channel_hz

        self.set_site_status_indicator(status)
        latched = self.is_latched()
        self.set_call_indicator(latched and self.state.working_channel, latched)
        self.set_indicator(self.net_indicator, self.state.net_status == "TRUE", "CONNECTED" if self.state.net_status == "TRUE" else "NO")
        self.set_indicator(self.rfss_indicator, self.state.rfss_status == "TRUE", hex_to_decimal_text(self.state.current_rfss))
        self.set_indicator(self.preferred_indicator, latched and self.state.preferred, "YES" if latched and self.state.preferred else "NO")

        if self.state.trunked_only_error:
            self.site_var.set("Not on trunked channel")
            self.site_name_var.set("")
            self.current_site_card_var.set("Not on trunked channel")
            self.current_site_card_sub_var.set("")
            self.net_var.set("Unknown")
            self.system_name_var.set("")
            self.cc_var.set("Unavailable")
            self.cc_sub_var.set("")
            self.home_var.set("Unavailable")
            self.home_quality_var.set("")
        else:
            system_name = self.system_names.get((self.state.wacn, self.state.system_id), "")
            site_name = self.site_names.get((self.state.wacn, self.state.system_id, self.state.current_rfss, self.state.current_site), "")
            site_number = site_display(self.state.current_site)
            wacn_text = f"WACN {hex_prefixed_text(self.state.wacn)}"
            sys_text = f"SYS {hex_prefixed_text(self.state.system_id)}"
            self.site_var.set(site_display(self.state.current_site))
            self.net_var.set(system_name or wacn_text)
            self.system_name_var.set(f"{wacn_text}   {sys_text}" if system_name else sys_text)
            self.site_name_var.set(site_name)
            self.current_site_card_var.set(site_name or site_number)
            self.current_site_card_sub_var.set(site_number if site_name else "")
            if self.state.ccscan:
                self.cc_var.set("CCSCAN")
                self.cc_sub_var.set("")
            elif self.state.working_channel and self.last_control_channel_hz is not None:
                self.cc_var.set(mhz_short(self.last_control_channel_hz))
                self.cc_sub_var.set(f"CC {hex_to_decimal_text(self.state.current_site)}")
            else:
                self.cc_var.set(mhz_short(self.state.control_channel_hz))
                self.cc_sub_var.set(f"CC {hex_to_decimal_text(self.state.current_site)}")
            self.home_var.set(dbm(self.state.home_effective_rssi))
            self.home_quality_var.set(rssi_quality(self.state.home_effective_rssi))

        for row in self.tree.get_children():
            self.tree.delete(row)
        for site in self.sorted_neighbor_sites():
            self.tree.insert("", tk.END, values=self.site_table_values(site))
        self.apply_table_sort()
        self.draw_signal_bars()
        self.render_tui()

    def draw_signal_bars(self) -> None:
        canvas = self.canvas
        colors = self.current_theme()
        canvas.delete("all")
        width = max(canvas.winfo_width(), 520)
        height = max(canvas.winfo_height(), 160)
        canvas.create_rectangle(0, 0, width, height, fill=colors["canvas_bg"], outline="")
        left = 42
        right = width - 16
        top = 34
        bottom = height - 38
        plot_h = max(80, bottom - top)
        min_dbm = -130
        max_dbm = -50

        canvas.create_text(16, 16, text="RSSI (dBm)", anchor="w", fill=colors["table_fg"], font=("Segoe UI", 10, "bold"))
        for tick in (-50, -70, -90, -110, -130):
            y = bottom - ((tick - min_dbm) / (max_dbm - min_dbm)) * plot_h
            canvas.create_line(left, y, right, y, fill=colors["bar_track"], dash=(3, 2))
            canvas.create_text(left - 8, y, text=str(tick), anchor="e", fill=colors["table_fg"], font=("Segoe UI", 9))

        rows: list[tuple[str, Optional[int], str, bool]] = []
        if self.state.current_site and self.state.home_effective_rssi is not None:
            rows.append((site_display(self.state.current_site), self.state.home_effective_rssi, "home", False))
        for site in self.sorted_neighbor_sites():
            if site.site_class == "FS" and site.no_signal:
                continue
            value = site.effective_rssi if site.effective_rssi is not None else site.rssi
            rows.append((site_display(site.site), value, "site", site.no_signal))

        visible_rows = rows[:13]
        if visible_rows:
            slot = (right - left) / len(visible_rows)
            bar_w = max(22, min(46, slot * 0.48))
        for index, (label, value, kind, no_signal) in enumerate(visible_rows):
            cx = left + slot * index + slot / 2
            canvas.create_text(cx, bottom + 15, text=label, anchor="center", fill=colors["table_fg"], font=("Segoe UI", 9, "bold" if kind == "home" else "normal"))
            if kind == "home":
                canvas.create_text(cx, bottom + 31, text="(Current)", anchor="center", fill=colors["accent_alt"], font=("Segoe UI", 8, "bold"))
            if value is not None:
                normalized = max(0.0, min(1.0, (value - min_dbm) / (max_dbm - min_dbm)))
                y = bottom - normalized * plot_h
                fill = colors["home_bar"] if kind == "home" else colors["site_bar"]
                canvas.create_rectangle(cx - bar_w / 2, y, cx + bar_w / 2, bottom, fill=fill, outline="")
                canvas.create_text(cx, y - 8, text=str(value), anchor="center", fill=colors["table_fg"], font=("Segoe UI", 9, "bold"))
            elif no_signal:
                canvas.create_line(cx - bar_w / 2, bottom - 3, cx + bar_w / 2, bottom - 3, fill=colors["muted_fg"], width=3)
        canvas.create_line(left, bottom, right, bottom, fill=colors["table_fg"], width=1)
        if not rows:
            message = "ProScan only works on trunked systems" if self.state.trunked_only_error else "Waiting for radio status block..."
            canvas.create_text(width / 2, height / 2, text=message, fill=colors["muted_fg"], font=("Segoe UI", 12))

    def on_close(self) -> None:
        if self.poller:
            self.poller.stop()
        self.destroy()


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Graphical Harris P25 serial site monitor")
    parser.add_argument("--port", default="COM1", help="Serial port, default COM1")
    parser.add_argument("--baud", type=int, default=19200, help="Baud rate, default 19200")
    parser.add_argument("--interval", type=float, default=2.0, help="Seconds between polls")
    parser.add_argument("--response-timeout", type=float, default=2.0, help="Seconds to wait for a response block")
    parser.add_argument("--read-timeout", type=float, default=0.2, help="Serial read timeout")
    parser.add_argument("--encoding", default="ascii", help="Serial text encoding")
    parser.add_argument("--command", default="proscan 2", help="Single command to send before carriage return when alternating is disabled")
    parser.add_argument("--commands", nargs="+", default=["proscan 1", "proscan 2"], help="Commands to alternate between while polling")
    parser.add_argument("--alternate-commands", action=argparse.BooleanOptionalAction, default=True, help="Alternate polling commands")
    parser.add_argument("--mock", action="store_true", help="Run using built-in sample data instead of serial")
    parser.add_argument("--auto-start", action=argparse.BooleanOptionalAction, default=load_auto_start_default(), help="Start polling when the app opens")
    parser.add_argument("--rtscts", action=argparse.BooleanOptionalAction, default=False, help="Use RTS/CTS flow control")
    parser.add_argument("--xonxoff", action=argparse.BooleanOptionalAction, default=True, help="Use software flow control")
    parser.add_argument("--dsrdtr", action=argparse.BooleanOptionalAction, default=False, help="Use DSR/DTR flow control")
    return parser


def main() -> None:
    args = build_arg_parser().parse_args()
    app = Dashboard(args)
    app.mainloop()


if __name__ == "__main__":
    main()
