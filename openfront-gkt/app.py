"""OpenFront GTK desktop wrapper.

Embeds https://openfront.io in a native GTK window using WebKitGTK.

Compatibility:
  * GTK 3 + WebKit2GTK 4.1  ← Zorin OS 17 (Ubuntu 22.04 base), Debian 12,
                              Ubuntu 22.04/24.04. Default, well-tested path.
  * GTK 4 + WebKitGTK 6.0    ← opportunistic upgrade for newer distros.

Because the page is loaded live from openfront.io, this wrapper does not
need to be updated when the game itself updates (the game is in alpha
and changes frequently).
"""
from __future__ import annotations

import argparse
import glob
import os
import sys
import sysconfig
from pathlib import Path

import gi

# ---------------------------------------------------------------------------
# Negotiate GTK + WebKit versions.
#
# We can't blindly chain try/except with gi.require_version, because once a
# namespace is pinned to a version (even tentatively), it can't be re-pinned
# in the same process. So we first inspect which typelibs are installed on
# disk and only then commit to a combination.
# ---------------------------------------------------------------------------
def _typelib_available(namespace: str, version: str) -> bool:
    """Return True if `<namespace>-<version>.typelib` is installed."""
    search_dirs = [
        "/usr/lib/x86_64-linux-gnu/girepository-1.0",
        "/usr/lib64/girepository-1.0",
        "/usr/lib/girepository-1.0",
        "/usr/local/lib/girepository-1.0",
        os.path.join(sys.prefix, "lib", "girepository-1.0"),
        os.path.join(sys.prefix, "lib64", "girepository-1.0"),
    ]
    search_dirs += glob.glob("/usr/lib/*/girepository-1.0")
    extra = os.environ.get("GI_TYPELIB_PATH", "")
    if extra:
        search_dirs = extra.split(os.pathsep) + search_dirs
    fname = f"{namespace}-{version}.typelib"
    seen = set()
    for d in search_dirs:
        if not d or d in seen:
            continue
        seen.add(d)
        if os.path.exists(os.path.join(d, fname)):
            return True
    return False


_WEBKIT_API: str
_GTK_API: str

if _typelib_available("Gtk", "4.0") and _typelib_available("WebKit", "6.0"):
    _GTK_API, _WEBKIT_API = "4.0", "6.0"
elif _typelib_available("Gtk", "3.0") and _typelib_available("WebKit2", "4.1"):
    _GTK_API, _WEBKIT_API = "3.0", "4.1"
elif _typelib_available("Gtk", "3.0") and _typelib_available("WebKit2", "4.0"):
    _GTK_API, _WEBKIT_API = "3.0", "4.0"
else:
    sys.stderr.write(
        "ERROR: WebKitGTK is not installed.\n"
        "On Zorin/Ubuntu/Debian, install with:\n"
        "  sudo apt install python3-gi gir1.2-gtk-3.0 gir1.2-webkit2-4.1\n"
        "  or on newer distros: sudo apt install python3-gi gir1.2-gtk-3.0 gir1.2-webkit-6.0\n"
        "On Fedora:\n"
        "  sudo dnf install python3-gobject gtk3 webkit2gtk4.1\n"
    )
    sys.exit(1)

gi.require_version("Gtk", _GTK_API)
gi.require_version("Gdk", _GTK_API)

if _WEBKIT_API == "6.0":
    gi.require_version("WebKit", "6.0")
    from gi.repository import WebKit  # type: ignore  # noqa: E402
else:
    gi.require_version("WebKit2", _WEBKIT_API)
    from gi.repository import WebKit2 as WebKit  # type: ignore  # noqa: E402

from gi.repository import Gtk, Gdk, Gio, GLib, GdkPixbuf  # noqa: E402

_IS_GTK4 = _GTK_API == "4.0"

APP_ID = "io.github.openfront_gtk"
APP_NAME = "OpenFront"
HOME_URL = "https://openfront.io/"
ALLOWED_HOST_SUFFIXES = (
    "openfront.io",
    "discord.com",
    "discord.gg",
    "github.com",
    "patreon.com",
    "youtube.com",
    "youtu.be",
    "google.com",        # OAuth flows
    "googleapis.com",
    "googleusercontent.com",
    "gstatic.com",
)


