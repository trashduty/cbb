@echo off
setlocal
cd /d "%~dp0"
where uv >nul 2>nul
if errorlevel 1 (
  echo UV is required. Install it with: py -m pip install uv
  pause
  exit /b 1
)
uv run --no-project run-local.py --start-date 2026-11-01 --days 7
if errorlevel 1 (
  echo Barttorvik failed. No successful upload was confirmed.
) else (
  echo Finished.
)
pause
