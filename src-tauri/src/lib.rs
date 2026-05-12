use std::process::Command;

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_notification::init())
        .setup(|_app| {
            // Find the install directory (where the Tauri exe lives) and locate
            // launch-silent.vbs, shipped alongside as an NSIS resource. It wraps
            // launch.bat with a 0-window WScript run so customers don't see the
            // console flash. launch.bat sets up the embedded Python venv on first
            // run and starts the FastAPI server on :7860.
            let exe_dir = std::env::current_exe()
                .expect("failed to get exe path")
                .parent()
                .expect("exe has no parent dir")
                .to_path_buf();

            let vbs_path = exe_dir.join("launch-silent.vbs");

            if vbs_path.exists() {
                Command::new("wscript.exe")
                    .arg(&vbs_path)
                    .current_dir(&exe_dir)
                    .spawn()
                    .expect("failed to spawn launch-silent.vbs");
            } else {
                eprintln!(
                    "launch-silent.vbs not found at {:?} — server must be started manually",
                    vbs_path
                );
            }

            // The frontend (static/index.html) detects Tauri and uses
            // http://127.0.0.1:7860 for API calls; its splash polls /status
            // until the server binds. No further wiring needed here.

            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running Lector");
}