def _user_data_dir() -> Path:
    base = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
    path = Path(base) / "openfront-gtk"
    path.mkdir(parents=True, exist_ok=True)
    return path


# ---------------------------------------------------------------------------
# Persistent settings
# ---------------------------------------------------------------------------
import json as _json

_SETTINGS_DEFAULTS: dict = {
    "mute_stderr": True,  # silence WebKit/MESA/Vulkan noise by default
}


def _settings_path() -> Path:
    return _user_data_dir() / "settings.json"


def load_settings() -> dict:
    try:
        data = _json.loads(_settings_path().read_text())
        return {**_SETTINGS_DEFAULTS, **data}
    except Exception:
        return dict(_SETTINGS_DEFAULTS)


def save_settings(settings: dict) -> None:
    try:
        _settings_path().write_text(_json.dumps(settings, indent=2))
    except Exception as exc:
        sys.stderr.write(f"openfront-gtk: could not save settings: {exc}\n")


def apply_mute(settings: dict) -> None:
    """Redirect stderr to /dev/null when mute_stderr is True."""
    if settings.get("mute_stderr", True):
        try:
            devnull = open(os.devnull, "w")
            os.dup2(devnull.fileno(), sys.stderr.fileno())
        except Exception:
            pass  # non-fatal


def _build_webview() -> "WebKit.WebView":
    data_dir = _user_data_dir()
    cache_dir = data_dir / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)

    if _WEBKIT_API == "6.0":
        network_session = WebKit.NetworkSession.new(str(data_dir), str(cache_dir))
        cookie_manager = network_session.get_cookie_manager()
        cookie_manager.set_persistent_storage(
            str(data_dir / "cookies.sqlite"),
            WebKit.CookiePersistentStorage.SQLITE,
        )
        webview = WebKit.WebView(network_session=network_session)
    else:
        # WebKit2 4.x: WebsiteDataManager is constructed via GObject keyword
        # args, not a .new() factory.
        data_manager = WebKit.WebsiteDataManager(
            base_data_directory=str(data_dir),
            base_cache_directory=str(cache_dir),
        )
        cookie_manager = data_manager.get_cookie_manager()
        cookie_manager.set_persistent_storage(
            str(data_dir / "cookies.sqlite"),
            WebKit.CookiePersistentStorage.SQLITE,
        )
        context = WebKit.WebContext.new_with_website_data_manager(data_manager)
        webview = WebKit.WebView.new_with_context(context)

    settings = webview.get_settings()
    settings.set_enable_javascript(True)
    settings.set_enable_webgl(True)
    settings.set_enable_smooth_scrolling(True)
    settings.set_enable_developer_extras(True)
    settings.set_javascript_can_open_windows_automatically(True)
    try:
        settings.set_user_agent_with_application_details("OpenFrontGTK", "1.0")
    except Exception:
        pass
    if hasattr(settings, "set_hardware_acceleration_policy"):
        try:
            settings.set_hardware_acceleration_policy(
                WebKit.HardwareAccelerationPolicy.ALWAYS
            )
        except Exception:
            pass
    return webview


def _host_allowed(uri: str) -> bool:
    try:
        from urllib.parse import urlparse
        host = (urlparse(uri).hostname or "").lower()
    except Exception:
        return False
    if not host:
        return False
    return any(host == h or host.endswith("." + h) for h in ALLOWED_HOST_SUFFIXES)


# ---------------------------------------------------------------------------
# Icon helper — load from installed theme or fall back to the repo's SVG
# ---------------------------------------------------------------------------

def _set_window_icon(window: "Gtk.Window") -> None:
    """Set the window icon from the hicolor theme if installed, else from the
    SVG file next to this module (works when running from a git clone)."""
    # Try the theme name first (only works after `sudo ./install.sh`).
    icon_theme = Gtk.IconTheme.get_default()
    if icon_theme.has_icon("openfront-gtk"):
        window.set_icon_name("openfront-gtk")
        return
    # Fall back: load the SVG from packaging/ relative to this file.
    import os as _os
    svg = _os.path.join(
        _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))),
        "packaging", "openfront-gtk.svg",
    )
    if _os.path.exists(svg):
        try:
            pb = GdkPixbuf.Pixbuf.new_from_file_at_size(svg, 128, 128)
            window.set_icon(pb)
            return
        except Exception:
            pass
    # Last resort: generic system icon.
    window.set_icon_name("applications-games")


