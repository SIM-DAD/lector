@echo off
setlocal
cd /d "%~dp0"

:: ── Kill any prior Lector pythonw before starting fresh ──────────────────────
:: NSIS uninstaller does not terminate running Lector processes. Every
:: install-test-reinstall cycle would otherwise leave a zombie holding port
:: 7860 and serving pre-update code, defeating the new install entirely.
:: Caught after two days of chasing a phantom "splash hangs at 8%" bug in
:: dev 2026-05-15 where each fresh install loaded the previous attempt's
:: server.py from memory instead of the patched disk file.
powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"Name='pythonw.exe' OR Name='python.exe'\" -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -match 'server\.py' -and ($_.CommandLine -match 'Lector' -or $_.CommandLine -match 'lector') } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }" >nul 2>&1

:: ── Log path lives in %LOCALAPPDATA%\Lector\ ─────────────────────────────────
:: %~dp0 resolves to the install dir, which on a perMachine NSIS install is
:: C:\Program Files\Lector\ — read-only for non-admin users. Writing the log
:: there silently failed after install and left customers with no diagnostic
:: trail when first launch broke. %LOCALAPPDATA% is per-user writable and is
:: where the venv lives anyway, so co-locate the log.
if not exist "%LOCALAPPDATA%\Lector" mkdir "%LOCALAPPDATA%\Lector" 2>nul
set LOG=%LOCALAPPDATA%\Lector\launch_log.txt
echo [%date% %time%] Launch started > "%LOG%"
echo Working dir: %CD% >> "%LOG%"

:: ── Keep .venv on a local drive to avoid syncing 3 GB to Google Drive ─────────
:: Store in %LOCALAPPDATA%\Lector\.venv so it survives project moves.
set VENV=%LOCALAPPDATA%\Lector\.venv
echo Venv: %VENV% >> "%LOG%"

:: ── Is the venv ready? ────────────────────────────────────────────────────────
if exist "%VENV%\Scripts\python.exe" (
    echo [OK] venv found, skipping setup >> "%LOG%"
    goto :activate
)

:: ── Full setup ────────────────────────────────────────────────────────────────
echo [SETUP] venv not found, running first-time setup >> "%LOG%"

echo [1/4] Creating virtual environment (Python 3.12)...
py -3.12 -m venv "%VENV%" >> "%LOG%" 2>&1
if errorlevel 1 (
    echo ERROR: py -3.12 failed >> "%LOG%"
    echo.
    echo ERROR: Python 3.12 not found.
    echo Install it from: https://www.python.org/downloads/release/python-3128/
    goto :fail
)
echo [1/4] venv created >> "%LOG%"

call "%VENV%\Scripts\activate.bat"

echo [2/4] Installing PyTorch 2.6.0 + CUDA 12.4  (downloading ~2.5 GB, please wait)...
pip install torch==2.6.0 torchaudio==2.6.0 --index-url https://download.pytorch.org/whl/cu124 >> "%LOG%" 2>&1
if errorlevel 1 ( echo ERROR: PyTorch install failed >> "%LOG%" & echo ERROR: PyTorch failed & goto :fail )
echo [2/4] PyTorch installed >> "%LOG%"

echo [3/4] Installing numpy...
pip install numpy >> "%LOG%" 2>&1
if errorlevel 1 ( echo ERROR: numpy failed >> "%LOG%" & goto :fail )
echo [3/4] numpy installed >> "%LOG%"

echo [4/4] Installing remaining dependencies  (may take a few minutes)...
pip install -r requirements.txt >> "%LOG%" 2>&1
if errorlevel 1 ( echo ERROR: requirements.txt install failed >> "%LOG%" & echo ERROR: pip install failed & goto :fail )
echo [4/4] All dependencies installed >> "%LOG%"

echo.
echo Setup complete.
echo.
goto :launch

:: ── Activate existing venv ────────────────────────────────────────────────────
:activate
call "%VENV%\Scripts\activate.bat"
if errorlevel 1 (
    echo ERROR: activate failed >> "%LOG%"
    echo ERROR: Could not activate venv. Delete "%VENV%" and rerun.
    goto :fail
)
echo [OK] venv activated >> "%LOG%"

:: ── Launch server ─────────────────────────────────────────────────────────────
:launch
echo [%date% %time%] Launching server >> "%LOG%"
echo Starting server at http://127.0.0.1:7860
echo Log: %LOG%
echo.

:: Skip TTS preload at startup (workaround for a torch+CUDA initialization
:: crash that fires when Kokoro/F5 load inside the uvicorn startup thread,
:: but does not fire when they load inside asyncio.to_thread workers from
:: an HTTP /tts handler). First /tts call pays a ~15s lazy-load latency;
:: subsequent calls are warm.
set LECTOR_SKIP_TTS_PRELOAD=1

:: Tell server.py we're inside the Tauri shell, not raw dev. Routes
:: voices/library/cache through platformdirs (install dir is read-only on
:: Program Files) and suppresses the auto-opened browser tab (Tauri webview
:: is the UI).
set LECTOR_PRODUCTION=1

"%VENV%\Scripts\pythonw.exe" server.py >> "%LOG%" 2>&1
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
