$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$App = Join-Path $Root "p25_radio_dashboard_v2.py"
$ImportPathHook = Join-Path $Root "pyinstaller_import_path_hook.py"
$Name = "ProScanMonitor"
$Version = "R00A02"
$BuildStamp = Get-Date -Format "yyyyMMdd_HHmmss"

$Dist = Join-Path $Root "release_build_$Version`_$BuildStamp"
$Work = Join-Path $Root ".pyinstaller_work"
$Spec = Join-Path $Root ".pyinstaller_spec"
$Venv = Join-Path $Root ".build_venv"
$PackageRoot = Join-Path $Root "release_package"
$Package = Join-Path $PackageRoot $Name
$Zip = Join-Path $PackageRoot "$($Name)_$Version.zip"

$CodexPython = Join-Path $HOME ".cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
if (Test-Path $CodexPython) {
    $BasePython = $CodexPython
} else {
    $BasePython = "python"
}
$PythonRoot = Split-Path -Parent $BasePython
$PythonDlls = Join-Path $PythonRoot "DLLs"
$PythonTcl = Join-Path $PythonRoot "tcl"

if (!(Test-Path $App)) {
    throw "Could not find app script: $App"
}
if (!(Test-Path $ImportPathHook)) {
    throw "Could not find PyInstaller import path hook: $ImportPathHook"
}
if (!(Test-Path (Join-Path $Root "harris_logo_header.png"))) {
    throw "Could not find logo asset beside this script."
}
if (!(Test-Path (Join-Path $Root "icons"))) {
    throw "Could not find icons folder beside this script."
}
if (!(Test-Path (Join-Path $PythonRoot "Lib\tkinter"))) {
    throw "The selected Python runtime does not include tkinter."
}
if (!(Test-Path (Join-Path $PythonTcl "tcl8.6"))) {
    throw "The selected Python runtime does not include Tcl data."
}
if (!(Test-Path (Join-Path $PythonTcl "tk8.6"))) {
    throw "The selected Python runtime does not include Tk data."
}

if (!(Test-Path (Join-Path $Venv "Scripts\python.exe"))) {
    Write-Host "Creating local build environment..."
    & $BasePython -m venv $Venv
}

$VenvPython = Join-Path $Venv "Scripts\python.exe"
$BuildPython = $VenvPython
$BuildSitePackages = Join-Path $Venv "Lib\site-packages"

$PreviousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
& $BuildPython -m PyInstaller --version *> $null
$HasPyInstaller = ($LASTEXITCODE -eq 0)
$ErrorActionPreference = $PreviousErrorActionPreference

if (!$HasPyInstaller) {
    Write-Host "Installing PyInstaller into the local build environment..."
    & $VenvPython -m pip install --disable-pip-version-check pyinstaller
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller install failed."
    }
}

Remove-Item -Recurse -Force -ErrorAction SilentlyContinue $Dist
Remove-Item -Recurse -Force -ErrorAction SilentlyContinue $Work
Remove-Item -Recurse -Force -ErrorAction SilentlyContinue $Spec
Remove-Item -Recurse -Force -ErrorAction SilentlyContinue $Package
Remove-Item -Force -ErrorAction SilentlyContinue $Zip

Write-Host "Building $Name.exe..."
& $BuildPython -m PyInstaller `
    --noconfirm `
    --clean `
    --onedir `
    --windowed `
    --name $Name `
    --distpath $Dist `
    --workpath $Work `
    --specpath $Spec `
    --runtime-hook $ImportPathHook `
    --hidden-import "_tkinter" `
    --add-binary "$PythonDlls\_tkinter.pyd;." `
    --add-binary "$PythonDlls\tcl86t.dll;." `
    --add-binary "$PythonDlls\tk86t.dll;." `
    --add-data "$PythonRoot\Lib\tkinter;tkinter" `
    --add-data "$PythonTcl\tcl8.6;_tcl_data" `
    --add-data "$PythonTcl\tk8.6;_tk_data" `
    --add-data "$Root\harris_logo_header.png;." `
    --add-data "$Root\icons;icons" `
    $App

New-Item -ItemType Directory -Force $Package | Out-Null
Copy-Item -Recurse -Force (Join-Path (Join-Path $Dist $Name) "*") $Package
Copy-Item -ErrorAction SilentlyContinue (Join-Path $Root "DSDPlus.networks") $Package
Copy-Item -ErrorAction SilentlyContinue (Join-Path $Root "DSDPlus.sites") $Package
Copy-Item (Join-Path $Root "p25_radio_dashboard_config.default.json") (Join-Path $Package "p25_radio_dashboard_config.json")
Get-ChildItem $Package -Recurse -Force -Filter "README*" | Remove-Item -Force

Compress-Archive -Path $Package -DestinationPath $Zip -Force

Write-Host ""
Write-Host "Release package created:"
Write-Host $Zip
