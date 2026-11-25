@echo off
setlocal
cd /d "%~dp0backend"

if not exist ".env" (
  copy ".env.example" ".env" >nul
  echo Created backend\.env from the example file.
  echo Open backend\.env and add your ElevenLabs and Google API credentials.
  echo Then run this file again.
  pause
  exit /b 0
)


where uv >nul 2>nul
if errorlevel 1 (
  echo uv is not installed. Install it with:
  echo powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 ^| iex"
  pause
  exit /b 1
)

uv sync
if errorlevel 1 (
  echo Backend dependency installation failed. Check the error above and your internet connection.
  pause
  exit /b 1
)

uv run bot.py
pause
