@echo off
REM ASIMOD Remote - Cloudflare Tunnel Permanente
REM ==============================================

echo.
echo [1/2] Iniciando ASIMOD API...
start "ASIMOD API" cmd /k "python run_api.py"

echo.
echo [2/2] Iniciando Cloudflare Tunnel de forma dinámica...
start "CLOUDFLARED" cmd /k "python core\tunnels\run_tunnel.py"

echo.
echo ========================================
echo Esperando a que todo inicie...
echo.
echo Cuando veas la URL en la ventana CLOUDFLARED, esa es tu URL FIJA.
echo Sera: https://asimod.noglowgames.com
echo.
echo Copiala y pegala en tu navegador del movil.
echo.
echo Presiona cualquier tecla para cerrar todo al terminar...
pause >nul

taskkill /f /im python.exe 2>nul
taskkill /f /im cloudflared.exe 2>nul
