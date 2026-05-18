@echo off
setlocal
cd /d "%~dp0"

:: ──────────────────────────────────────────────────────────────────────────────
:: Lector launch script
::
:: All Python dependency installation moved to NSIS install-time (see
:: src-tauri/installer-hooks.nsh, commit landing 2026-05-16). This script no
:: longer creates a venv, no longer requires system Python, and no longer
:: downloads anything. Bundled CPython lives at %~dp0\python\ — populated by
:: the installer's POSTINSTALL hook. First launch is now O(seconds), not
:: O(tens of minutes).
::
:: Why the change: campus-laptop clean test 2026-05-16 caught launch.bat dying
:: at `py -3.12 not found`. Customer machines do not have Python. The 2026-04-25
:: pivot scoped this fix but only the Python sources got bundled; the runtime
:: + deps install never followed. Resolved now.
:: ──────────────────────────────────────────────────────────────────────────────

:: ── Kill any prior Lector pythonw before starting fresh ───────────────────────
:: NSIS uninstaller does not always terminate running Lector processes during
:: a reinstall, and a stale pythonw holding port 7860 with the prior version's
:: in-memory server.py defeats the new install entirely. The NSIS PREUNINSTALL
:: hook also does this for the install path; we keep it here so direct relaunch
:: (without reinstall) still self-heals.
powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"Name='pythonw.exe' OR Name='python.exe'\" -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -match 'server\.py' -and ($_.CommandLine -match 'Lector' -or $_.CommandLine -match 'lector') } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }" >nul 2>&1

:: ── Log path lives in %LOCALAPPDATA%\Lector\ ──────────────────────────────────
:: %~dp0 resolves to the install dir (C:\Program Files\Lector\ on perMachine),
:: which is read-only for non-admin users. %LOCALAPPDATA% is per-user writable.
if not exist "%LOCALAPPDATA%\Lector" mkdir "%LOCALAPPDATA%\Lector" 2>nul
set "LOG=%LOCALAPPDATA%\Lector\launch_log.txt"
echo [%date% %time%] Launch started > "%LOG%"
echo Working dir: %CD% >> "%LOG%"

:: ── Resolve bundled Python ────────────────────────────────────────────────────
set "PY=%~dp0python\pythonw.exe"
echo Python: %PY% >> "%LOG%"

if not exist "%PY%" (
    echo ERROR: bundled Python missing at %PY% >> "%LOG%"
    echo.
    echo ERROR: Lector install is incomplete - bundled Python runtime not found.
    echo Expected at: %PY%
    echo.
    echo This usually means the installer's dependency-install step was
    echo cancelled, blocked by antivirus, or failed mid-way. Re-run the
    echo Lector installer ^(it will overwrite the broken install^).
    goto :fail
)

:: ── Sanity check core deps exist  (catches install-hook silent failure) ───────
:: Cheap import check against the bundled Python's site-packages. fastapi
:: imports in <100ms cold; if it's missing, the install hook never ran. Kokoro
:: and torch are deliberately NOT checked here because they each take many
:: seconds to import (spaCy/ONNX/CUDA-DLL probing) and would push first-launch
:: time from O(seconds) to O(minute). Server startup will surface real torch
:: or kokoro failures via /status returning non-200.
"%~dp0python\python.exe" -c "import fastapi" 2>>"%LOG%"
if errorlevel 1 (
    echo ERROR: bundled Python is present but FastAPI failed to import. >> "%LOG%"
    echo.
    echo ERROR: Lector dependencies are missing or broken.
    echo The installer's dependency-install step probably failed.
    echo Re-run the Lector installer to repair.
    echo.
    echo Log: %LOG%
    goto :fail
)
echo [OK] core dep import succeeded >> "%LOG%"

:: ── Launch server ─────────────────────────────────────────────────────────────
echo [%date% %time%] Launching server >> "%LOG%"
echo Starting server at http://127.0.0.1:7860
echo Log: %LOG%
echo.

:: Skip TTS preload at startup (workaround for a torch+CUDA initialization
:: crash that fires when Kokoro/F5 load inside the uvicorn startup thread,
:: but does not fire when they load inside asyncio.to_thread workers from
:: an HTTP /tts handler). First /tts call pays a ~15s lazy-load latency;
:: subsequent calls are warm.
set "LECTOR_SKIP_TTS_PRELOAD=1"

:: Tell server.py we're inside the Tauri shell, not raw dev. Routes
:: voices/library/cache through platformdirs (install dir is read-only on
:: Program Files) and suppresses the auto-opened browser tab (Tauri webview
:: is the UI).
set "LECTOR_PRODUCTION=1"

"%PY%" server.py >> "%LOG%" 2>&1
set ERR=%errorlevel%
echo [%date% %time%] Server exited, code %ERR% >> "%LOG%"

echo.
if %ERR% neq 0 (
    echo Server exited with an error. Showing last 60 lines of log:
    echo.
    powershell -noprofile -command "Get-Content '%LOG%' -Tail 60"
    echo.
    echo Full log: %LOG%
)
pause
exit /b %ERR%

:: ── Failure handler ───────────────────────────────────────────────────────────
:fail
echo.
echo FAILED. Showing last 60 lines of log:
echo.
powershell -noprofile -command "Get-Content '%LOG%' -Tail 60"
echo.
echo Full log: %LOG%
pause
exit /b 1
