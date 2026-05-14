fn main() {
    // Re-run the build script when any icon file changes so the embedded
    // window icon (and bundled installer icons) stay in sync after running
    // `cargo tauri icon`. Without this, Cargo treats .png/.ico changes as
    // irrelevant to the Rust target and skips re-linking, so Lector.exe
    // keeps its previously-embedded icon as a Win32 resource. Matches the
    // Resero pattern (LLC-006 src-tauri/build.rs).
    println!("cargo:rerun-if-changed=icons");
    // frontendDist content is baked into lector.exe at build time. Without this
    // declaration, Cargo skips re-linking when only static/ changes, leaving the
    // .exe with stale embedded HTML/CSS/JS. Caught the second time during the
    // Thu 5/14 clean-VM test when an API-base hardcode in static/index.html
    // didn't reach customers because cargo reused the cached binary.
    println!("cargo:rerun-if-changed=../static");
    tauri_build::build()
}
