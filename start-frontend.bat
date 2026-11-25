@echo off
setlocal
cd /d "%~dp0frontend"

where node >nul 2>nul
if errorlevel 1 (
  echo Node.js 20 or newer is required. Install Node.js LTS, then reopen this file.
  pause
  exit /b 1
)


if not exist node_modules (
  echo Installing frontend dependencies for the first run...
  npm install
  if errorlevel 1 (
    echo Frontend dependency installation failed. Check the error above and your internet connection.
    pause
    exit /b 1
  )
)

npm run dev
pause