# ---------------------------------------------------------------------------
# Window mixin — shared signal handlers
# ---------------------------------------------------------------------------

class _WindowMixin:
    webview: "WebKit.WebView"
    _back_btn: "Gtk.Button"
    _forward_btn: "Gtk.Button"

    def _connect_webview_signals(self) -> None:
        self.webview.connect("load-changed", self._on_load_changed)
        self.webview.connect("load-failed", self._on_load_failed)
        self.webview.connect("decide-policy", self._on_decide_policy)
        self.webview.connect("create", self._on_create_window)

    def _update_nav_buttons(self) -> None:
        self._back_btn.set_sensitive(self.webview.can_go_back())
        self._forward_btn.set_sensitive(self.webview.can_go_forward())

    def _on_load_changed(self, _wv, event) -> None:
        if event == WebKit.LoadEvent.FINISHED:
            self._update_nav_buttons()
            self._set_status_visible(False)
        elif event == WebKit.LoadEvent.STARTED:
            self._set_status("Loading OpenFront…")
            self._set_status_visible(True)

    def _on_load_failed(self, _wv, _event, failing_uri, error) -> bool:
        self._set_status(
            f"Failed to load {failing_uri}\n\n{error.message}\n\n"
            "Check your internet connection, then click Reload."
        )
        self._set_status_visible(True)
        return False

    def _on_decide_policy(self, _wv, decision, decision_type) -> bool:
        if decision_type != WebKit.PolicyDecisionType.NAVIGATION_ACTION:
            return False
        nav_action = decision.get_navigation_action()
        request = nav_action.get_request()
        uri = request.get_uri() or ""
        if not uri or uri.startswith(("about:", "data:", "blob:")):
            return False
        if _host_allowed(uri):
            return False
        decision.ignore()
        try:
            Gio.AppInfo.launch_default_for_uri(uri, None)
        except GLib.Error:
            pass
        return True

    def _on_create_window(self, _wv, nav_action):
        request = nav_action.get_request() if nav_action else None
        uri = request.get_uri() if request else ""
        if uri:
            if _host_allowed(uri):
                self.webview.load_uri(uri)
            else:
                try:
                    Gio.AppInfo.launch_default_for_uri(uri, None)
                except GLib.Error:
                    pass
        return None

    def _set_status(self, text: str) -> None:
        raise NotImplementedError

    def _set_status_visible(self, visible: bool) -> None:
        raise NotImplementedError


