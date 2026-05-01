#!/usr/bin/env bash
# install.sh — install OpenFront GTK system-wide on Zorin/Ubuntu/Debian.
# Run with: sudo ./install.sh
# Uninstall with: sudo ./install.sh --uninstall

set -euo pipefail

PREFIX="${PREFIX:-/usr/local}"
APP_NAME="openfront-gtk"
SHARE_DIR="${PREFIX}/share/${APP_NAME}"
BIN_LINK="${PREFIX}/bin/${APP_NAME}"
DESKTOP_FILE="/usr/share/applications/${APP_NAME}.desktop"
ICON_FILE="/usr/share/icons/hicolor/scalable/apps/${APP_NAME}.svg"

if [[ "${1:-}" == "--uninstall" ]]; then
  rm -rf "${SHARE_DIR}"
  rm -f "${BIN_LINK}" "${DESKTOP_FILE}" "${ICON_FILE}"
  command -v update-desktop-database >/dev/null && update-desktop-database || true
  command -v gtk-update-icon-cache >/dev/null && \
    gtk-update-icon-cache -f /usr/share/icons/hicolor || true
  echo "OpenFront GTK uninstalled."
  exit 0
fi

if [[ $EUID -ne 0 ]]; then
  echo "This installer must be run as root. Try: sudo ./install.sh" >&2
  exit 1
fi

# --- Dependency check / install -------------------------------------------
echo ">>> Checking system dependencies..."
MISSING=()
for pkg in python3 python3-gi gir1.2-gtk-3.0; do
  dpkg -s "$pkg" >/dev/null 2>&1 || MISSING+=("$pkg")
done

# WebKit: prefer 4.1, fall back to 4.0. (WebKitGTK 6.0 is auto-detected
# at runtime if also installed, but 4.1 is what Zorin OS 17 ships.)
if ! dpkg -s gir1.2-webkit2-4.1 >/dev/null 2>&1 && \
   ! dpkg -s gir1.2-webkit2-4.0 >/dev/null 2>&1 && \
   ! dpkg -s gir1.2-webkit-6.0  >/dev/null 2>&1; then
  if apt-cache show gir1.2-webkit2-4.1 >/dev/null 2>&1; then
    MISSING+=("gir1.2-webkit2-4.1")
  elif apt-cache show gir1.2-webkit2-4.0 >/dev/null 2>&1; then
    MISSING+=("gir1.2-webkit2-4.0")
  else
    MISSING+=("gir1.2-webkit-6.0")
  fi
fi

if [[ ${#MISSING[@]} -gt 0 ]]; then
  echo ">>> Installing missing packages: ${MISSING[*]}"
  apt update
  apt install -y "${MISSING[@]}"
fi

# --- Copy files -----------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
echo ">>> Installing to ${SHARE_DIR}"
install -d "${SHARE_DIR}"
cp -r "${SCRIPT_DIR}/openfront_gtk" "${SHARE_DIR}/"
cp "${SCRIPT_DIR}/openfront-gtk" "${SHARE_DIR}/"
chmod +x "${SHARE_DIR}/openfront-gtk"

ln -sf "${SHARE_DIR}/openfront-gtk" "${BIN_LINK}"

install -Dm644 "${SCRIPT_DIR}/packaging/openfront-gtk.desktop" "${DESKTOP_FILE}"
install -Dm644 "${SCRIPT_DIR}/packaging/openfront-gtk.svg" "${ICON_FILE}"

command -v update-desktop-database >/dev/null && \
  update-desktop-database /usr/share/applications || true
command -v gtk-update-icon-cache >/dev/null && \
  gtk-update-icon-cache -f /usr/share/icons/hicolor || true

echo
echo "✓ OpenFront GTK installed."
echo "  Launch from your application menu, or run: openfront-gtk"
