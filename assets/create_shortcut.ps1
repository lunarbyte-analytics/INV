$ErrorActionPreference = "Stop"
$dir = Split-Path -Parent $MyInvocation.MyCommand.Path
$root = Split-Path -Parent $dir
$ico = Join-Path $dir "inv.ico"
$bat = Join-Path $root "UruchomINV.bat"
$lnkPath = Join-Path $root "INV.lnk"

if (-not (Test-Path $ico)) { throw "Brak $ico" }
if (-not (Test-Path $bat)) { throw "Brak $bat" }

$ws = New-Object -ComObject WScript.Shell
$s = $ws.CreateShortcut($lnkPath)
$s.TargetPath = $bat
$s.WorkingDirectory = $root
$s.IconLocation = "$ico,0"
$s.Description = "INV - Faktury"
$s.Save()
Write-Host "Utworzono skrot: $lnkPath"
