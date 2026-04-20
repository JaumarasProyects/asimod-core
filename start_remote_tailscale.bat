@echo off
title ASIMOD - Tailscale Connector
cls
echo ========================================================
echo   INCICIANDO ASIMOD (MODO RED PRIVADA TAILSCALE)
echo ========================================================
echo.

:: Intentar detectar la IP antes de arrancar
python check_tailscale.py

echo.
echo Arrancando Servidor API...
echo --------------------------------------------------------
python run_api.py
pause
