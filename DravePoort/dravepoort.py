#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DravePoort - startportaal voor de Dravenlock-apps.
Toont alle apps uit een map als grote, toegankelijke tegels EN in een
systeemvak-menu. Een klik start de app. Dravenlock-huisstijl, OS-taal.
"""
import os
import sys
import json

from PyQt6.QtCore import Qt, QUrl, QLocale, QSize, pyqtSignal, QFileInfo
from PyQt6.QtGui import (QPixmap, QIcon, QDesktopServices, QAction, QPainter,
                         QColor, QBrush, QPen, QFontMetrics)
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QLabel, QPushButton, QToolButton,
    QVBoxLayout, QHBoxLayout, QGridLayout, QScrollArea, QFrame, QLineEdit,
    QComboBox, QCheckBox, QDialog, QMessageBox, QFileDialog, QStatusBar,
    QSystemTrayIcon, QMenu, QSizePolicy, QPlainTextEdit)

APP_NAME = "DravePoort"
APP_VERSION = "0.1.3"
DONATE_URL = "https://paypal.me/roger076"
SUPPORT_MAIL = "service@dravenlock.nl"

# ---- Dravenlock-huisstijl ----
BG = "#0e0e11"
PANEL = "#16161b"
TILE = "#1a1a20"
SILVER = "#d4d4d4"
MUTE = "#8a8a94"
ACCENT = "#6fa3d6"


# ---------------------------------------------------------------------------
# Paden (frozen-bewust)
# ---------------------------------------------------------------------------
def _app_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def _resource(name):
    """Zoekt een meegeleverd bestand (logo) in _MEIPASS of naast de app."""
    for base in (getattr(sys, "_MEIPASS", None), _app_dir()):
        if base:
            p = os.path.join(base, name)
            if os.path.exists(p):
                return p
    return os.path.join(_app_dir(), name)


def _config_path():
    # eigen confignaam -> nooit het config.json van een andere app raken
    return os.path.join(_app_dir(), "dravepoort_config.json")


DEFAULT_CONFIG = {"lang": "", "folder": "", "manual": [], "hidden": [],
                  "tray_start": False}


def load_config():
    cfg = dict(DEFAULT_CONFIG)
    try:
        with open(_config_path(), "r", encoding="utf-8") as f:
            cfg.update(json.load(f))
    except Exception:
        pass
    return cfg


def save_config(cfg):
    try:
        with open(_config_path(), "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Taal (NL basis + OS-detectie + handmatige keuze)
# ---------------------------------------------------------------------------
_LANG = "nl"

TRANSLATIONS = {
    "en": {
        "Vernieuwen": "Refresh", "Map kiezen\u2026": "Choose folder\u2026",
        "Toevoegen\u2026": "Add\u2026", "Zoeken\u2026": "Search\u2026",
        "Instellingen\u2026": "Settings\u2026", "Snelgids": "Quick guide",
        "Over": "About", "Sluiten": "Close", "Afsluiten": "Quit",
        "Taal:": "Language:", "Automatisch (OS)": "Automatic (OS)",
        "Nederlands": "Dutch", "Engels": "English",
        "Map met apps:": "Apps folder:", "Kiezen\u2026": "Choose\u2026",
        "(map naast het portaal)": "(folder next to the portal)",
        "Starten in het systeemvak (venster verborgen)":
            "Start in the system tray (window hidden)",
        "Portaal openen": "Open portal",
        "Geen apps gevonden in deze map.": "No apps found in this folder.",
        "Kies de map waar je Drave-apps staan via 'Map kiezen'.":
            "Choose the folder with your Drave apps via 'Choose folder'.",
        "apps": "apps", "app": "app",
        "Kon de app niet starten": "Could not start the app",
        "App toevoegen": "Add app",
        "Programma's (*.exe *.lnk *.bat)": "Programs (*.exe *.lnk *.bat)",
        "Alle bestanden (*)": "All files (*)",
        "Verbergen": "Hide", "Uit de lijst halen": "Remove from list",
        "Snelkoppeling": "Shortcut", "Dravenlock-app": "Dravenlock app",
        "Donatie": "Donate",
        "draait nog in het systeemvak": "is still running in the system tray",
        "snelgids_titel": "DravePoort - quick guide",
        "Verborgen apps weer tonen": "Show hidden apps again",
    }
}

# Korte omschrijving per app (op kleine letters van de bestandsnaam)
APP_INFO = {
    "draveforms": ("PDF-formulieren invullen (dropdowns, tekst, vinkjes)",
                   "Fill PDF forms (dropdowns, text, checkboxes)"),
    "dravesheet": ("D&D personagebladen met auto-berekening + PDF-export",
                   "D&D character sheets with auto-calc + PDF export"),
    "dravedice": ("Dobbelsteen-roller voor D&D",
                  "Dice roller for D&D"),
    "dravetable": ("DM-scherm: initiatief- en HP-tracker",
                   "DM screen: initiative and HP tracker"),
    "dravecodex": ("Offline campagne-wiki",
                   "Offline campaign wiki"),
    "dravemaster": ("Browser voor de spelleider (dobbelen + AI-tools)",
                    "Browser for the game master (dice + AI tools)"),
    "draveread": ("Tekst voorlezen (tekst-naar-spraak)",
                  "Read text aloud (text-to-speech)"),
    "dravezoom": ("Schermvergrooter",
                  "Screen magnifier"),
    "dravecontrast": ("Kleurcontrast-checker (WCAG)",
                      "Colour contrast checker (WCAG)"),
    "dravesign": ("PDF's ondertekenen",
                  "Sign PDFs"),
    "dravepdf": ("PDF's samenvoegen, splitsen, draaien",
                 "Merge, split and rotate PDFs"),
    "draveshot": ("Schermafbeeldingen met notities",
                  "Screenshots with annotations"),
    "dravenote": ("Lokale notities (markdown)",
                  "Local notes (markdown)"),
    "dravetag": ("Mediabestanden taggen + hernoemen",
                 "Tag media files + bulk rename"),
    "draveedit": ("Website-bouwer (WYSIWYG)",
                  "Website builder (WYSIWYG)"),
    "dravemotion": ("Video-editor",
                    "Video editor"),
    "dravencrawl": ("Website doorzoeken",
                    "Search through a website"),
    "dravebrowser": ("Privacy-browser met spelletjes en widgets",
                     "Privacy browser with games and widgets"),
    "dravesetup": ("Van een .exe een installer/de-installer maken",
                   "Turn an .exe into an installer/uninstaller"),
    "dravesound": ("Muziek maken en bewerken",
                   "Make and edit music"),
    "dravestudio": ("Fotobewerking",
                    "Photo editing"),
    "pysetup_maker": ("Installer maken van een .py",
                      "Build an installer from a .py"),
    "syscare": ("Onderhoud en opschonen van je pc",
                "Maintain and clean your PC"),
    "deskbutler": ("E-mailprogramma",
                   "E-mail program"),
}


def detect_lang(cfg):
    forced = (cfg.get("lang") or "").strip().lower()
    if forced in ("nl", "en"):
        return forced
    try:
        if QLocale.system().name().lower().startswith("nl"):
            return "nl"
        return "en"
    except Exception:
        return "nl"


def t(s, lang=None):
    lg = lang or _LANG
    if lg == "nl":
        return s
    return TRANSLATIONS.get(lg, {}).get(s, s)


def describe(stem, kind, lang=None):
    info = APP_INFO.get(stem.lower())
    if info:
        return info[0] if (lang or _LANG) == "nl" else info[1]
    if kind == ".lnk":
        return t("Snelkoppeling", lang)
    return t("Dravenlock-app", lang)


# ---------------------------------------------------------------------------
# Logo
# ---------------------------------------------------------------------------
def logo_pixmap(size=64):
    p = _resource("logo.png")
    if os.path.exists(p):
        pm = QPixmap(p)
        if not pm.isNull():
            return pm.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatio,
                             Qt.TransformationMode.SmoothTransformation)
    # nood-logo (eenvoudig schild) als de png ontbreekt
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    pr = QPainter(pm)
    pr.setRenderHint(QPainter.RenderHint.Antialiasing)
    pr.setBrush(QBrush(QColor(ACCENT)))
    pr.setPen(Qt.PenStyle.NoPen)
    pr.drawRoundedRect(int(size * 0.18), int(size * 0.12),
                       int(size * 0.64), int(size * 0.76),
                       int(size * 0.12), int(size * 0.12))
    pr.end()
    return pm


def app_icon():
    return QIcon(logo_pixmap(64))


# ---------------------------------------------------------------------------
# App-map scannen
# ---------------------------------------------------------------------------
SKIP_DIRS = {".venv", "__pycache__", "build", "dist", "_internal",
             "system volume information", "$recycle.bin"}


def _self_stem():
    if getattr(sys, "frozen", False):
        return os.path.splitext(os.path.basename(sys.executable))[0].lower()
    return "dravepoort"


def scan_apps(folder, manual, hidden):
    """Geeft een lijst dicts: {name, path, desc, kind}.
    Kijkt zowel in de hoofdmap als in een submap 'apps' (als die bestaat)."""
    items = []
    seen = set()
    hidden_l = {h.lower() for h in (hidden or [])}
    self_stem = _self_stem()

    def add(name, path, kind, manual_item=False):
        key = os.path.normcase(os.path.abspath(path))
        if key in seen:
            return
        if name.lower() in hidden_l:
            return
        seen.add(key)
        items.append({"name": name, "path": path, "kind": kind,
                      "desc": describe(name, kind), "manual": manual_item})

    def scan_root(root):
        try:
            entries = sorted(os.listdir(root), key=str.lower)
        except Exception:
            return
        for nm in entries:
            full = os.path.join(root, nm)
            if os.path.isfile(full):
                stem, ext = os.path.splitext(nm)
                ext = ext.lower()
                if ext in (".exe", ".lnk"):
                    if ext == ".exe" and stem.lower() == self_stem:
                        continue
                    add(stem, full, ext)
            elif os.path.isdir(full) and nm.lower() not in SKIP_DIRS \
                    and nm.lower() != "apps" and not nm.startswith("."):
                runbat = os.path.join(full, "run.bat")
                if os.path.exists(runbat):
                    add(nm, runbat, ".bat")

    if folder and os.path.isdir(folder):
        scan_root(folder)
        # submap 'apps' (hoofdletterongevoelig)
        try:
            for sub in os.listdir(folder):
                if sub.lower() == "apps" and os.path.isdir(os.path.join(folder, sub)):
                    scan_root(os.path.join(folder, sub))
        except Exception:
            pass

    for p in (manual or []):
        if p and os.path.exists(p):
            stem = os.path.splitext(os.path.basename(p))[0]
            ext = os.path.splitext(p)[1].lower()
            add(stem, p, ext if ext else ".exe", manual_item=True)

    items.sort(key=lambda d: d["name"].lower())
    return items


def launch_path(path):
    try:
        if sys.platform.startswith("win"):
            os.startfile(path)  # werkt voor .exe, .lnk en .bat
        else:
            import subprocess
            subprocess.Popen([path], cwd=os.path.dirname(path) or None)
        return True, ""
    except Exception as e:
        return False, str(e)


# ---------------------------------------------------------------------------
# Tegel (toegankelijk, klikbaar met muis en toetsenbord)
# ---------------------------------------------------------------------------
class Tile(QFrame):
    clicked = pyqtSignal()
    secondary = pyqtSignal()  # rechtermuisknop / contextmenu

    def __init__(self, item, parent=None):
        super().__init__(parent)
        self.item = item
        self.setObjectName("tile")
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(232, 168)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(lambda _p: self.secondary.emit())
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 14, 14, 12)
        lay.setSpacing(6)
        ic = QLabel()
        ic.setPixmap(logo_pixmap(58))
        ic.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(ic)
        nm = QLabel(item["name"])
        nm.setObjectName("tilename")
        nm.setAlignment(Qt.AlignmentFlag.AlignCenter)
        nm.setWordWrap(True)
        lay.addWidget(nm)
        ds = QLabel(item["desc"])
        ds.setObjectName("tiledesc")
        ds.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ds.setWordWrap(True)
        lay.addWidget(ds)
        lay.addStretch(1)
        self.setAccessibleName(item["name"])
        self.setAccessibleDescription(item["desc"])
        self.setToolTip("%s\n%s" % (item["name"], item["path"]))

    def mouseReleaseEvent(self, ev):
        if ev.button() == Qt.MouseButton.LeftButton and self.rect().contains(ev.pos()):
            self.clicked.emit()
        super().mouseReleaseEvent(ev)

    def keyPressEvent(self, ev):
        if ev.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            self.clicked.emit()
        else:
            super().keyPressEvent(ev)


# ---------------------------------------------------------------------------
# Snelgids
# ---------------------------------------------------------------------------
GUIDE_NL = """DravePoort - Snelgids

