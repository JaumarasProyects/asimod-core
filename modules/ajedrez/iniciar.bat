@echo off
echo Iniciando servidor...
cd /d "%~dp0"
start /b python -m http.server 8080 >nul 2>&1
timeout /t 2 /nobreak >nul
start http://localhost:8080
echo Abre http://localhost:8080 en tu navegador
pause
