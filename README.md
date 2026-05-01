# OpenFront GTK

Desktop wrapper for [OpenFront.io](https://openfront.io) — the open-source browser RTS. Loads the live site in a native GTK window via WebKit, so you never need to update the wrapper when the game updates.

Not affiliated with the OpenFront.io team. Game is AGPL-3.0; this wrapper is MIT.

## Install

You need Python 3.10+, PyGObject, and WebKit2GTK. On Zorin/Ubuntu/Debian:

```bash
sudo apt install python3-gi gir1.2-gtk-3.0 gir1.2-webkit2-4.1
# or on newer distros:
# sudo apt install python3-gi gir1.2-gtk-3.0 gir1.2-webkit-6.0
```

Then either run directly from the repo:

```bash
git clone https://github.com/yourusername/openfront-gtk.git
cd openfront-gtk
./openfront-gtk
```

Or do a system install (adds a desktop menu entry + icon):

```bash
sudo ./install.sh
# to remove: sudo ./install.sh --uninstall
```

On Fedora: `sudo dnf install python3-gobject gtk3 webkit2gtk4.1`

The app auto-detects GTK 4 + WebKitGTK 6.0 if available and uses those instead.

## What it does

Opens `https://openfront.io/` in an embedded WebKit view with a header bar (back, forward, reload, home, fullscreen, hamburger menu). External links (Discord, GitHub, YouTube, etc.) open in your system browser.

Cookies and cache persist in `~/.local/share/openfront-gtk/` so you stay logged in across sessions. There's a "Clear cache & cookies" option in the menu if something breaks.

Keyboard shortcuts: F11 fullscreen, Ctrl+R / F5 reload, Ctrl+Q quit.

Settings dialog has a toggle to mute the MESA/Vulkan/WebKit stderr noise (on by default). Turn it off if you're debugging something.

## Why not just use a browser?

You can. This is for people who want a dedicated window that doesn't compete with their 40 browser tabs, launches from the app menu, and doesn't bundle 150 MB of Chromium.

## CLI

```
./openfront-gtk [--url URL] [--version]
```

`--url` lets you point at a different instance (staging, self-hosted, etc).

## Troubleshooting

If you get "WebKitGTK is not installed" — you're missing the GIR typelib package. Install `gir1.2-webkit2-4.1` (or `gir1.2-webkit-6.0` on newer distros).

Black screen usually means your GPU doesn't support WebGL. Try: `WEBKIT_DISABLE_COMPOSITING_MODE=1 ./openfront-gtk`

If the game seems stuck on an old version, clear cache from the menu.

## License

MIT. See [LICENSE](LICENSE).
