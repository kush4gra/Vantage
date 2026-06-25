#!/usr/bin/env python3
"""SNI tray + dbusmenu implementation for Vantage (pure Gio — no GTK3/GTK4).

Two D-Bus interfaces on the session bus:
  org.kde.StatusNotifierItem  /StatusNotifierItem  — icon registration
  com.canonical.dbusmenu      /StatusNotifierMenu  — right-click menu tree

Left-click (Activate) and middle-click (SecondaryActivate) toggle the window.
Right-click causes the tray host to call GetLayout on the dbusmenu object and
render the menu itself — no GTK popup needed, so this works on Wayland.
"""
import logging
import os
from gettext import gettext as _

import gi
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import GLib, Gio, GdkPixbuf

from .client import (
    FAN_MODES, FAN_LABELS, CONSERVATION_LIMIT_PCT)

log = logging.getLogger("vantage.tray")

PROFILE_LABELS = {
    "power-saver": _("Power Saver"), "low-power": _("Low Power"),
    "balanced": _("Balanced"), "performance": _("Performance"),
}
KBD_LABELS = [_("Off"), _("Low"), _("High")]

# Pre-rendered light tray PNG (installed path first, dev fallback next). A PNG
# is used rather than the SVG because gdk-pixbuf's SVG loader (librsvg) is an
# optional dependency that may be absent, whereas PNG support is always present.
_ICON_CANDIDATES = [
    # Installed location (pkgdatadir), then the source tree for uninstalled runs.
    "/usr/share/vantage/icon-tray.png",
    os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "data", "icon-tray.png"),
]


def _load_icon_pixmaps():
    """Load the light tray icon as ARGB32 pixmaps for the SNI IconPixmap.

    Serving raw pixels over D-Bus sidesteps the host's icon-theme lookup and,
    crucially, GTK symbolic recolouring — which would otherwise force the
    `-symbolic` icon to the theme's near-black default and render invisibly on
    dark panels. SNI expects ARGB32 in network byte order (big-endian).
    """
    path = next((p for p in _ICON_CANDIDATES if os.path.exists(p)), None)
    if path is None:
        return []
    pixmaps = []
    for size in (22, 32, 48):
        try:
            pb = GdkPixbuf.Pixbuf.new_from_file_at_size(path, size, size)
        except Exception:
            log.exception("failed to load tray icon %s at %dpx", path, size)
            continue
        pb = pb.add_alpha(False, 0, 0, 0) if not pb.get_has_alpha() else pb
        w, h = pb.get_width(), pb.get_height()
        rowstride = pb.get_rowstride()
        n_ch = pb.get_n_channels()
        src = pb.get_pixels()
        argb = bytearray(w * h * 4)
        o = 0
        for y in range(h):
            row = y * rowstride
            for x in range(w):
                i = row + x * n_ch
                r, g, b = src[i], src[i + 1], src[i + 2]
                a = src[i + 3] if n_ch == 4 else 255
                argb[o], argb[o + 1], argb[o + 2], argb[o + 3] = a, r, g, b
                o += 4
        pixmaps.append((w, h, bytes(argb)))
    return pixmaps


# ---------------------------------------------------------------------------
# D-Bus interface XML
# ---------------------------------------------------------------------------

SNI_XML = """\
<node>
  <interface name="org.kde.StatusNotifierItem">
    <property name="Category"          type="s" access="read"/>
    <property name="Id"                type="s" access="read"/>
    <property name="Title"             type="s" access="read"/>
    <property name="Status"            type="s" access="read"/>
    <property name="IconName"          type="s"        access="read"/>
    <property name="IconPixmap"        type="a(iiay)"  access="read"/>
    <property name="OverlayIconName"   type="s"        access="read"/>
    <property name="AttentionIconName" type="s"        access="read"/>
    <property name="Menu"              type="o"        access="read"/>
    <property name="ItemIsMenu"        type="b"        access="read"/>
    <method name="Activate">
      <arg name="x" type="i" direction="in"/>
      <arg name="y" type="i" direction="in"/>
    </method>
    <method name="ContextMenu">
      <arg name="x" type="i" direction="in"/>
      <arg name="y" type="i" direction="in"/>
    </method>
    <method name="SecondaryActivate">
      <arg name="x" type="i" direction="in"/>
      <arg name="y" type="i" direction="in"/>
    </method>
    <method name="Scroll">
      <arg name="delta"       type="i" direction="in"/>
      <arg name="orientation" type="s" direction="in"/>
    </method>
    <signal name="NewTitle"/>
    <signal name="NewIcon"/>
    <signal name="NewAttentionIcon"/>
    <signal name="NewOverlayIcon"/>
    <signal name="NewStatus">
      <arg name="status" type="s"/>
    </signal>
  </interface>
</node>"""