DravePoort is je startportaal: het toont al je Dravenlock-apps als grote
tegels en in een menu bij de klok (systeemvak). Een klik start de app.

Aan de slag
- Zet DravePoort in dezelfde map als je Drave-apps (de .exe-bestanden),
  OF in een nette submap 'apps' daarbinnen. Beide worden gescand, dus de
  apps verschijnen vanzelf als tegels.
- Staat je map ergens anders? Klik op 'Map kiezen' en wijs de map aan.
- Klik op een tegel (of druk Enter als die geselecteerd is) om de app te
  starten. Met Tab loop je langs de tegels.
- 'Toevoegen' laat je een losse app aanwijzen die buiten de map staat.
- 'Vernieuwen' leest de map opnieuw in (bijv. na een nieuwe app).

Systeemvak
- Sluit je het venster, dan blijft DravePoort als pictogram bij de klok
  staan. Klik erop voor het venster, of rechtsklik voor het snelmenu met
  al je apps. Kies 'Afsluiten' om DravePoort echt te sluiten.

Verbergen
- Rechtsklik op een tegel om die te verbergen. Via Instellingen kun je
  verborgen apps weer terugzetten.

Vragen of een tip? service@dravenlock.nl
"""

GUIDE_EN = """DravePoort - Quick guide

