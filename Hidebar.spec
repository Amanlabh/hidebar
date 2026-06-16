# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for Hidebar — builds Hidebar.app (macOS).
from PyInstaller.utils.hooks import collect_submodules, collect_dynamic_libs

hiddenimports = []
# pyttsx3 picks its driver at runtime (nsss on macOS) — not auto-detected
hiddenimports += ["pyttsx3.drivers", "pyttsx3.drivers.nsss"]
# pyobjc frameworks used for the always-on-top / all-spaces overlay
hiddenimports += collect_submodules("AppKit")
hiddenimports += collect_submodules("Cocoa")
hiddenimports += ["objc", "Quartz"]
# speech recognition + audio
hiddenimports += ["speech_recognition"]

# pyaudio ships the portaudio dylib — make sure it's bundled
binaries = collect_dynamic_libs("pyaudio")

a = Analysis(
    ["Hidebar.py"],
    pathex=[],
    binaries=binaries,
    datas=[],
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Hidebar",
    debug=False,
    strip=False,
    upx=False,
    console=False,          # windowed (GUI) app, no terminal
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="Hidebar",
)
app = BUNDLE(
    coll,
    name="Hidebar.app",
    icon=None,
    bundle_identifier="com.hidebar.app",
    info_plist={
        "CFBundleName": "Hidebar",
        "CFBundleDisplayName": "Hidebar",
        "CFBundleShortVersionString": "1.0.0",
        "CFBundleVersion": "1.0.0",
        "NSHighResolutionCapable": True,
        # Permission prompts shown to the user on first use:
        "NSMicrophoneUsageDescription":
            "Hidebar uses the microphone (or a loopback device) to transcribe questions.",
        # Keep the overlay out of the Dock/Cmd-Tab if you prefer (set True):
        "LSUIElement": False,
    },
)
