# -*- coding: utf-8 -*-
# winkel.py - de Dravenlock-winkel in DravePoort: alle apps installeren en bijwerken.
# Copyright (C) 2026 Dravenlock (Roger & Claudio). Vrije software onder de GNU GPL v3.0.
"""Toont alle Dravenlock-apps (lijst van dravenlock.nl/apps.json) met per app een knop
Installeren / Bijwerken / Openen. Downloadt de zip van GitHub, pakt hem uit in een eigen
map en onthoudt welke versie er staat. Er gaat niets van de gebruiker mee."""
import ctypes
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import urllib.request
import zipfile

from PyQt6.QtCore import Qt, QObject, QThread, QTimer, pyqtSignal
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (QDialog, QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
                             QScrollArea, QFrame, QLineEdit, QComboBox, QCheckBox, QMessageBox,
                             QProgressBar, QFileDialog, QMenu, QSizePolicy)

CATALOGUS = "https://dravenlock.nl/apps.json"
AGENT = {"User-Agent": "DravePoort-winkel"}

BG, PANEL, TILE, SILVER, MUTE, ACCENT, GROEN = "#0e0e11", "#16161b", "#1a1a20", "#d4d4d4", "#8a8a94", "#6fa3d6", "#5ad988"


# ------------------------------------------------------------------ opslag
def _basis_data():
    b = os.environ.get("APPDATA") or os.path.join(os.path.expanduser("~"), ".config")
    p = os.path.join(b, "Dravenlock")
    os.makedirs(p, exist_ok=True)
    return p


def _staat_pad():
    return os.path.join(_basis_data(), "winkel.json")


def standaard_map():
    b = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    return os.path.join(b, "Programs", "Dravenlock")


def lees_staat():
    try:
        with open(_staat_pad(), encoding="utf-8-sig") as f:
            d = json.load(f)
    except Exception:
        d = {}
    d.setdefault("map", standaard_map())
    d.setdefault("apps", {})
    d.setdefault("snelkoppeling", True)
    return d


