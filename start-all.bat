@echo off
setlocal
if not exist "%~dp0backend\.env" (
  echo Run start-backend.bat once first so it creates backend\.env.
  call "%~dp0start-backend.bat"
  exit /b 0
)
start "VoiceCare Backend" cmd /k call "%~dp0start-backend.bat"
start "VoiceCare Frontend" cmd /k call "%~dp0start-frontend.bat"
