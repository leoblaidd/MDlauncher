"""Modal do jogo: hero no topo, capa sobreposta, título, informações, Play, tela cheia e editar."""
from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from ..storage import Game
from . import theme
from .common import Card, Overlay, checker_brush, cover_crop, load_image, placeholder, rounded

HERO_H = 300
COVER_W, COVER_H = 196, 294


class HeroCard(Card):
    def __init__(self, parent):
        super().__init__(parent)
        self.hero = QPixmap()
        self.cover_img = None
        self._cache = None

    def set_images(self, hero_path: str, cover_path: str):
        img = load_image(hero_path)
        self.hero = QPixmap.fromImage(img) if not img.isNull() else QPixmap()
        c = load_image(cover_path)
        self.cover_img = c if not c.isNull() else None
        self._cache = None
        self.update()

    def resizeEvent(self, e):
        self._cache = None
        super().resizeEvent(e)

    def _hero_pix(self):
        if self._cache is not None:
            return self._cache
        w, h, dpr = self.width(), HERO_H, self.devicePixelRatioF()
        if not self.hero.isNull():
            pm = cover_crop(self.hero, w, h, dpr)
        elif self.cover_img is not None:
            # sem hero: usa a capa ampliada e desfocada (escala para baixo e para cima)
            small = cover_crop(QPixmap.fromImage(self.cover_img), max(1, w // 18), max(1, h // 18), 1.0)
            pm = small.scaled(int(w * dpr), int(h * dpr), Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
            pm.setDevicePixelRatio(dpr)
        else:
            pm = QPixmap(int(w * dpr), int(h * dpr))
            pm.setDevicePixelRatio(dpr)
            pp = QPainter(pm)
            pp.fillRect(0, 0, w, h, checker_brush(30))
            pp.end()
        self._cache = pm
        return pm

    def paintEvent(self, e):
        super().paintEvent(e)
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        clip = QPainterPath()
        clip.addRoundedRect(QRectF(self.rect()).adjusted(1, 1, -1, -1), self.radius, self.radius)
        p.setClipPath(clip)
        p.drawPixmap(0, 0, self._hero_pix())
        g = QLinearGradient(0, 0, 0, HERO_H)
        g.setColorAt(0.0, QColor(0, 0, 0, 40))
        g.setColorAt(0.55, QColor(20, 20, 24, 60))
        g.setColorAt(1.0, QColor(theme.CARD))
        p.fillRect(QRectF(0, 0, self.width(), HERO_H + 1), g)


class CoverLabel(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.pm = QPixmap()
        self.setFixedSize(COVER_W + 24, COVER_H + 24)

    def set_cover(self, path: str, name: str):
        dpr = self.devicePixelRatioF()
        img = load_image(path)
        pm = cover_crop(img, COVER_W, COVER_H, dpr) if not img.isNull() else placeholder(name, COVER_W, COVER_H, dpr)
        self.pm = rounded(pm, 12)
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(12, 8, COVER_W, COVER_H)
        for i, a in enumerate((70, 45, 25, 12)):
            sp = QPainterPath()
            sp.addRoundedRect(r.adjusted(-i * 2, -i + 4, i * 2, i * 2 + 6), 14 + i, 14 + i)
            p.fillPath(sp, QColor(0, 0, 0, a))
        p.drawPixmap(12, 8, self.pm)
        path = QPainterPath()
        path.addRoundedRect(r, 12, 12)
        p.setPen(QColor(255, 255, 255, 40))
        p.drawPath(path)


def _chip(icon_name: str, text: str) -> QWidget:
    w = QWidget()
    w.setObjectName("chip")
    w.setStyleSheet("#chip { background: rgba(255,255,255,0.07); border: 1px solid rgba(255,255,255,0.08); border-radius: 13px; }")
    lay = QHBoxLayout(w)
    lay.setContentsMargins(10, 4, 12, 4)
    lay.setSpacing(6)
    ic = QLabel()
    ic.setPixmap(theme.pixmap(icon_name, 14, "#c9c9d2"))
    t = QLabel(text)
    t.setStyleSheet("font-size: 12px; color: #dcdce2; background: transparent;")
    ic.setStyleSheet("background: transparent;")
    lay.addWidget(ic)
    lay.addWidget(t)
    return w


class GameModal(Overlay):
    play_requested = Signal(object, bool)
    edit_requested = Signal(object)
    fullscreen_changed = Signal(object, bool)

    def __init__(self, parent, game: Game, fullscreen: bool, running: bool = False):
        super().__init__(parent, card_size=(900, 590))
        self.game = game
        self.card.deleteLater()
        self.card = HeroCard(self)

        self.cover = CoverLabel(self.card)

        self.btn_close = QPushButton(self.card)
        self.btn_close.setIcon(theme.icon("close"))
        self.btn_close.setFixedSize(34, 34)
        self.btn_close.setCursor(Qt.PointingHandCursor)
        self.btn_close.setToolTip("Fechar (Esc)")
        self.btn_close.setStyleSheet("QPushButton { background: rgba(0,0,0,0.45); border: 1px solid rgba(255,255,255,0.15);"
                                     " border-radius: 17px; padding: 0; } QPushButton:hover { background: rgba(0,0,0,0.7); }")
        self.btn_close.clicked.connect(self.close_overlay)

        self.info = QWidget(self.card)
        self.info.setStyleSheet("background: transparent;")
        v = QVBoxLayout(self.info)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(10)
        self.title = QLabel()
        self.title.setObjectName("h1")
        self.title.setWordWrap(True)
        self.title.setStyleSheet("font-size: 30px; font-weight: 800; background: transparent;")
        v.addWidget(self.title)
        self.chips = QHBoxLayout()
        self.chips.setSpacing(8)
        v.addLayout(self.chips)
        self.playtime = QLabel()
        self.playtime.setStyleSheet("font-size: 14px; color: #d6d6dc; background: transparent;")
        v.addWidget(self.playtime)
        v.addStretch(1)

        btns = QHBoxLayout()
        btns.setSpacing(10)
        self.btn_play = QPushButton("  JOGAR")
        self.btn_play.setIcon(theme.icon("play", theme.DARK_TEXT))
        self.btn_play.setFixedSize(190, 50)
        self.btn_play.setCursor(Qt.PointingHandCursor)
        self.btn_play.setStyleSheet(
            f"QPushButton {{ background: {theme.SILVER_GRAD}; border: 1px solid #e4eaf1; color: {theme.DARK_TEXT};"
            " font-size: 16px; font-weight: 800; letter-spacing: 1px; border-radius: 10px; }"
            f" QPushButton:hover {{ background: {theme.SILVER_GRAD_HOVER}; }}"
            " QPushButton:disabled { background: #3a4049; border-color: #3a4049; color: #9aa3ad; }")
        self.btn_play.clicked.connect(lambda: self.play_requested.emit(self.game, self.btn_fs.isChecked()))
        self.btn_fs = QPushButton("  Tela cheia")
        self.btn_fs.setObjectName("toggle")
        self.btn_fs.setCheckable(True)
        self.btn_fs.setChecked(fullscreen)
        self.btn_fs.setIcon(theme.icon("fullscreen"))
        self.btn_fs.setFixedHeight(50)
        self.btn_fs.setCursor(Qt.PointingHandCursor)
        self.btn_fs.setToolTip("Iniciar o jogo em tela cheia (usa o argumento do seu emulador)")
        self.btn_fs.toggled.connect(lambda on: self.fullscreen_changed.emit(self.game, on))
        self.btn_edit = QPushButton()
        self.btn_edit.setIcon(theme.icon("edit"))
        self.btn_edit.setFixedSize(50, 50)
        self.btn_edit.setToolTip("Editar informações, capa, hero, ROM e emulador")
        self.btn_edit.setCursor(Qt.PointingHandCursor)
        self.btn_edit.clicked.connect(lambda: self.edit_requested.emit(self.game))
        btns.addWidget(self.btn_play)
        btns.addWidget(self.btn_fs)
        btns.addWidget(self.btn_edit)
        btns.addStretch(1)
        v.addLayout(btns)

        self.credits = QLabel(self.card)
        self.credits.setStyleSheet("font-size: 11px; color: #74747e; background: transparent;")

        self.refresh()
        self.set_running(running)

    def refresh(self):
        g = self.game
        self.card.set_images(g.hero_path, g.cover_path)
        self.cover.set_cover(g.cover_path, g.name)
        self.title.setText(g.name)
        while self.chips.count():
            it = self.chips.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
        if g.release_date:
            self.chips.addWidget(_chip("calendar", theme.fmt_date(g.release_date)))
        if g.multiplayer is True:
            self.chips.addWidget(_chip("users", f"Multiplayer{' · ' + g.players + ' jogadores' if g.players else ''}"))
        elif g.multiplayer is False:
            self.chips.addWidget(_chip("user", "Single player"))
        if g.developer:
            self.chips.addWidget(_chip("cart", g.developer))
        self.chips.addStretch(1)
        pt = theme.fmt_playtime(g.playtime)
        txt = f"<b>{pt}</b> {'jogadas' if g.playtime >= 60 else ''}"
        if g.last_played:
            txt += f"&nbsp;&nbsp;<span style='color:#8a8a94'>· última vez em {datetime.fromtimestamp(g.last_played):%d/%m/%Y}</span>"
        self.playtime.setTextFormat(Qt.RichText)
        self.playtime.setText(txt)
        cred = []
        if g.cover_source:
            cred.append(f"Capa: {g.cover_source}")
        if g.hero_source:
            cred.append(f"Hero: {g.hero_source}")
        self.credits.setText("   ·   ".join(cred))
        self.card.update()

    def set_running(self, running: bool):
        self.btn_play.setEnabled(not running)
        self.btn_play.setText("  JOGANDO…" if running else "  JOGAR")

    def _layout_card(self):
        super()._layout_card()
        w, h = self.card.width(), self.card.height()
        self.btn_close.move(w - 34 - 16, 16)
        cx = 34
        cy = HERO_H - 150
        self.cover.move(cx - 12, cy - 8)
        ix = cx + COVER_W + 34
        self.info.setGeometry(ix, HERO_H - 6, w - ix - 34, h - HERO_H + 6 - 30)
        self.credits.setGeometry(cx, cy + COVER_H + 14, COVER_W + 40, 18)
