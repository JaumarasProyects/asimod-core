@echo off
echo Iniciando ASIMOD en modo DEBUG INTERNO...
call .\venv\Scripts\activate
python main_standalone.py > debug_asimod.log 2>&1
echo Ejecucion terminada. Revisa debug_asimod.log.
pause