# ---------------------------------------------------------------------------
# GTK 4 window (modern systems)
# ---------------------------------------------------------------------------
if _IS_GTK4:

    class OpenFrontWindow(Gtk.ApplicationWindow, _WindowMixin):  # type: ignore[misc]
        def __init__(self, app, start_url: str = HOME_URL) -> None:
            super().__init__(application=app, title=APP_NAME)
            self.set_default_size(1280, 800)
            _set_window_icon(self)

            header = Gtk.HeaderBar()
            header.set_show_title_buttons(True)
            self.set_titlebar(header)

            def mkbtn(icon, tip, cb):
                b = Gtk.Button.new_from_icon_name(icon)
                b.set_tooltip_text(tip)
                b.connect("clicked", cb)
                return b

            self._back_btn = mkbtn("go-previous-symbolic", "Back",
                                   lambda *_: self.webview.go_back())
            self._forward_btn = mkbtn("go-next-symbolic", "Forward",
                                      lambda *_: self.webview.go_forward())
            for b in (self._back_btn, self._forward_btn,
                      mkbtn("view-refresh-symbolic", "Reload",
                            lambda *_: self.webview.reload()),
                      mkbtn("go-home-symbolic", "Home",
                            lambda *_: self.webview.load_uri(HOME_URL))):
                header.pack_start(b)

            self._fs_btn = mkbtn("view-fullscreen-symbolic",
                                 "Toggle fullscreen (F11)",
                                 self._on_fullscreen_toggle)
            header.pack_end(self._fs_btn)

            menu = Gio.Menu()
            menu.append("Settings", "app.settings")
            menu.append("Open in system browser", "app.open-external")
            menu.append("Clear cache & cookies", "app.clear-data")
            menu.append("Quit", "app.quit")
            menu_btn = Gtk.MenuButton()
            menu_btn.set_icon_name("open-menu-symbolic")
            menu_btn.set_menu_model(menu)
            header.pack_end(menu_btn)

            self.webview = _build_webview()
            self.webview.set_hexpand(True)
            self.webview.set_vexpand(True)
            self._connect_webview_signals()

            self._status_label = Gtk.Label(label="Loading OpenFront…")
            self._status_label.add_css_class("dim-label")
            self._status_label.set_halign(Gtk.Align.CENTER)
            self._status_label.set_valign(Gtk.Align.CENTER)
            self._status_label.set_wrap(True)

            overlay = Gtk.Overlay()
            overlay.set_child(self.webview)
            overlay.add_overlay(self._status_label)
            self.set_child(overlay)

            ctrl = Gtk.EventControllerKey()
            ctrl.connect("key-pressed", self._on_key_pressed)
            self.add_controller(ctrl)

            self._update_nav_buttons()
            self.webview.load_uri(start_url)

        def _set_status(self, text: str) -> None:
            self._status_label.set_text(text)

        def _set_status_visible(self, visible: bool) -> None:
            self._status_label.set_visible(visible)

        def _on_fullscreen_toggle(self, *_a) -> None:
            if self.is_fullscreen():
                self.unfullscreen()
                self._fs_btn.set_icon_name("view-fullscreen-symbolic")
            else:
                self.fullscreen()
                self._fs_btn.set_icon_name("view-restore-symbolic")

        def _on_key_pressed(self, _ctrl, keyval, _kc, state) -> bool:
            ctrl = bool(state & Gdk.ModifierType.CONTROL_MASK)
            if keyval == Gdk.KEY_F11:
                self._on_fullscreen_toggle(); return True
            if keyval == Gdk.KEY_Escape and self.is_fullscreen():
                self._on_fullscreen_toggle(); return True
            if keyval == Gdk.KEY_F5 or (ctrl and keyval in (Gdk.KEY_r, Gdk.KEY_R)):
                self.webview.reload(); return True
            if ctrl and keyval in (Gdk.KEY_q, Gdk.KEY_Q):
                self.close(); return True
            return False