MENU_XML = """\
<node>
  <interface name="com.canonical.dbusmenu">
    <property name="Version"       type="u"  access="read"/>
    <property name="TextDirection" type="s"  access="read"/>
    <property name="Status"        type="s"  access="read"/>
    <property name="IconThemePath" type="as" access="read"/>
    <method name="GetLayout">
      <arg name="parentId"       type="i"          direction="in"/>
      <arg name="recursionDepth" type="i"          direction="in"/>
      <arg name="propertyNames"  type="as"         direction="in"/>
      <arg name="revision"       type="u"          direction="out"/>
      <arg name="layout"         type="(ia{sv}av)" direction="out"/>
    </method>
    <method name="GetGroupProperties">
      <arg name="ids"           type="ai"        direction="in"/>
      <arg name="propertyNames" type="as"        direction="in"/>
      <arg name="properties"    type="a(ia{sv})" direction="out"/>
    </method>
    <method name="Event">
      <arg name="id"        type="i"  direction="in"/>
      <arg name="eventId"   type="s"  direction="in"/>
      <arg name="data"      type="v"  direction="in"/>
      <arg name="timestamp" type="u"  direction="in"/>
    </method>
    <method name="EventGroup">
      <arg name="events"   type="a(isvu)" direction="in"/>
      <arg name="idErrors" type="ai"      direction="out"/>
    </method>
    <method name="AboutToShow">
      <arg name="id"         type="i" direction="in"/>
      <arg name="needUpdate" type="b" direction="out"/>
    </method>
    <method name="AboutToShowGroup">
      <arg name="ids"           type="ai" direction="in"/>
      <arg name="updatesNeeded" type="ai" direction="out"/>
      <arg name="idErrors"      type="ai" direction="out"/>
    </method>
    <signal name="LayoutUpdated">
      <arg name="revision" type="u"/>
      <arg name="parent"   type="i"/>
    </signal>
    <signal name="ItemsPropertiesUpdated">
      <arg name="updatedProps" type="a(ia{sv})"/>
      <arg name="removedProps" type="a(ias)"/>
    </signal>
  </interface>
</node>"""


# ---------------------------------------------------------------------------
# dbusmenu object
# ---------------------------------------------------------------------------

