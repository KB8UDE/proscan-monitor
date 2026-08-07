# ProScan Monitor

ProScan Monitor is a Windows dashboard for Harris P25 radios that support the `proscan` serial commands. It polls the radio, parses neighbor-site information, and displays the current site, network, control channel, home RSSI, status indicators, RSSI bar chart, and neighbor table.

Current release: `R00A02`

## Features

- Polls `proscan 1` and `proscan 2` alternately.
- Defaults to XON/XOFF serial flow control.
- Shows RFSS, LRA, site ID, RSSI, control-channel frequency, signal quality, validity, and CC type.
- Keeps current/home site information in the top cards and shows neighbor sites in the graph and table.
- Supports light and dark modes.
- Includes optional text UI mode.
- Can load optional DSDPlus network and site name files.
- Saves local preferences in `p25_radio_dashboard_config.json`.

## Download And Run

Download the latest release zip from GitHub Releases, then unzip the whole folder.

Run:

```text
ProScanMonitor\ProScanMonitor.exe
```

Keep the `_internal` folder beside `ProScanMonitor.exe`. The app needs that folder because it contains the bundled Python/Tk runtime.

## Radio Connection

Default serial settings:

```text
Baud: 19200
Data: 8N1
Flow control: XON/XOFF
Poll interval: 2 seconds
Commands: proscan 1, proscan 2
```

Select the COM port in the app before starting.

## Optional Name Lookups

The app can display network and site names from DSDPlus files. Place these files in the same folder as `ProScanMonitor.exe`:

```text
DSDPlus.networks
DSDPlus.sites
```

If the files are missing, or a matching name is not found, the app falls back to the radio-provided IDs.

Only P25 entries are used when the file includes a protocol field.

Example `DSDPlus.networks`:

```csv
P25,BEE00.348,Example Public Safety Network
```

Example `DSDPlus.sites`:

```csv
P25,BEE00.348,03.01,Downtown Simulcast
P25,BEE00.348,03.24,North Site
```

Hex values may be written with or without `0x`.

## Running From Source

Python 3 with Tkinter is required.

Live radio:

```powershell
.\run_p25_dashboard_v2.bat
```

Mock/demo mode:

```powershell
.\run_p25_dashboard_v2_mock.bat
```

## Building A Release

The build script is included so releases can be reproduced.

Requirements:

- Windows
- Python 3 with Tkinter
- Internet access the first time PyInstaller is installed into the local build environment

Build:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\build_exe.ps1
```

The release zip is created at:

```text
release_package\ProScanMonitor_R00A02.zip
```

The release uses PyInstaller `--onedir` packaging. This intentionally creates an app folder instead of a single self-extracting exe, which is friendlier to antivirus tools and easier to troubleshoot.

## Repository Notes

Local settings and build output are intentionally excluded from Git:

```text
p25_radio_dashboard_config.json
release_build*/
release_package*/
.build_venv/
.pyinstaller_work/
.pyinstaller_spec/
```

Use `p25_radio_dashboard_config.default.json` as the default settings template.