# ---------------------------------------------------------------------------
# GTK 3 window (Zorin OS 17 default)
# ---------------------------------------------------------------------------
else:

    class OpenFrontWindow(Gtk.ApplicationWindow, _WindowMixin):  # type: ignore[misc,no-redef]
        def __init__(self, app, start_url: str = HOME_URL) -> None:
            super().__init__(application=app, title=APP_NAME)
            self.set_default_size(1280, 800)
            _set_window_icon(self)

            header = Gtk.HeaderBar()
            header.set_show_close_button(True)
            header.set_title(APP_NAME)
            self.set_titlebar(header)

            def mkbtn(icon, tip, cb):
                b = Gtk.Button.new_from_icon_name(icon, Gtk.IconSize.BUTTON)
                b.set_tooltip_text(tip)
                b.connect("clicked", cb)
                return b

            self._back_btn = mkbtn("go-previous-symbolic", "Back",
                                   lambda *_: self.webview.go_back())
            self._forward_btn = mkbtn("go-next-symbolic", "Forward",
                                      lambda *_: self.webview.go_forward())
            for b in (self._back_btn, self._forward_btn,
                      mkbtn("view-refresh-symbolic", "Reload",
                            lambda *_: self.webview.reload()),
                      mkbtn("go-home-symbolic", "Home",
                            lambda *_: self.webview.load_uri(HOME_URL))):
                header.pack_start(b)

            self._fs_btn = mkbtn("view-fullscreen-symbolic",
                                 "Toggle fullscreen (F11)",
                                 self._on_fullscreen_toggle)
            header.pack_end(self._fs_btn)

            menu_model = Gio.Menu()
            menu_model.append("Settings", "app.settings")
            menu_model.append("Open in system browser", "app.open-external")
            menu_model.append("Clear cache & cookies", "app.clear-data")
            menu_model.append("Quit", "app.quit")
            menu_btn = Gtk.MenuButton()
            menu_btn.set_image(Gtk.Image.new_from_icon_name(
                "open-menu-symbolic", Gtk.IconSize.BUTTON))
            menu_btn.set_use_popover(True)
            menu_btn.set_menu_model(menu_model)
            header.pack_end(menu_btn)

            self.webview = _build_webview()
            self._connect_webview_signals()

            self._status_label = Gtk.Label()
            self._status_label.set_text("Loading OpenFront…")
            self._status_label.set_halign(Gtk.Align.CENTER)
            self._status_label.set_valign(Gtk.Align.CENTER)
            self._status_label.set_line_wrap(True)
            self._status_label.set_no_show_all(True)

            overlay = Gtk.Overlay()
            overlay.add(self.webview)
            overlay.add_overlay(self._status_label)
            self.add(overlay)

            self.connect("key-press-event", self._on_key_press)

            self.show_all()
            self._update_nav_buttons()
            self.webview.load_uri(start_url)

        def _set_status(self, text: str) -> None:
            self._status_label.set_text(text)

        def _set_status_visible(self, visible: bool) -> None:
            if visible:
                self._status_label.show()
            else:
                self._status_label.hide()

        def _is_fullscreen(self) -> bool:
            window = self.get_window()
            if window is None:
                return False
            return bool(window.get_state() & Gdk.WindowState.FULLSCREEN)

        def _on_fullscreen_toggle(self, *_a) -> None:
            if self._is_fullscreen():
                self.unfullscreen()
                self._fs_btn.set_image(Gtk.Image.new_from_icon_name(
                    "view-fullscreen-symbolic", Gtk.IconSize.BUTTON))
            else:
                self.fullscreen()
                self._fs_btn.set_image(Gtk.Image.new_from_icon_name(
                    "view-restore-symbolic", Gtk.IconSize.BUTTON))

        def _on_key_press(self, _w, event) -> bool:
            keyval = event.keyval
            state = event.state
            ctrl = bool(state & Gdk.ModifierType.CONTROL_MASK)
            if keyval == Gdk.KEY_F11:
                self._on_fullscreen_toggle(); return True
            if keyval == Gdk.KEY_Escape and self._is_fullscreen():
                self._on_fullscreen_toggle(); return True
            if keyval == Gdk.KEY_F5 or (ctrl and keyval in (Gdk.KEY_r, Gdk.KEY_R)):
                self.webview.reload(); return True
            if ctrl and keyval in (Gdk.KEY_q, Gdk.KEY_Q):
                self.close(); return True
            return False


# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------

