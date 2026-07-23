@echo off
chcp 65001 >nul
cd /d "%~dp0"

REM Wskazówka: w Explorerze uruchamiaj skrót INV.lnk (ikona).
REM Jeśli go nie ma — uruchom raz UtworzSkrotINV.bat.

REM Uruchomienie z wirtualnego środowiska, jeśli istnieje (opcjonalnie utworzone przez: py -3 -m venv .venv)
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" -m pip install -r "%~dp0requirements.txt" -q 2>nul
  ".venv\Scripts\python.exe" "%~dp0main.py"
  if errorlevel 1 pause
  exit /b %ERRORLEVEL%
)

where py >nul 2>nul
if %ERRORLEVEL%==0 (
  py -3 -m pip install -r "%~dp0requirements.txt" -q 2>nul
  py -3 "%~dp0main.py"
  if errorlevel 1 pause
  exit /b %ERRORLEVEL%
)

where python >nul 2>nul
if %ERRORLEVEL%==0 (
  python -m pip install -r "%~dp0requirements.txt" -q 2>nul
  python "%~dp0main.py"
  if errorlevel 1 pause
  exit /b %ERRORLEVEL%
)

echo.
echo Nie znaleziono Pythona na tym komputerze.
echo.
echo Zainstaluj Python 3.10 lub nowszy ze strony:
echo   https://www.python.org/downloads/windows/
echo.
echo Przy instalacji zaznacz opcje dodania Pythona do PATH, np.:
echo   "Add python.exe to PATH" albo "Add Python to environment variables".
echo Po instalacji uruchom ponownie ten plik (UruchomINV.bat).
echo.
pause
exit /b 1
