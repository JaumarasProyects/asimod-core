@echo off
setlocal enabledelayedexpansion

echo.
echo ========================================
echo    ASIMOD - Interfaz Remoto Web
echo ========================================
echo.

for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr "IPv4"') do (
    set "IP=%%a"
    set "IP=!IP: =!"
    if not "!IP!"=="" goto :found
)
:found

echo Abriendo interfaz web...
echo.
echo Este PC:       http://localhost:8000
echo Red WiFi:     http://!IP!:8000
echo.
start http://localhost:8000
echo Presiona Ctrl+C para cerrar
echo.
pause