class OpenFrontApp(Gtk.Application):
    def __init__(self, start_url: str = HOME_URL) -> None:
        super().__init__(
            application_id=APP_ID,
            flags=Gio.ApplicationFlags.NON_UNIQUE,
        )
        self._start_url = start_url
        self._window: "OpenFrontWindow | None" = None

    def do_startup(self) -> None:  # type: ignore[override]
        Gtk.Application.do_startup(self)
        for name, callback in (
            ("settings", self._on_settings),
            ("quit", lambda *_: self.quit()),
            ("open-external", self._on_open_external),
            ("clear-data", self._on_clear_data),
        ):
            action = Gio.SimpleAction.new(name, None)
            action.connect("activate", callback)
            self.add_action(action)
        self.set_accels_for_action("app.quit", ["<Primary>q"])

    def do_activate(self) -> None:  # type: ignore[override]
        if self._window is None:
            self._window = OpenFrontWindow(self, self._start_url)
        self._window.present()

    def _on_settings(self, *_a) -> None:
        """Show a Settings dialog with an About tab and a Settings tab."""
        settings = load_settings()
        dlg = Gtk.Dialog(
            title="OpenFront GTK — Settings",
            transient_for=self._window,
            modal=True,
        )
        dlg.set_default_size(420, 300)

        # ---- Notebook (tabs) ----
        notebook = Gtk.Notebook()

        # ---- Settings tab ----
        settings_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        settings_box.set_border_width(18)

        mute_check = Gtk.CheckButton(
            label="Mute verbose stderr messages"
        )
        mute_check.set_tooltip_text(
            "Silences GPU driver warnings, WebKit codec notices, and other "
            "low-level noise that clutters the terminal.\n"
            "Disable this if you need to debug a crash or rendering issue."
        )
        mute_check.set_active(settings.get("mute_stderr", True))
        settings_box.pack_start(mute_check, False, False, 0)

        note = Gtk.Label()
        note.set_markup(
            '<span size="small" foreground="#888888">'
            "Takes effect on next launch.</span>"
        )
        note.set_halign(Gtk.Align.START)
        settings_box.pack_start(note, False, False, 0)

        notebook.append_page(settings_box, Gtk.Label(label="Settings"))

        # ---- About tab ----
        about_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        about_box.set_border_width(18)

        for text, markup in (
            (f"<b>{APP_NAME} GTK</b>", True),
            ("Version 1.0.0", False),
            (
                "Unofficial desktop wrapper for OpenFront.io.\n"
                "The game loads live — no wrapper update needed when the game updates.",
                False,
            ),
            (
                '<a href="https://openfront.io/">openfront.io</a>  •  '
                f'GTK {_GTK_API}  •  WebKit {_WEBKIT_API}',
                True,
            ),
        ):
            lbl = Gtk.Label()
            if markup:
                lbl.set_markup(text)
            else:
                lbl.set_text(text)
            lbl.set_line_wrap(True)
            lbl.set_halign(Gtk.Align.START)
            about_box.pack_start(lbl, False, False, 0)

        notebook.append_page(about_box, Gtk.Label(label="About"))

        content_area = dlg.get_content_area()
        content_area.pack_start(notebook, True, True, 0)
        content_area.set_spacing(0)

        dlg.add_button("Close", Gtk.ResponseType.CLOSE)
        dlg.show_all()
        dlg.run()

        # Persist whatever state the checkbox is in when closed.
        settings["mute_stderr"] = mute_check.get_active()
        save_settings(settings)
        dlg.destroy()

    def _on_open_external(self, *_a) -> None:
        Gio.AppInfo.launch_default_for_uri(HOME_URL, None)

    def _on_clear_data(self, *_a) -> None:
        if not self._window:
            return

        def do_clear():
            try:
                if _WEBKIT_API == "6.0":
                    session = self._window.webview.get_network_session()
                    dm = session.get_website_data_manager()
                else:
                    ctx = self._window.webview.get_context()
                    dm = ctx.get_website_data_manager()
                dm.clear(WebKit.WebsiteDataTypes.ALL, 0, None, None, None)
                self._window.webview.reload()
            except Exception as exc:
                sys.stderr.write(f"clear-data failed: {exc}\n")

        if _IS_GTK4:
            dlg = Gtk.AlertDialog()
            dlg.set_message("Clear cached data and cookies?")
            dlg.set_detail(
                "You will be signed out of OpenFront and any cached game "
                "assets will be re-downloaded on next launch."
            )
            dlg.set_buttons(["Cancel", "Clear"])
            dlg.set_default_button(0)
            dlg.set_cancel_button(0)

            def _on_response(src, result):
                try:
                    if src.choose_finish(result) == 1:
                        do_clear()
                except GLib.Error:
                    pass
            dlg.choose(self._window, None, _on_response)
        else:
            dialog = Gtk.MessageDialog(
                transient_for=self._window,
                modal=True,
                message_type=Gtk.MessageType.QUESTION,
                buttons=Gtk.ButtonsType.NONE,
                text="Clear cached data and cookies?",
            )
            dialog.format_secondary_text(
                "You will be signed out of OpenFront and cached assets "
                "will be re-downloaded on next launch."
            )
            dialog.add_button("Cancel", Gtk.ResponseType.CANCEL)
            dialog.add_button("Clear", Gtk.ResponseType.OK)
            dialog.set_default_response(Gtk.ResponseType.CANCEL)
            response = dialog.run()
            dialog.destroy()
            if response == Gtk.ResponseType.OK:
                do_clear()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="openfront-gtk",
        description="GTK desktop wrapper for OpenFront.io",
    )
    parser.add_argument(
        "--url",
        default=HOME_URL,
        help=f"Initial URL to load (default: {HOME_URL})",
    )
    parser.add_argument("--version", action="store_true")
    args, gtk_args = parser.parse_known_args(argv)

    if args.version:
        from openfront_gtk import __version__
        print(
            f"openfront-gtk {__version__} "
            f"(GTK {_GTK_API}, WebKit {_WEBKIT_API})"
        )
        return 0

    settings = load_settings()
    apply_mute(settings)

    app = OpenFrontApp(start_url=args.url)
    return app.run([sys.argv[0]] + gtk_args)


if __name__ == "__main__":
    sys.exit(main())
