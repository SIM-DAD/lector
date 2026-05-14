fn main() {
    // Re-run the build script when any icon file changes so the embedded
    // window icon (and bundled installer icons) stay in sync after running
    // `cargo tauri icon`. Without this, Cargo treats .png/.ico changes as
    // irrelevant to the Rust target and skips re-linking, so Lector.exe
    // keeps its previously-embedded icon as a Win32 resource. Matches the
    // Resero pattern (LLC-006 src-tauri/build.rs).
    println!("cargo:rerun-if-changed=icons");
    tauri_build::build()
}