class VantageMenu:
    """com.canonical.dbusmenu at /StatusNotifierMenu.

    The tray host (Waybar, KDE plasmashell, etc.) queries this object to
    render the right-click menu. Menu state is rebuilt after every write so
    checkmarks and radio bullets stay in sync.
    """

    MENU_PATH  = "/StatusNotifierMenu"
    MENU_IFACE = "com.canonical.dbusmenu"

    def __init__(self, backend, window_fn, quit_fn):
        self._backend       = backend
        self._window_fn     = window_fn
        self._quit_fn       = quit_fn
        self._revision      = 0
        self._next_id       = 1
        self._id_to_action  = {}
        self._flat_items    = {}
        self._root_children = []
        self._node_by_id    = {}
        self._conn          = None
        self._reg_id        = None
        self._node_info     = Gio.DBusNodeInfo.new_for_xml(MENU_XML)

    def register(self, conn):
        self._conn = conn
        iface = self._node_info.lookup_interface(self.MENU_IFACE)
        self._reg_id = conn.register_object(
            self.MENU_PATH, iface,
            self._on_method_call, self._on_get_property, None)

    def unregister(self):
        if self._conn and self._reg_id:
            self._conn.unregister_object(self._reg_id)
            self._reg_id = None

    def rebuild(self):
        """Rebuild menu from current hardware state and notify the tray host."""
        self._revision += 1
        self._next_id = 1
        self._id_to_action.clear()
        self._flat_items.clear()
        self._root_children = self._build_items()
        self._index_nodes()
        if self._conn and self._reg_id:
            self._conn.emit_signal(
                None, self.MENU_PATH, self.MENU_IFACE, "LayoutUpdated",
                GLib.Variant("(ui)", (self._revision, 0)))
        return False   # safe for GLib.idle_add

    # ---- ID allocator --------------------------------------------------------

    def _alloc(self, props, action=None):
        id_ = self._next_id
        self._next_id += 1
        if action:
            self._id_to_action[id_] = action
        self._flat_items[id_] = props
        return id_

    # ---- menu tree -----------------------------------------------------------

    def _build_items(self):
        st = self._backend.get_state()
        items = []

        def toggle(label, active, setter):
            props = {
                "label":        GLib.Variant("s", label),
                "toggle-type":  GLib.Variant("s", "checkmark"),
                "toggle-state": GLib.Variant("i", 1 if active else 0),
                "enabled":      GLib.Variant("b", True),
            }
            def action(fn=setter):
                fn()
                GLib.idle_add(self.rebuild)
            return self._alloc(props, action), props

        if "conservation_mode" in st:
            active = st["conservation_mode"] == "1"
            id_, props = toggle(
                _("Conservation (~%d%%)") % CONSERVATION_LIMIT_PCT, active,
                lambda a=active: self._backend.set_vpc("conservation_mode", "0" if a else "1"))
            items.append((id_, props, []))

        if "usb_charging" in st:
            active = st["usb_charging"] == "1"
            id_, props = toggle(
                _("Always-On USB"), active,
                lambda a=active: self._backend.set_vpc("usb_charging", "0" if a else "1"))
            items.append((id_, props, []))

        if "power_profile" in st:
            items.append(self._profile_submenu(st))

        if "fan_mode" in st:
            items.append(self._fan_submenu(st))

        if "fn_lock" in st:
            active = st["fn_lock"] == "0"
            id_, props = toggle(
                _("Fn Lock"), active,
                lambda a=active: self._backend.set_vpc("fn_lock", "1" if a else "0"))
            items.append((id_, props, []))

        if "touchpad_inhibited" in st:
            active = st["touchpad_inhibited"] != "1"
            id_, props = toggle(
                _("Touchpad"), active,
                lambda a=active: self._backend.set_touchpad_enabled(not a))
            items.append((id_, props, []))

        if "kbd_backlight" in st:
            items.append(self._kbd_submenu(st))

        if "mic_on" in st:
            active = st["mic_on"] == "1"
            id_, props = toggle(
                _("Microphone"), active,
                lambda a=active: self._backend.set_mic_on(not a))
            items.append((id_, props, []))

        if "wifi_on" in st:
            active = st["wifi_on"] == "1"
            id_, props = toggle(
                _("Wi-Fi"), active,
                lambda a=active: self._backend.set_wifi_on(not a))
            items.append((id_, props, []))

        sep_props = {"type": GLib.Variant("s", "separator")}
        items.append((self._alloc(sep_props), sep_props, []))

        win = self._window_fn()
        visible = win is not None and win.get_visible()
        lbl = _("Hide Vantage") if visible else _("Show Vantage")
        show_props = {"label": GLib.Variant("s", lbl), "enabled": GLib.Variant("b", True)}
        def show_action(v=visible):
            w = self._window_fn()
            if w:
                w.hide() if v else w.present()
        items.append((self._alloc(show_props, show_action), show_props, []))

        quit_props = {"label": GLib.Variant("s", _("Quit")), "enabled": GLib.Variant("b", True)}
        items.append((self._alloc(quit_props, self._quit_fn), quit_props, []))

        return items

    def _profile_submenu(self, st):
        profiles = [p for p in st["power_profile_choices"].split(",") if p]
        current  = st.get("power_profile")
        children = []
        for p in profiles:
            props = {
                "label":        GLib.Variant("s", PROFILE_LABELS.get(p, p.title())),
                "toggle-type":  GLib.Variant("s", "radio"),
                "toggle-state": GLib.Variant("i", 1 if p == current else 0),
                "enabled":      GLib.Variant("b", True),
            }
            def action(name=p):
                self._backend.set_power_profile(name)
                GLib.idle_add(self.rebuild)
            children.append((self._alloc(props, action), props, []))
        cur_label = PROFILE_LABELS.get(current, current or "?")
        parent_props = {
            "label":            GLib.Variant("s", _("Power Profile: %s") % cur_label),
            "children-display": GLib.Variant("s", "submenu"),
            "enabled":          GLib.Variant("b", True),
        }
        return (self._alloc(parent_props), parent_props, children)

    def _fan_submenu(self, st):
        mode    = st.get("fan_mode")
        current = FAN_LABELS.get(mode, mode or "?")
        children = []
        for val, label in FAN_MODES:
            props = {
                "label":        GLib.Variant("s", label),
                "toggle-type":  GLib.Variant("s", "radio"),
                "toggle-state": GLib.Variant("i", 1 if current == label else 0),
                "enabled":      GLib.Variant("b", True),
            }
            def action(v=val):
                self._backend.set_vpc("fan_mode", v)
                if v != "2":  # Dust Cleaning resets sysfs asynchronously — skip rebuild
                    GLib.idle_add(self.rebuild)
            children.append((self._alloc(props, action), props, []))
        parent_props = {
            "label":            GLib.Variant("s", _("Fan Mode: %s") % current),
            "children-display": GLib.Variant("s", "submenu"),
            "enabled":          GLib.Variant("b", True),
        }
        return (self._alloc(parent_props), parent_props, children)

    def _kbd_submenu(self, st):
        try:
            mx  = int(st.get("kbd_backlight_max", "2"))
            cur = int(st.get("kbd_backlight", "0"))
        except ValueError:
            mx, cur = 2, 0
        labels = KBD_LABELS[:mx + 1] if mx <= 2 \
            else [_("Off")] + [_("Level %d") % i for i in range(1, mx + 1)]
        children = []
        for i, label in enumerate(labels):
            props = {
                "label":        GLib.Variant("s", label),
                "toggle-type":  GLib.Variant("s", "radio"),
                "toggle-state": GLib.Variant("i", 1 if i == cur else 0),
                "enabled":      GLib.Variant("b", True),
            }
            def action(lvl=i):
                self._backend.set_kbd_backlight(lvl)
                GLib.idle_add(self.rebuild)
            children.append((self._alloc(props, action), props, []))
        cur_label = labels[cur] if cur < len(labels) else str(cur)
        parent_props = {
            "label":            GLib.Variant("s", _("Keyboard Backlight: %s") % cur_label),
            "children-display": GLib.Variant("s", "submenu"),
            "enabled":          GLib.Variant("b", True),
        }
        return (self._alloc(parent_props), parent_props, children)

    # ---- GLib.Variant serialisation ------------------------------------------

    def _item_to_tuple(self, id_, props, children, depth):
        # Plain Python tuple for embedding directly in a (ia{sv}av) struct
        # position. Each child in the av is a GLib.Variant("(ia{sv}av)", ...) —
        # the `av` array type already boxes each element as a variant, so do NOT
        # add an extra GLib.Variant("v", ...) wrapper (that double-nests and
        # makes libdbusmenu read a nested variant where it expects a property,
        # crashing waybar with a g_variant_get_int32 assertion). `depth` limits
        # recursion: 0 = no children, -1 = unlimited, n = n more levels.
        if depth == 0:
            child_av = []
        else:
            nd = depth - 1 if depth > 0 else -1
            child_av = [self._item_to_variant(*c, depth=nd) for c in children]
        return (id_, props, child_av)

    def _item_to_variant(self, id_, props, children, depth=-1):
        return GLib.Variant("(ia{sv}av)",
                            self._item_to_tuple(id_, props, children, depth))

    def _find_node(self, id_):
        """Return the (id, props, children) tuple for id_, or None.

        id 0 is the virtual root whose children are the top-level items.
        """
        if id_ == 0:
            return (0, {"children-display": GLib.Variant("s", "submenu")},
                    self._root_children)
        return self._node_by_id.get(id_)

    def _index_nodes(self):
        """Walk _root_children and map every id -> its (id, props, children)."""
        self._node_by_id = {}

        def walk(node):
            self._node_by_id[node[0]] = node
            for child in node[2]:
                walk(child)

        for n in self._root_children:
            walk(n)

    # ---- D-Bus handlers ------------------------------------------------------

    def _on_method_call(self, conn, sender, path, iface, method, params, invocation):
        log.debug("dbusmenu call: %s%s", method, params.print_(True))
        try:
            self._dispatch(method, params, invocation)
        except Exception as exc:
            log.exception("dbusmenu %s failed", method)
            invocation.return_dbus_error("org.freedesktop.DBus.Error.Failed", str(exc))

    def _dispatch(self, method, params, invocation):
        if method == "GetLayout":
            parent_id, depth, _prop_names = params.unpack()
            node = self._find_node(parent_id)
            if node is None:
                # Unknown id — return an empty item with the requested id so the
                # host doesn't index past the end (which segfaults libdbusmenu).
                root = (parent_id, {}, [])
            else:
                # Pass the inner struct as a plain Python tuple, not a pre-built
                # GLib.Variant — GI re-boxes struct positions and chokes on a
                # nested variant ("Expected GLib.Variant, but got str").
                root = self._item_to_tuple(node[0], node[1], node[2], depth)
            invocation.return_value(GLib.Variant("(u(ia{sv}av))", (self._revision, root)))

        elif method == "GetGroupProperties":
            ids, _prop_names = params.unpack()
            result = [(id_, self._flat_items.get(id_, {})) for id_ in ids]
            invocation.return_value(GLib.Variant("(a(ia{sv}))", (result,)))

        elif method == "Event":
            id_, event_id, _data, _ts = params.unpack()
            if event_id == "clicked":
                action = self._id_to_action.get(id_)
                if action:
                    action()
            invocation.return_value(GLib.Variant("()", ()))

        elif method == "EventGroup":
            events, = params.unpack()
            for id_, event_id, _data, _ts in events:
                if event_id == "clicked":
                    action = self._id_to_action.get(id_)
                    if action:
                        action()
            invocation.return_value(GLib.Variant("(ai)", ([],)))

        elif method in ("AboutToShow", ):
            invocation.return_value(GLib.Variant("(b)", (False,)))

        elif method == "AboutToShowGroup":
            invocation.return_value(GLib.Variant("(aiai)", ([], [])))

        else:
            invocation.return_dbus_error(
                "org.freedesktop.DBus.Error.UnknownMethod",
                "No method %s on %s" % (method, self.MENU_IFACE))

    def _on_get_property(self, conn, sender, path, iface, prop_name):
        return {
            "Version":       GLib.Variant("u", 3),
            "TextDirection": GLib.Variant("s", "ltr"),
            "Status":        GLib.Variant("s", "normal"),
            "IconThemePath": GLib.Variant("as", []),
        }.get(prop_name)


