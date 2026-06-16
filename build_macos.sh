#!/bin/bash
# Build Hidebar.app (unsigned) and package it as a distributable DMG.
# Usage: ./build_macos.sh
set -e
cd "$(dirname "$0")"

echo "==> Installing build + runtime dependencies"
python3 -m pip install --quiet --upgrade \
    pyinstaller requests SpeechRecognition pyaudio pyttsx3 pyobjc

echo "==> Cleaning previous build"
rm -rf build dist

echo "==> Building Hidebar.app"
python3 -m PyInstaller --noconfirm Hidebar.spec

echo "==> Packaging DMG"
APP="dist/Hidebar.app"
DMG="dist/Hidebar.dmg"
STAGING="dist/dmg"
rm -rf "$STAGING" "$DMG"
mkdir -p "$STAGING"
cp -R "$APP" "$STAGING/"
# Add an Applications symlink so users can drag-to-install
ln -s /Applications "$STAGING/Applications"
hdiutil create -volname "Hidebar" -srcfolder "$STAGING" -ov -format UDZO "$DMG"
rm -rf "$STAGING"

echo ""
echo "==> Done"
echo "    App: $APP"
echo "    DMG: $DMG  (share this file)"
echo ""
echo "First launch on another Mac (unsigned): right-click the app -> Open,"
echo "then confirm. Or run: xattr -dr com.apple.quarantine /Applications/Hidebar.app"
