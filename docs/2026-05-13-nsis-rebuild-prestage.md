---
type: design
status: draft
zone: llc
project: LLC-003
last_modified: 2026-05-13T05:30:00-05:00
tldr: "Pre-stage notes for the Wed 5/13 11:00-13:00 NSIS rebuild block. Maps the current state of src-tauri + launch scripts against the work items from the 5/7 audit. Three Tier-0 deltas remain in tauri.conf.json (bundle.resources, bundle.windows.nsis.license, pythonw.exe in launch.bat). Build + clean-machine smoke test fills the rest of the block."
---

# NSIS Rebuild: Pre-Stage (2026-05-13)

Pre-staging for the Wed 5/13 11:00-13:00 calendar block. Goal: walk into the block knowing exactly which files change and in what order so we spend the two hours on the build/test loop, not on rediscovery.

## Already done (don't redo)

| Item | Where | State |
|---|---|---|
| `lib.rs` spawns `wscript.exe launch-silent.vbs` | `src-tauri/src/lib.rs:14-33` | Shipped 2026-05-11 (commit pre-pivot). `current_dir(&exe_dir)` set; `cargo check` passed. |
| `launch-silent.vbs` 0-window wrapper | repo root | Shipped. Wraps `launch.bat` with `WshShell.Run ..., 0, False`. |
| `launch.bat` first-run pip install + server start | repo root | Shipped. Sets `LECTOR_PRODUCTION=1` + `LECTOR_SKIP_TTS_PRELOAD=1`. Logs to `launch_log.txt`. |
| `server.py` env-gated `USER_DATA_DIR` via `platformdirs` | `server.py:75-95` | Shipped 2026-05-11. Suppresses `webbrowser.open` under prod. |
| `tauri.conf.json` targets `nsis` only | `tauri.conf.json:33` | Shipped. Mac deferred per 4/25 pivot. |
| Tauri icon set | `src-tauri/icons/` | All five files present (32, 128, 128@2x, ico, png). Referenced in `tauri.conf.json:34-39`. |
| Frontend splash polling `/status` | `static/index.html:1088-1140` | Shipped. Tauri detection via `window.__TAURI__`; API base flips to `http://127.0.0.1:7860`. |
| `LICENSE` file at repo root | `LICENSE` | Proprietary license. Ready to point NSIS at. |
| Vendored simdad-crypto wheel | `vendor/simdad_crypto-0.1.0-py3-none-any.whl` | Referenced from `requirements.txt:30` via relative path. Must ship in bundle. |

## Deltas needed in the 11:00 block

### Tier-0 launch blockers (must land Wed)

**D1. `bundle.resources` in `tauri.conf.json`.** Right now the bundle config has `"externalBin": []` and no resources list, so the NSIS installer only ships `Lector.exe` + the icons. Customer install would land an empty Tauri shell. Need to add a `resources` entry that ships everything launch.bat references with `%~dp0` paths.

Files to include (relative to `src-tauri/` per Tauri convention; paths resolve to repo siblings):

```json
"resources": [
  "../server.py",
  "../crypto.py",
  "../library_store.py",
  "../license_manager.py",
  "../text_parser.py",
  "../requirements.txt",
  "../launch.bat",
  "../launch-silent.vbs",
  "../static",
  "../vendor"
]
```

NOT bundled:
- `voices/`: repo dev artifacts. Built-in Kokoro voices ship with the pip package; F5 custom voices live in APPDATA at runtime.
- `audio_cache/`, `library/`, `librosa-cache/`: runtime state, populated under APPDATA.
- `archive/`, `build/`, `dist/`, `docs/`, `comms/`, `video/`, `__pycache__/`, `.venv`: dev cruft.
- `launch_log.txt`, `pip_err.txt`, `pip_out.txt`: runtime logs (should be in `.gitignore`; not for shipping anyway).

**D2. `bundle.windows.nsis.license` in `tauri.conf.json`.** Add the NSIS license-text page so customers see the proprietary EULA before install. Add to `bundle.windows`:

```json
"windows": {
  "wix": { "language": "en-US" },
  "nsis": {
    "license": "../LICENSE",
    "installerIcon": "icons/icon.ico",
    "installMode": "perMachine"
  }
}
```

(`installerIcon` is belt-and-suspenders; Tauri usually picks it up from `bundle.icon`. `installMode: perMachine` matches the existing Program Files install assumption in launch.bat / server.py.)

**D3. `pythonw.exe` in `launch.bat:86`.** Switch the server invocation from `python.exe` to `pythonw.exe` so even if launch-silent.vbs is bypassed (e.g., user double-clicks launch.bat for debugging) the Python child process doesn't flash a console window. `pythonw.exe` ships in every CPython install alongside `python.exe`.

```diff
- "%VENV%\Scripts\python.exe" server.py >> "%LOG%" 2>&1
+ "%VENV%\Scripts\pythonw.exe" server.py >> "%LOG%" 2>&1
```

Note: stdout/stderr piping still works under pythonw via the `>>` redirect; pythonw just doesn't allocate a console.

### Tier-1 polish (defer to v1.0.1 if time gets tight)