def bewaar_staat(d):
    try:
        with open(_staat_pad() + ".tmp", "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=1)
        os.replace(_staat_pad() + ".tmp", _staat_pad())
    except Exception:
        pass


def geinstalleerd():
    """[(naam, exe-pad)] van de apps die via de winkel zijn geïnstalleerd (voor de tegels)."""
    uit = []
    for repo, info in lees_staat()["apps"].items():
        exe = info.get("exe")
        if exe and os.path.exists(exe):
            uit.append((info.get("naam") or repo, exe))
    return uit


# ------------------------------------------------------------------ hulp
def _als_tuple(v):
    import re
    return tuple(int(x) for x in re.findall(r"\d+", str(v))[:4]) or (0,)


def nieuwer(a, b):
    x, y = _als_tuple(a), _als_tuple(b)
    n = max(len(x), len(y))
    return x + (0,) * (n - len(x)) > y + (0,) * (n - len(y))


def zoek_exe(map_, repo):
    beste = None
    for d, subs, files in os.walk(map_):
        subs[:] = [s for s in subs if s.lower() != "_internal"]
        for f in files:
            fl = f.lower()
            if fl.endswith(".exe") and not any(w in fl for w in ("unins", "ffmpeg", "ffprobe", "tor.exe", "setup")):
                p = os.path.join(d, f)
                score = (fl[:-4] == repo.lower(), os.path.getsize(p))
                if beste is None or score > beste[0]:
                    beste = (score, p)
    return beste[1] if beste else None


def draait(map_):
    """Is er een programma uit deze map open?"""
    try:
        out = subprocess.run(["powershell", "-NoProfile", "-Command",
                              "Get-Process | ? { $_.Path -and $_.Path.StartsWith('%s') } | %% Name" % map_.replace("'", "''")],
                             capture_output=True, text=True, timeout=15, creationflags=0x08000000).stdout
        return [r for r in out.split() if r.strip()]
    except Exception:
        return []


def snelkoppeling(naam, exe):
    try:
        ps = ("$s=(New-Object -ComObject WScript.Shell).CreateShortcut([Environment]::GetFolderPath('Desktop')+'\\%s.lnk');"
              "$s.TargetPath='%s';$s.WorkingDirectory='%s';$s.IconLocation='%s,0';$s.Save()"
              % (naam.replace("'", "''"), exe.replace("'", "''"), os.path.dirname(exe).replace("'", "''"),
                 exe.replace("'", "''")))
        subprocess.run(["powershell", "-NoProfile", "-Command", ps], timeout=20, creationflags=0x08000000)
    except Exception:
        pass


def naar_prullenbak(pad):
    """Map naar de Prullenbak (terug te halen), via SHFileOperationW."""
    class SHFILEOPSTRUCTW(ctypes.Structure):
        _fields_ = [("hwnd", ctypes.c_void_p), ("wFunc", ctypes.c_uint), ("pFrom", ctypes.c_wchar_p),
                    ("pTo", ctypes.c_wchar_p), ("fFlags", ctypes.c_ushort), ("fAnyOperationsAborted", ctypes.c_int),
                    ("hNameMappings", ctypes.c_void_p), ("lpszProgressTitle", ctypes.c_wchar_p)]
    op = SHFILEOPSTRUCTW(None, 3, pad + "\0\0", None, 0x0040 | 0x0010 | 0x0004 | 0x0400, 0, None, None)
    return ctypes.windll.shell32.SHFileOperationW(ctypes.byref(op)) == 0


# ------------------------------------------------------------------ werk op de achtergrond
class Installeerder(QObject):
    voortgang = pyqtSignal(str, int, str)      # repo, procent, tekst
    klaar = pyqtSignal(str, bool, str)          # repo, gelukt, melding

    def __init__(self, app, staat):
        super().__init__()
        self.app, self.staat = app, staat

    def run(self):
        a = self.app
        repo = a["repo"]
        doel = os.path.join(self.staat["map"], repo)
        tmp = tempfile.mkdtemp(prefix="drave_")
        try:
            zp = os.path.join(tmp, "app.zip")
            req = urllib.request.Request(a["zip"], headers=AGENT)
            with urllib.request.urlopen(req, timeout=30) as r, open(zp, "wb") as f:
                tot = int(r.headers.get("Content-Length") or 0)
                n = 0
                while True:
                    blok = r.read(1 << 18)
                    if not blok:
                        break
                    f.write(blok)
                    n += len(blok)
                    if tot:
                        self.voortgang.emit(repo, int(n * 90 / tot), "Downloaden... %d van %d MB" % (n >> 20, tot >> 20))
            self.voortgang.emit(repo, 92, "Uitpakken...")
            uit = os.path.join(tmp, "uit")
            with zipfile.ZipFile(zp) as z:
                z.extractall(uit)
            # één map in de zip? dan de inhoud daarvan nemen
            inhoud = os.listdir(uit)
            bron = os.path.join(uit, inhoud[0]) if len(inhoud) == 1 and os.path.isdir(os.path.join(uit, inhoud[0])) else uit
            os.makedirs(doel, exist_ok=True)
            for d, subs, files in os.walk(bron):
                rel = os.path.relpath(d, bron)
                os.makedirs(os.path.join(doel, rel), exist_ok=True)
                for fn in files:
                    shutil.copy2(os.path.join(d, fn), os.path.join(doel, rel, fn))
            exe = zoek_exe(doel, repo)
            if not exe:
                raise RuntimeError("Geen programma (.exe) gevonden in de download.")
            self.staat["apps"][repo] = dict(naam=a.get("naam", repo), versie=a.get("versie", ""), map=doel, exe=exe)
            bewaar_staat(self.staat)
            if self.staat.get("snelkoppeling"):
                snelkoppeling(a.get("naam", repo), exe)
            self.voortgang.emit(repo, 100, "Klaar")
            self.klaar.emit(repo, True, "%s %s staat klaar." % (a.get("naam", repo), a.get("versie", "")))
        except Exception as e:
            self.klaar.emit(repo, False, "Dat lukte niet: %s" % e)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class Ophaler(QObject):
    """Haalt de catalogus en (los) de plaatjes op."""
    catalogus = pyqtSignal(list, str)
    plaatje = pyqtSignal(str, bytes)

    def haal(self):
        try:
            req = urllib.request.Request(CATALOGUS, headers=AGENT)
            with urllib.request.urlopen(req, timeout=15) as r:
                d = json.loads(r.read().decode("utf-8"))
            self.catalogus.emit(d.get("apps", []), "")
        except Exception as e:
            self.catalogus.emit([], str(e))

    def plaatjes(self, lijst):
        cache = os.path.join(_basis_data(), "winkel-plaatjes")
        os.makedirs(cache, exist_ok=True)
        for repo, url in lijst:
            p = os.path.join(cache, repo + ".jpg")
            try:
                if not os.path.exists(p):
                    req = urllib.request.Request(url, headers=AGENT)
                    with urllib.request.urlopen(req, timeout=15) as r, open(p, "wb") as f:
                        f.write(r.read())
                with open(p, "rb") as f:
                    self.plaatje.emit(repo, f.read())
            except Exception:
                pass


# ------------------------------------------------------------------ één rij
class Rij(QFrame):
    def __init__(self, app, dlg):
        super().__init__()
        self.app, self.dlg = app, dlg
        self.setObjectName("rij")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(16)
        self.foto = QLabel()
        self.foto.setFixedSize(200, 125)
        self.foto.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.foto.setObjectName("foto")
        self.foto.setText(app["repo"][:2].upper() if not app["repo"].startswith("Drave") else app["repo"][5:7].upper())
        lay.addWidget(self.foto)
        mid = QVBoxLayout()
        mid.setSpacing(4)
        self.titel = QLabel()
        self.titel.setObjectName("titel")
        mid.addWidget(self.titel)
        b = QLabel(app.get("beschr", ""))
        b.setWordWrap(True)
        b.setObjectName("beschr")
        mid.addWidget(b)
        self.info = QLabel()
        self.info.setObjectName("info")
        mid.addWidget(self.info)
        self.balk = QProgressBar()
        self.balk.setFixedHeight(18)
        self.balk.hide()
        mid.addWidget(self.balk)
        mid.addStretch(1)
        lay.addLayout(mid, 1)
        knoppen = QVBoxLayout()
        self.knop = QPushButton()
        self.knop.setMinimumSize(170, 46)
        self.knop.clicked.connect(self._klik)
        knoppen.addWidget(self.knop)
        self.open = QPushButton("Openen")
        self.open.setMinimumSize(170, 40)
        self.open.clicked.connect(self._open)
        knoppen.addWidget(self.open)
        self.meer = QPushButton("Meer...")
        self.meer.setMinimumSize(170, 34)
        self.meer.clicked.connect(self._meer)
        knoppen.addWidget(self.meer)
        knoppen.addStretch(1)
        lay.addLayout(knoppen)
        self.ververs()

    def staat(self):
        return self.dlg.staat["apps"].get(self.app["repo"])

    def ververs(self):
        a, st = self.app, self.staat()
        self.titel.setText("%s   <span style='color:%s;font-size:15px'>%s</span>" % (a.get("naam", a["repo"]), MUTE, a.get("cat", "")))
        if st and os.path.exists(st.get("exe") or ""):
            oud = st.get("versie", "?")
            if nieuwer(a.get("versie", ""), oud):
                self.knop.setText("Bijwerken naar %s" % a.get("versie"))
                self.knop.setObjectName("bijwerken")
                self.info.setText("Geïnstalleerd: versie %s  ·  nieuw: %s  ·  %s MB" % (oud, a.get("versie"), a.get("mb", "?")))
            else:
                self.knop.setText("✓ Bijgewerkt")
                self.knop.setObjectName("klaar")
                self.info.setText("Geïnstalleerd: versie %s (nieuwste)" % oud)
            self.open.setEnabled(True)
        else:
            self.knop.setText("Installeren")
            self.knop.setObjectName("primair")
            self.info.setText("Versie %s  ·  %s MB" % (a.get("versie", "?"), a.get("mb", "?")))
            self.open.setEnabled(False)
        self.knop.setEnabled(self.knop.objectName() != "klaar")
        self.knop.style().unpolish(self.knop)
        self.knop.style().polish(self.knop)

    def _klik(self):
        self.dlg.installeer(self.app)

    def _open(self):
        st = self.staat()
        if st and os.path.exists(st.get("exe", "")):
            try:
                subprocess.Popen([st["exe"]], cwd=os.path.dirname(st["exe"]))
            except Exception as e:
                QMessageBox.warning(self, "DravePoort", "Kon de app niet starten:\n%s" % e)

    def _meer(self):
        m = QMenu(self)
        m.addAction("Uitleg en broncode op GitHub", lambda: self.dlg.open_url(self.app.get("github", "")))
        st = self.staat()
        if st:
            m.addAction("Map openen", lambda: os.startfile(st["map"]) if os.path.isdir(st.get("map", "")) else None)
            m.addAction("Snelkoppeling op bureaublad", lambda: snelkoppeling(self.app.get("naam", self.app["repo"]), st["exe"]))
            m.addSeparator()
            m.addAction("Verwijderen (naar de Prullenbak)", lambda: self.dlg.verwijder(self.app))
        m.exec(self.meer.mapToGlobal(self.meer.rect().bottomLeft()))


# ------------------------------------------------------------------ het venster
class WinkelDialoog(QDialog):
    def __init__(self, ouder=None):
        super().__init__(ouder)
        self.setWindowTitle("Dravenlock-winkel")
        self.resize(1100, 820)
        self.staat = lees_staat()
        self.apps, self.rijen, self.bezig = [], {}, {}
        self.setStyleSheet("""
            QDialog { background:%(BG)s; color:%(SILVER)s; font-size:17px; }
            QLabel { color:%(SILVER)s; }
            #kop { font-size:30px; font-weight:700; color:white; }
            #rij { background:%(TILE)s; border:1px solid #2a2a32; border-radius:12px; }
            #foto { background:#0a0a0c; border:1px solid #2a2a32; border-radius:8px; color:%(MUTE)s; font-size:34px; font-weight:700; }
            #titel { font-size:22px; font-weight:700; color:white; }
            #beschr { color:%(SILVER)s; font-size:17px; }
            #info { color:%(MUTE)s; font-size:15px; }
            QPushButton { background:#24242c; color:%(SILVER)s; border:1px solid #3a3a44; border-radius:8px; padding:6px 14px; font-size:16px; }
            QPushButton:hover { border-color:%(ACCENT)s; }
            QPushButton:disabled { color:#555; }
            QPushButton#primair { background:%(ACCENT)s; color:#0e0e11; font-weight:700; border:0; }
            QPushButton#bijwerken { background:#ffb347; color:#0e0e11; font-weight:700; border:0; }
            QPushButton#klaar { background:transparent; color:%(GROEN)s; border:1px solid #2f5a3c; }
            QLineEdit, QComboBox { background:#0a0a0c; color:white; border:1px solid #3a3a44; border-radius:8px; padding:6px 10px; font-size:17px; }
            QScrollArea { border:0; background:%(BG)s; }
            QWidget#binnen { background:%(BG)s; }
            QProgressBar { background:#0a0a0c; border:1px solid #3a3a44; border-radius:6px; color:white; text-align:center; font-size:12px; }
            QProgressBar::chunk { background:%(ACCENT)s; border-radius:5px; }
            QCheckBox { color:%(SILVER)s; }
        """ % dict(BG=BG, SILVER=SILVER, TILE=TILE, MUTE=MUTE, ACCENT=ACCENT, GROEN=GROEN))
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 16, 20, 16)
        kop = QLabel("🛒  Dravenlock-winkel")
        kop.setObjectName("kop")
        lay.addWidget(kop)
        sub = QLabel("Alle apps gratis en open source. Eén klik om te installeren of bij te werken.")
        sub.setStyleSheet("color:%s" % MUTE)
        lay.addWidget(sub)
        bar = QHBoxLayout()
        self.zoek = QLineEdit()
        self.zoek.setPlaceholderText("Zoeken...")
        self.zoek.setClearButtonEnabled(True)
        self.zoek.textChanged.connect(self.filter)
        bar.addWidget(self.zoek, 2)
        self.cat = QComboBox()
        self.cat.addItem("Alle categorieën")
        self.cat.currentIndexChanged.connect(self.filter)
        bar.addWidget(self.cat, 1)
        self.alleen = QCheckBox("Alleen mijn apps")
        self.alleen.toggled.connect(self.filter)
        bar.addWidget(self.alleen)
        self.alles = QPushButton("⟳  Alles bijwerken")
        self.alles.setObjectName("bijwerken")
        self.alles.clicked.connect(self.alles_bijwerken)
        bar.addWidget(self.alles)
        lay.addLayout(bar)
        self.status = QLabel("Lijst ophalen...")
        self.status.setStyleSheet("color:%s" % MUTE)
        lay.addWidget(self.status)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.binnen = QWidget()
        self.binnen.setObjectName("binnen")
        self.lijst = QVBoxLayout(self.binnen)
        self.lijst.setSpacing(10)
        self.lijst.addStretch(1)
        self.scroll.setWidget(self.binnen)
        lay.addWidget(self.scroll, 1)
        voet = QHBoxLayout()
        self.map_lbl = QLabel()
        self.map_lbl.setStyleSheet("color:%s;font-size:14px" % MUTE)
        voet.addWidget(self.map_lbl, 1)
        self.sk = QCheckBox("Snelkoppeling op bureaublad")
        self.sk.setChecked(bool(self.staat.get("snelkoppeling", True)))
        self.sk.toggled.connect(self._sk)
        voet.addWidget(self.sk)
        b = QPushButton("Map kiezen...")
        b.clicked.connect(self.kies_map)
        voet.addWidget(b)
        dicht = QPushButton("Sluiten")
        dicht.clicked.connect(self.accept)
        voet.addWidget(dicht)
        lay.addLayout(voet)
        self._toon_map()
        # catalogus ophalen
        self.ophaler = Ophaler()
        self.ophaler.catalogus.connect(self.kreeg_catalogus)
        self.ophaler.plaatje.connect(self.kreeg_plaatje)
        threading.Thread(target=self.ophaler.haal, daemon=True).start()

    # ---- basis
    def open_url(self, url):
        if url:
            import webbrowser
            webbrowser.open(url)

    def _sk(self, aan):
        self.staat["snelkoppeling"] = bool(aan)
        bewaar_staat(self.staat)

    def _toon_map(self):
        self.map_lbl.setText("Apps komen in: %s" % self.staat["map"])

    def kies_map(self):
        m = QFileDialog.getExistingDirectory(self, "Waar moeten de apps komen?", self.staat["map"])
        if m:
            self.staat["map"] = m
            bewaar_staat(self.staat)
            self._toon_map()

    # ---- catalogus
    def kreeg_catalogus(self, apps, fout):
        if fout or not apps:
            self.status.setText("Kon de lijst niet ophalen. Is er internet? (%s)" % (fout or "leeg"))
            return
        self.apps = sorted(apps, key=lambda a: (a.get("cat", ""), a.get("naam", a["repo"]).lower()))
        cats = []
        for a in self.apps:
            if a.get("cat") and a["cat"] not in cats:
                cats.append(a["cat"])
        for c in cats:
            self.cat.addItem(c)
        for a in self.apps:
            r = Rij(a, self)
            self.rijen[a["repo"]] = r
            self.lijst.insertWidget(self.lijst.count() - 1, r)
        self.filter()
        plaatjes = [(a["repo"], a["img"]) for a in self.apps if a.get("img")]
        threading.Thread(target=self.ophaler.plaatjes, args=(plaatjes,), daemon=True).start()

    def kreeg_plaatje(self, repo, data):
        r = self.rijen.get(repo)
        if r:
            pm = QPixmap()
            if pm.loadFromData(data):
                r.foto.setPixmap(pm.scaled(r.foto.size(), Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                                           Qt.TransformationMode.SmoothTransformation).copy(0, 0, 200, 125))

    def filter(self):
        z = self.zoek.text().strip().lower()
        c = self.cat.currentText() if self.cat.currentIndex() > 0 else ""
        n = upd = 0
        for a in self.apps:
            r = self.rijen[a["repo"]]
            st = self.staat["apps"].get(a["repo"])
            zicht = ((not z or z in (a.get("naam", "") + " " + a.get("beschr", "")).lower())
                     and (not c or a.get("cat") == c) and (not self.alleen.isChecked() or st))
            r.setVisible(bool(zicht))
            n += bool(zicht)
            if st and nieuwer(a.get("versie", ""), st.get("versie", "")):
                upd += 1
        self.binnen.adjustSize()
        self.scroll.verticalScrollBar().setValue(0)
        self.alles.setEnabled(upd > 0)
        self.alles.setText("⟳  Alles bijwerken (%d)" % upd if upd else "Alles is bijgewerkt")
        self.status.setText("%d apps" % n + (" · %d update%s beschikbaar" % (upd, "s" if upd != 1 else "") if upd else ""))

    # ---- installeren
    def installeer(self, app):
        repo = app["repo"]
        if repo in self.bezig:
            return
        st = self.staat["apps"].get(repo)
        if st and os.path.isdir(st.get("map", "")):
            open_ = draait(st["map"])
            if open_:
                QMessageBox.information(self, "Even sluiten", "%s is nog open.\nSluit de app eerst, en klik dan opnieuw." % app.get("naam", repo))
                return
        r = self.rijen[repo]
        r.knop.setEnabled(False)
        r.balk.setValue(0)
        r.balk.show()
        w = Installeerder(app, self.staat)
        t = QThread(self)
        w.moveToThread(t)
        t.started.connect(w.run)
        w.voortgang.connect(self._voortgang)
        w.klaar.connect(self._klaar)
        w.klaar.connect(t.quit)
        self.bezig[repo] = (w, t)
        t.start()

    def _voortgang(self, repo, pct, tekst):
        r = self.rijen.get(repo)
        if r:
            r.balk.setValue(pct)
            r.balk.setFormat(tekst)

    def _klaar(self, repo, ok, melding):
        self.bezig.pop(repo, None)
        r = self.rijen.get(repo)
        if r:
            r.balk.hide()
            r.ververs()
        self.filter()
        self.status.setText(melding)
        if not ok:
            QMessageBox.warning(self, "Dravenlock-winkel", melding)
        if hasattr(self.parent(), "refresh"):
            try:
                self.parent().refresh()
            except Exception:
                pass

    def alles_bijwerken(self):
        for a in self.apps:
            st = self.staat["apps"].get(a["repo"])
            if st and nieuwer(a.get("versie", ""), st.get("versie", "")):
                self.installeer(a)

    def verwijder(self, app):
        repo = app["repo"]
        st = self.staat["apps"].get(repo)
        if not st:
            return
        if draait(st["map"]):
            QMessageBox.information(self, "Even sluiten", "Sluit %s eerst." % app.get("naam", repo))
            return
        if QMessageBox.question(self, "Verwijderen", "%s verwijderen?\n\nDe map gaat naar de Prullenbak, dus je kunt hem terughalen."
                                % app.get("naam", repo)) != QMessageBox.StandardButton.Yes:
            return
        if os.path.isdir(st["map"]) and not naar_prullenbak(st["map"]):
            QMessageBox.warning(self, "Verwijderen", "Dat lukte niet. Is de app nog open?")
            return
        self.staat["apps"].pop(repo, None)
        bewaar_staat(self.staat)
        self.rijen[repo].ververs()
        self.filter()
        if hasattr(self.parent(), "refresh"):
            self.parent().refresh()
