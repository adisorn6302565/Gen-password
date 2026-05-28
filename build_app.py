import os
import subprocess
import sys


def build_exe():
    print("--- AegisVault EXE Builder ---")
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    
    # Ensure PyInstaller is installed
    try:
        import PyInstaller
    except ImportError:
        print("Installing PyInstaller...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])

    fast_mode = "--onefile" not in sys.argv

    # Build command
    # Default onedir mode starts much faster with PySide6 WebEngine because it
    # does not extract hundreds of MB of Qt files on every launch.
    # Pass --onefile to this script only when you really need one portable EXE.
    # --windowed: No console window
    # --name: The name of the output EXE
    cmd = [
        "pyinstaller",
        "--noconfirm",
        "--windowed",
        "--add-data", "ui;ui",
        "--name", "AegisVault",
        "main.py"
    ]

    if not fast_mode:
        cmd.insert(2, "--onefile")

    print(f"Running: {' '.join(cmd)}")
    subprocess.check_call(cmd)

    if fast_mode:
        stale_onefile = os.path.join("dist", "AegisVault.exe")
        if os.path.exists(stale_onefile):
            os.remove(stale_onefile)
            print("Removed old slow one-file EXE from 'dist'.")
        print("\nSUCCESS! Fast-start build is in 'dist\\AegisVault\\AegisVault.exe'.")
        print("Tip: keep the whole 'dist\\AegisVault' folder together when moving it.")
    else:
        print("\nSUCCESS! One-file build is in 'dist\\AegisVault.exe'.")
        print("Note: one-file builds open slower because PyInstaller extracts Qt WebEngine each time.")

if __name__ == "__main__":
    build_exe()