**P1. Splash timeout in `static/index.html:1091`.** The `while (true)` poll loop has no timeout. If launch.bat fails (e.g., Python 3.12 not installed), customers see an infinite "Starting Lector..." spinner. Add a ~60s timeout that surfaces `launch_log.txt` path + a Restart link. Not a Tier-0 blocker (fallback is the customer kills the Tauri window via taskbar), but it's a $29 polish gap per the 5/7 audit's fit-for-price list.

**P2. Crash dialog in `lib.rs:27`.** Current `.expect("failed to spawn launch-silent.vbs")` panics the Tauri shell silently. Wrap in a `match` and show a `tauri-plugin-dialog` message box instead. Defensible to defer because the only way this fires is missing `launch-silent.vbs`, which the bundle.resources change above prevents.

## Execution order for the 11:00 block

1. **Apply D1 + D2 to tauri.conf.json.** ~10 min. Single file edit.
2. **Apply D3 to launch.bat.** ~2 min. Single line.
3. **Run `pnpm tauri build`** from `src-tauri/` (or `cd src-tauri && cargo tauri build` if that's the working invocation; check `package.json` scripts). ~5-15 min first time, faster on rebuild.
4. **Verify NSIS output** at `src-tauri/target/release/bundle/nsis/Lector_1.0.0_x64-setup.exe`. Expected size: ~10-20 MB (Tauri shell + Python sources + static/ + vendor/ wheel). Customer's ~2.5 GB PyTorch download happens at first-run pip install via launch.bat, not at install time.
5. **Sign the installer** with the EV cert toolchain per `yubikey-activation-runbook.md`. Use `/n "SIM DAD LLC"`, not `/a`. (This is the Sat 5/17 step in the original plan, but a dry-run sign here is cheap and catches signing-config bugs early.)
6. **Clean-VM smoke test slot is Thu 5/14, not today.** Today the goal is just to produce a signed installer that walks through the NSIS wizard, lands files in `C:\Program Files\Lector\`, and the launch shortcut starts the Tauri shell which spawns launch.bat which finds server.py next to itself. End-to-end audio playback is Thu.

## Verification checklist (Wed)

- [ ] `tauri.conf.json` validates (no JSON syntax error)
- [ ] `pnpm tauri build` (or `cargo tauri build`) completes without error
- [ ] `target/release/bundle/nsis/Lector_1.0.0_x64-setup.exe` exists
- [ ] Installer wizard shows the LICENSE text on the license-agreement page
- [ ] After install, `C:\Program Files\Lector\` contains: `Lector.exe`, `server.py`, `crypto.py`, `library_store.py`, `license_manager.py`, `text_parser.py`, `requirements.txt`, `launch.bat`, `launch-silent.vbs`, `static/`, `vendor/simdad_crypto-0.1.0-py3-none-any.whl`
- [ ] Launching `Lector.exe` (or the Start Menu shortcut) opens the Tauri window with the splash
- [ ] Splash transitions to the editor once the FastAPI server binds (may take ~5-10 min on first run during pip install, which is expected and documented)
- [ ] No console window flashes during launch

## Risk register / known gotchas

- **pnpm vs npm**: Lector's `src-tauri/` package.json might assume one or the other. Check `src-tauri/package.json` scripts (probably `tauri`, `dev`, `build`). If it uses pnpm and pnpm isn't on PATH for this shell, fall back to `cargo tauri build` directly.
- **Tauri resource path resolution**: `../server.py` is relative to `src-tauri/`, which is what Tauri expects. If `tauri.conf.json` ends up with `resources: ["server.py"]` (no `..`), the build will fail with "file not found." Per the Tauri 2.x docs.
- **PyTorch download time**: First-run pip install pulls 2.5 GB of PyTorch CUDA wheels. The customer sees the Tauri splash spinning for 5-15 min depending on bandwidth. Acceptable per the customer expectation set by `feedback_install_vs_launch.md` ("install-time work belongs in the installer with visible progress; launch must be fast"). However: launch.bat does the install on FIRST LAUNCH, not at NSIS-install time. So the customer hits the NSIS wizard → fast → click Launch → splash for 15 min. That's a Tier-1 polish gap (per the 5/7 audit's "Tauri-native progress window during pip install" item) but not Tier-0.
- **Lector_1.0.0_x64-setup.exe filename**: Tauri auto-generates this from `productName` + `version` + arch. If the lector-web download CTA hardcodes a different filename, it'll 404. Verify against `lector-web/index.html` download links before publish.
- **SmartScreen reputation reset**: Per `reference_ev_smartscreen_reality.md`, EV cert gives publisher reputation but per-file reputation seeds organically. The signed installer will show "SIM DAD LLC, Private Organization, Illinois, US" but customers still see a mild warning until reputation builds (~days). Day 0 marketing should set expectations.

## After the block ends

If everything lands cleanly, the post-block STATUS update:

- `next_action_oneline` → "Run the Thu 5/14 09:00-12:00 clean-VM round-trip test (install on a fresh Windows VM, full save/load/TTS/uninstall cycle)."
- Recent Changes entry for the NSIS rebuild
- Hand off to the Thu calendar block

If something fails (e.g., resource path issue, sign-tool config bug, license-page formatting), document the failure inline in this file and adjust next_action.