DravePoort is your start portal: it shows all your Dravenlock apps as big
tiles and in a menu near the clock (system tray). One click starts an app.

Getting started
- Put DravePoort in the same folder as your Drave apps (the .exe files),
  OR in a tidy 'apps' subfolder inside it. Both are scanned, so the apps
  appear as tiles automatically.
- Folder elsewhere? Click 'Choose folder' and point to it.
- Click a tile (or press Enter when it is selected) to start the app. Use
  Tab to move between tiles.
- 'Add' lets you point to a single app outside the folder.
- 'Refresh' re-reads the folder (e.g. after adding a new app).

System tray
- Closing the window keeps DravePoort as an icon near the clock. Click it
  for the window, or right-click for the quick menu with all your apps.
  Choose 'Quit' to really close DravePoort.

Hiding
- Right-click a tile to hide it. You can restore hidden apps via Settings.

Questions or feedback? service@dravenlock.nl
"""


class GuideDialog(QDialog):
    def __init__(self, parent, lang):
        super().__init__(parent)
        self.setWindowTitle(t("snelgids_titel", lang))
        self.resize(560, 520)
        lay = QVBoxLayout(self)
        box = QPlainTextEdit()
        box.setReadOnly(True)
        box.setPlainText(GUIDE_NL if lang == "nl" else GUIDE_EN)
        box.setObjectName("guide")
        lay.addWidget(box)
        row = QHBoxLayout()
        row.addStretch(1)
        close = QPushButton(t("Sluiten", lang))
        close.clicked.connect(self.accept)
        row.addWidget(close)
        lay.addLayout(row)


# ---------------------------------------------------------------------------
# Instellingen
# ---------------------------------------------------------------------------
class SettingsDialog(QDialog):
    def __init__(self, parent, cfg, lang):
        super().__init__(parent)
        self.cfg = cfg
        self.setWindowTitle(t("Instellingen\u2026", lang))
        self.resize(500, 320)
        lay = QVBoxLayout(self)

        lay.addWidget(QLabel(t("Taal:", lang)))
        self.langbox = QComboBox()
        self.langbox.addItem(t("Automatisch (OS)", lang), "")
        self.langbox.addItem(t("Nederlands", lang), "nl")
        self.langbox.addItem(t("Engels", lang), "en")
        self.langbox.setCurrentIndex(
            {"": 0, "nl": 1, "en": 2}.get(cfg.get("lang", ""), 0))
        lay.addWidget(self.langbox)

        lay.addSpacing(6)
        lay.addWidget(QLabel(t("Map met apps:", lang)))
        frow = QHBoxLayout()
        self.folder_lbl = QLabel(cfg.get("folder")
                                 or t("(map naast het portaal)", lang))
        self.folder_lbl.setObjectName("hint")
        self.folder_lbl.setWordWrap(True)
        frow.addWidget(self.folder_lbl, 1)
        pick = QPushButton(t("Kiezen\u2026", lang))
        pick.clicked.connect(self._pick_folder)
        frow.addWidget(pick)
        lay.addLayout(frow)

        lay.addSpacing(6)
        self.tray = QCheckBox(t("Starten in het systeemvak (venster verborgen)",
                                lang))
        self.tray.setChecked(bool(cfg.get("tray_start")))
        lay.addWidget(self.tray)

        if cfg.get("hidden"):
            unhide = QPushButton("%s (%d)" % (t("Verborgen apps weer tonen", lang),
                                              len(cfg["hidden"])))
            unhide.clicked.connect(self._unhide)
            lay.addWidget(unhide)

        lay.addStretch(1)
        row = QHBoxLayout()
        row.addStretch(1)
        ok = QPushButton("OK")
        ok.clicked.connect(self.accept)
        row.addWidget(ok)
        lay.addLayout(row)

    def _pick_folder(self):
        path = QFileDialog.getExistingDirectory(
            self, t("Map kiezen\u2026", _LANG), self.cfg.get("folder") or "")
        if path:
            self.cfg["folder"] = path
            self.folder_lbl.setText(path)

    def _unhide(self):
        self.cfg["hidden"] = []
        QMessageBox.information(self, APP_NAME,
                                t("Verborgen apps weer tonen", _LANG) + " \u2713")

    def result_cfg(self):
        self.cfg["lang"] = self.langbox.currentData()
        self.cfg["tray_start"] = self.tray.isChecked()
        return self.cfg


# ---------------------------------------------------------------------------
# Hoofdvenster
# ---------------------------------------------------------------------------
class DravePoort(QMainWindow):
    def __init__(self, cfg):
        super().__init__()
        self.cfg = cfg
        self.lang = _LANG
        self.items = []
        self.tiles = []
        self._allow_quit = False
        self._tray_hinted = False

        self.setWindowTitle(APP_NAME)
        self.setWindowIcon(app_icon())
        self.resize(900, 660)

        central = QWidget()
        self.setCentralWidget(central)
        outer = QVBoxLayout(central)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(self._header())
        outer.addWidget(self._toolbar())

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setObjectName("scroll")
        self.host = QWidget()
        self.host.setObjectName("host")
        self.grid = QGridLayout(self.host)
        self.grid.setContentsMargins(18, 18, 18, 18)
        self.grid.setSpacing(16)
        self.grid.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.scroll.setWidget(self.host)
        outer.addWidget(self.scroll, 1)

        self.empty = QLabel("")
        self.empty.setObjectName("empty")
        self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty.setWordWrap(True)
        self.empty.setVisible(False)
        outer.addWidget(self.empty)

        sb = QStatusBar()
        self.setStatusBar(sb)
        self.count_lbl = QLabel("")
        self.count_lbl.setObjectName("muted")
        sb.addWidget(self.count_lbl)
        sb.addPermanentWidget(QLabel("v" + APP_VERSION))

        self._build_tray()
        self.refresh()

    # ---- UI-opbouw ----
    def _header(self):
        w = QWidget()
        w.setObjectName("header")
        w.setFixedHeight(58)
        lay = QHBoxLayout(w)
        lay.setContentsMargins(14, 8, 14, 8)
        logo = QLabel()
        logo.setPixmap(logo_pixmap(34))
        lay.addWidget(logo)
        title = QLabel(APP_NAME)
        title.setObjectName("title")
        lay.addWidget(title)
        ver = QLabel("v" + APP_VERSION)
        ver.setObjectName("ver")
        lay.addWidget(ver)
        lay.addStretch(1)
        for label, slot in [(t("Instellingen\u2026", self.lang), self._settings),
                            (t("Snelgids", self.lang), self._guide),
                            (t("Over", self.lang), self._about),
                            (t("Afsluiten", self.lang), self._quit)]:
            b = QPushButton(label)
            b.clicked.connect(lambda _=False, s=slot: s())
            lay.addWidget(b)
        return w

    def _toolbar(self):
        w = QWidget()
        w.setObjectName("toolbar")
        w.setFixedHeight(50)
        lay = QHBoxLayout(w)
        lay.setContentsMargins(14, 7, 14, 7)
        lay.setSpacing(8)
        b_ref = QPushButton("\u21bb  " + t("Vernieuwen", self.lang))
        b_ref.setObjectName("primary")
        b_ref.clicked.connect(self.refresh)
        lay.addWidget(b_ref)
        b_folder = QPushButton("\U0001f4c1  " + t("Map kiezen\u2026", self.lang))
        b_folder.clicked.connect(self._choose_folder)
        lay.addWidget(b_folder)
        b_add = QPushButton("\u2795  " + t("Toevoegen\u2026", self.lang))
        b_add.clicked.connect(self._add_app)
        lay.addWidget(b_add)
        lay.addStretch(1)
        self.search = QLineEdit()
        self.search.setPlaceholderText(t("Zoeken\u2026", self.lang))
        self.search.setObjectName("search")
        self.search.setClearButtonEnabled(True)
        self.search.setFixedWidth(240)
        self.search.textChanged.connect(self._reflow)
        lay.addWidget(self.search)
        return w

    # ---- systeemvak ----
    def _build_tray(self):
        self.tray = None
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return
        self.tray = QSystemTrayIcon(app_icon(), self)
        self.tray.setToolTip(APP_NAME)
        self.tray.activated.connect(self._tray_activated)
        self._rebuild_tray_menu()
        self.tray.show()

    def _rebuild_tray_menu(self):
        if not self.tray:
            return
        menu = QMenu()
        for it in self.items:
            act = QAction(app_icon(), it["name"], self)
            act.triggered.connect(lambda _=False, p=it["path"], n=it["name"]:
                                  self._launch(p, n))
            menu.addAction(act)
        if not self.items:
            empty = QAction(t("Geen apps gevonden in deze map.", self.lang), self)
            empty.setEnabled(False)
            menu.addAction(empty)
        menu.addSeparator()
        op = QAction(t("Portaal openen", self.lang), self)
        op.triggered.connect(self._show_window)
        menu.addAction(op)
        qa = QAction(t("Afsluiten", self.lang), self)
        qa.triggered.connect(self._quit)
        menu.addAction(qa)
        self.tray.setContextMenu(menu)

    def _tray_activated(self, reason):
        if reason in (QSystemTrayIcon.ActivationReason.Trigger,
                      QSystemTrayIcon.ActivationReason.DoubleClick):
            if self.isVisible() and not self.isMinimized():
                self.hide()
            else:
                self._show_window()

    def _show_window(self):
        self.showNormal()
        self.raise_()
        self.activateWindow()

    # ---- scannen + tegels ----
    def _scan_folder(self):
        return self.cfg.get("folder") or _app_dir()

    def refresh(self):
        self.items = scan_apps(self._scan_folder(),
                               self.cfg.get("manual", []),
                               self.cfg.get("hidden", []))
        # oude tegels weg
        for tl in self.tiles:
            tl.setParent(None)
            tl.deleteLater()
        self.tiles = []
        for it in self.items:
            tl = Tile(it)
            tl.clicked.connect(lambda p=it["path"], n=it["name"]: self._launch(p, n))
            tl.secondary.connect(lambda it=it: self._tile_menu(it))
            self.tiles.append(tl)
        self._reflow()
        self._rebuild_tray_menu()
        n = len(self.items)
        unit = t("app", self.lang) if n == 1 else t("apps", self.lang)
        self.count_lbl.setText("%d %s" % (n, unit))

    def _visible_tiles(self):
        q = (self.search.text() if hasattr(self, "search") else "").strip().lower()
        out = []
        for tl in self.tiles:
            ok = (not q) or q in tl.item["name"].lower() or q in tl.item["desc"].lower()
            tl.setVisible(ok)
            if ok:
                out.append(tl)
        return out

    def _reflow(self):
        vis = self._visible_tiles()
        # kolommen op basis van breedte
        avail = self.scroll.viewport().width() - 36
        tilew = 232 + 16
        cols = max(1, avail // tilew)
        # uit layout halen (zonder verwijderen)
        while self.grid.count():
            self.grid.takeAt(0)
        for i, tl in enumerate(vis):
            self.grid.addWidget(tl, i // cols, i % cols)
        self.empty.setVisible(not vis)
        if not vis:
            if self.items:
                self.empty.setText("")
            else:
                self.empty.setText("%s\n%s" % (
                    t("Geen apps gevonden in deze map.", self.lang),
                    t("Kies de map waar je Drave-apps staan via 'Map kiezen'.",
                      self.lang)))

    def resizeEvent(self, ev):
        super().resizeEvent(ev)
        self._reflow()

    # ---- acties ----
    def _launch(self, path, name):
        ok, err = launch_path(path)
        if ok:
            self.statusBar().showMessage("\u25b6 %s" % name, 2500)
        else:
            QMessageBox.warning(self, t("Kon de app niet starten", self.lang),
                                "%s\n\n%s" % (path, err))

    def _choose_folder(self):
        path = QFileDialog.getExistingDirectory(
            self, t("Map kiezen\u2026", self.lang), self._scan_folder())
        if path:
            self.cfg["folder"] = path
            save_config(self.cfg)
            self.refresh()

    def _add_app(self):
        path, _ = QFileDialog.getOpenFileName(
            self, t("App toevoegen", self.lang), self._scan_folder(),
            t("Programma's (*.exe *.lnk *.bat)", self.lang) + ";;"
            + t("Alle bestanden (*)", self.lang))
        if not path:
            return
        manual = list(self.cfg.get("manual", []))
        if path not in manual:
            manual.append(path)
            self.cfg["manual"] = manual
            save_config(self.cfg)
        self.refresh()

    def _tile_menu(self, item):
        menu = QMenu(self)
        if item.get("manual"):
            act = menu.addAction(t("Uit de lijst halen", self.lang))
        else:
            act = menu.addAction(t("Verbergen", self.lang))
        chosen = menu.exec(self.cursor().pos())
        if chosen == act:
            if item.get("manual"):
                manual = [p for p in self.cfg.get("manual", [])
                          if p != item["path"]]
                self.cfg["manual"] = manual
            else:
                hidden = list(self.cfg.get("hidden", []))
                if item["name"] not in hidden:
                    hidden.append(item["name"])
                self.cfg["hidden"] = hidden
            save_config(self.cfg)
            self.refresh()

    def _settings(self):
        dlg = SettingsDialog(self, dict(self.cfg), self.lang)
        if dlg.exec():
            self.cfg = dlg.result_cfg()
            save_config(self.cfg)
            self.refresh()

    def _guide(self):
        GuideDialog(self, self.lang).exec()

    def _about(self):
        QMessageBox.information(
            self, t("Over", self.lang),
            "%s v%s\n\n%s\nDravenlock\n%s\n%s"
            % (APP_NAME, APP_VERSION,
               "Startportaal voor je Dravenlock-apps."
               if self.lang == "nl" else "Start portal for your Dravenlock apps.",
               SUPPORT_MAIL, DONATE_URL))

    def _quit(self):
        self._allow_quit = True
        if self.tray:
            self.tray.hide()
        QApplication.quit()

    def closeEvent(self, ev):
        # venster sluiten -> naar het systeemvak, niet afsluiten
        if self._allow_quit or not self.tray:
            ev.accept()
            return
        ev.ignore()
        self.hide()
        if not self._tray_hinted:
            self._tray_hinted = True
            try:
                self.tray.showMessage(
                    APP_NAME,
                    "%s %s." % (APP_NAME, t("draait nog in het systeemvak",
                                            self.lang)),
                    app_icon(), 4000)
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Stijl
# ---------------------------------------------------------------------------
QSS = """
* { font-family: 'Segoe UI', sans-serif; font-size: 14px; color: %(silver)s; }
QMainWindow, QWidget { background: %(bg)s; }
#header { background: %(panel)s; border-bottom: 1px solid #23232b; }
#title { font-size: 20px; font-weight: 700; color: %(silver)s; }
#ver { color: %(mute)s; font-size: 12px; }
#toolbar { background: %(bg)s; border-bottom: 1px solid #23232b; }
QPushButton { background: %(panel)s; border: 1px solid #2c2c36; border-radius: 8px;
              padding: 7px 13px; color: %(silver)s; }
