# Harris ProScan Monitor R00A02

Run live:

```powershell
.\run_p25_dashboard_v2.bat
```

Run mock data:

```powershell
.\run_p25_dashboard_v2_mock.bat
```

R00A02 alternates `proscan 1` and `proscan 2`, supports light/dark and text UI display modes, uses icon-enhanced top cards, shows the RSSI graph as vertical bars, and stores local preferences in `p25_radio_dashboard_config.json`.

## Release Build

Create the release package:

```powershell
.\build_exe.ps1
```

The release zip is written to `release_package\ProScanMonitor_R00A02.zip`. Build folders and local settings are intentionally excluded from Git.

## Optional CSV Lookups

Place these DSDPlus files in the same folder as the app. If they are missing, the extra name fields are hidden. The loader only uses `P25` rows when a protocol field is present.

`DSDPlus.networks`:

```csv
P25,BEE00.348,Example Public Safety Network
```

`DSDPlus.sites`:

```csv
P25,BEE00.348,03.01,Downtown Simulcast
P25,BEE00.348,03.24,North Site
```

Headered CSV-style files are also accepted. Hex values may be written with or without `0x`.