# ---------------------------------------------------------------------------
# StatusNotifierItem object
# ---------------------------------------------------------------------------

class VantageSNI:
    """org.kde.StatusNotifierItem at /StatusNotifierItem.

    All D-Bus callbacks fire on the GLib main loop thread (same as GTK4),
    so calling window.present() / window.hide() is unconditionally safe.
    """

    SNI_PATH      = "/StatusNotifierItem"
    SNI_IFACE     = "org.kde.StatusNotifierItem"
    WATCHER_BUS   = "org.kde.StatusNotifierWatcher"
    WATCHER_PATH  = "/StatusNotifierWatcher"
    WATCHER_IFACE = "org.kde.StatusNotifierWatcher"

    def __init__(self, backend, window_fn, quit_fn):
        self._backend    = backend
        self._window_fn  = window_fn
        self._quit_fn    = quit_fn
        self._menu       = VantageMenu(backend, window_fn, quit_fn)
        self._conn       = None
        self._owner_id   = 0
        self._sni_reg_id = None
        self._bus_name   = "org.kde.StatusNotifierItem-%d-1" % os.getpid()
        self._node_info  = Gio.DBusNodeInfo.new_for_xml(SNI_XML)
        self._icon_pixmap = GLib.Variant("a(iiay)", _load_icon_pixmaps())

    def start(self):
        self._owner_id = Gio.bus_own_name(
            Gio.BusType.SESSION,
            self._bus_name,
            Gio.BusNameOwnerFlags.NONE,
            self._on_bus_acquired,
            self._on_name_acquired,
            self._on_name_lost,
        )

    def stop(self):
        if self._sni_reg_id and self._conn:
            self._conn.unregister_object(self._sni_reg_id)
            self._sni_reg_id = None
        self._menu.unregister()
        if self._owner_id:
            Gio.bus_unown_name(self._owner_id)
            self._owner_id = 0
        self._conn = None

    def notify_window_visibility_changed(self):
        """Call after window show/hide to refresh the Show/Hide menu label."""
        GLib.idle_add(self._menu.rebuild)

    # ---- bus lifecycle -------------------------------------------------------

    def _on_bus_acquired(self, conn, name):
        self._conn = conn
        iface = self._node_info.lookup_interface(self.SNI_IFACE)
        self._sni_reg_id = conn.register_object(
            self.SNI_PATH, iface,
            self._on_method_call, self._on_get_property, None)
        self._menu.register(conn)
        self._menu.rebuild()

    def _on_name_acquired(self, conn, name):
        conn.call(
            self.WATCHER_BUS, self.WATCHER_PATH, self.WATCHER_IFACE,
            "RegisterStatusNotifierItem",
            GLib.Variant("(s)", (self._bus_name,)),
            None, Gio.DBusCallFlags.NONE, -1, None,
            lambda c, r: self._on_registered(c, r))

    def _on_name_lost(self, conn, name):
        pass   # no watcher or bus conflict — tray just won't appear

    def _on_registered(self, conn, result):
        try:
            conn.call_finish(result)
        except GLib.Error:
            pass   # StatusNotifierWatcher not running (e.g. bare GNOME)

    # ---- SNI method/property handlers ----------------------------------------

    def _on_method_call(self, conn, sender, path, iface, method, params, invocation):
        win = self._window_fn()
        if method in ("Activate", "SecondaryActivate"):
            if win:
                win.hide() if win.get_visible() else win.present()
            invocation.return_value(GLib.Variant("()", ()))
        elif method in ("ContextMenu", "Scroll"):
            invocation.return_value(GLib.Variant("()", ()))
        else:
            invocation.return_dbus_error(
                "org.freedesktop.DBus.Error.UnknownMethod",
                "No method %s on %s" % (method, self.SNI_IFACE))

    def _on_get_property(self, conn, sender, path, iface, prop_name):
        return {
            "Category":          GLib.Variant("s", "Hardware"),
            "Id":                GLib.Variant("s", "vantage"),
            "Title":             GLib.Variant("s", "Lenovo Vantage"),
            "Status":            GLib.Variant("s", "Active"),
            # IconName left empty on purpose: if set, hosts prefer it over
            # IconPixmap and apply GTK symbolic recolouring (forcing the icon
            # near-black on dark panels). Serving only the pixmap guarantees the
            # light icon renders identically everywhere.
            "IconName":          GLib.Variant("s", ""),
            "IconPixmap":        self._icon_pixmap,
            "OverlayIconName":   GLib.Variant("s", ""),
            "AttentionIconName": GLib.Variant("s", ""),
            "Menu":              GLib.Variant("o", VantageMenu.MENU_PATH),
            "ItemIsMenu":        GLib.Variant("b", False),
        }.get(prop_name)
