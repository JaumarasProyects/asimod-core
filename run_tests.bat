@echo off
echo Running ASIMOD Tests...
echo.

python -m pytest tests/ -v --tb=short

echo.
echo ========================================
echo Tests completed.
echo ========================================
pause
