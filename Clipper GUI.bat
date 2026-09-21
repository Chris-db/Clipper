@echo off
REM Double-click to open the Clipper window (no console).
start "" "%~dp0.venv\Scripts\pythonw.exe" "%~dp0clipper_gui.py"
