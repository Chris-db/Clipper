@echo off
REM Run the clipper using its own virtual environment. Usage: clip SOURCE START END [options]
"%~dp0.venv\Scripts\python.exe" "%~dp0clip.py" %*