QPushButton:hover { border-color: %(accent)s; }
QPushButton:focus { border: 2px solid %(accent)s; }
QPushButton#primary { background: %(accent)s; color: #08131f; font-weight: 700;
                      border: none; }
QPushButton#primary:hover { background: #87b6e3; }
QToolButton#donate { border: none; background: transparent; color: %(accent)s; }
QLineEdit#search { background: %(tile)s; border: 1px solid #2c2c36;
                   border-radius: 8px; padding: 7px 10px; color: #ffffff;
                   font-size: 15px; }
QLineEdit#search:focus { border-color: %(accent)s; }
QScrollArea#scroll, #host { background: %(bg)s; border: none; }
#muted, #hint { color: %(mute)s; font-size: 12px; }
#empty { color: %(mute)s; font-size: 16px; padding: 30px; }
#tile { background: %(tile)s; border: 1px solid #2c2c36; border-radius: 12px; }
#tile:hover { border-color: %(accent)s; background: #20212a; }
#tile:focus { border: 2px solid %(accent)s; background: #20212a; }
#tilename { font-size: 17px; font-weight: 700; color: #ffffff; }
#tiledesc { font-size: 12px; color: %(mute)s; }
QPlainTextEdit#guide { background: %(panel)s; border: 1px solid #2c2c36;
                       border-radius: 8px; padding: 10px; font-size: 14px; }
