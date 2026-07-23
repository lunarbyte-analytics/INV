@echo off
chcp 65001 >nul
cd /d "%~dp0"

if not exist "assets\inv.ico" (
  echo Brak pliku assets\inv.ico
  pause
  exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0assets\create_shortcut.ps1"
if errorlevel 1 (
  echo Nie udalo sie utworzyc skrotu.
  pause
  exit /b 1
)

echo.
echo Gotowe. Uruchamiaj aplikacje przez skrot INV.lnk (z ikona).
echo Mozesz skopiowac INV.lnk na pulpit lub przypiac do paska zadan.
echo.
pause
