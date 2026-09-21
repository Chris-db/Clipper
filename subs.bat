@echo off
REM Add subtitles to a video, keeping it exactly as-is (no cutting, no reframing).
REM Drag a video file onto this icon, or run:  subs "C:\path\to\video.mp4"
REM Output lands in the clips\ folder as <name>_subtitled.mp4
if "%~1"=="" (
  echo Drag a video file onto this file, or run:  subs "path\to\video.mp4"
  pause
  exit /b
)
"%~dp0.venv\Scripts\python.exe" "%~dp0clip.py" "%~1"
echo.
pause