QDialog { background: %(bg)s; }
QComboBox, QCheckBox { font-size: 14px; }
QComboBox { background: %(tile)s; border: 1px solid #2c2c36; border-radius: 8px;
            padding: 6px 8px; color: #ffffff; }
QMenu { background: %(panel)s; color: %(silver)s; border: 1px solid #2c2c36; }
QMenu::item { padding: 7px 22px; }
QMenu::item:selected { background: %(accent)s; color: #08131f; }
""" % {"bg": BG, "panel": PANEL, "tile": TILE, "silver": SILVER,
       "mute": MUTE, "accent": ACCENT}


def _install_excepthook():
    import traceback

    def hook(exctype, value, tb):
        msg = "".join(traceback.format_exception(exctype, value, tb))
        try:
            with open(os.path.join(_app_dir(), "dravepoort-fout.txt"),
                      "w", encoding="utf-8") as f:
                f.write(msg)
        except Exception:
            pass
        try:
            if QApplication.instance():
                QMessageBox.critical(None, "DravePoort - fout",
                                     "Er ging iets mis:\n\n" + msg[-1500:]
                                     + "\n\n(Ook opgeslagen in dravepoort-fout.txt)")
        except Exception:
            pass
        sys.__excepthook__(exctype, value, tb)

    sys.excepthook = hook


def main():
    global _LANG
    _install_excepthook()
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)  # blijft in het systeemvak
    try:
        cfg = load_config()
        _LANG = detect_lang(cfg)
        app.setStyleSheet(QSS)
        win = DravePoort(cfg)
        if cfg.get("tray_start") and win.tray:
            pass  # verborgen starten
        else:
            win.show()
    except Exception:
        sys.excepthook(*sys.exc_info())
        return
    try:  # Dravenlock: stille update-check (uit te zetten; Ctrl+Shift+U = met de hand)
        import drave_update
        drave_update.start(win, 'DravePoort', APP_VERSION)
    except Exception:
        pass
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
