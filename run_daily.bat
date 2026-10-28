@echo off
REM Deskpilot daily run -- launched by Windows Task Scheduler on weekdays 16:00 SGT.
REM Runs the whole routine locally (reads .env, hits Gemini, delivers to Telegram).
cd /d "%~dp0"
if not exist "logs" mkdir "logs"
echo ======== %DATE% %TIME% ======== >> "logs\daily_run.log"
py -3.14 -m deskpilot.run "Run today's desk plan" >> "logs\daily_run.log" 2>&1
echo exit code %ERRORLEVEL% >> "logs\daily_run.log"
