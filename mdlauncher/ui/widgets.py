"""Grid de capas (rolagem suave), dock de vidro com busca, logo e botões da janela."""
from __future__ import annotations

import unicodedata

from PySide6.QtCore import (QEasingCurve, QPoint, QPropertyAnimation, QRect, QRectF, Qt, Signal,
                            Property)
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QLineEdit, QScrollArea, QSlider,
                               QToolButton, QWidget)

from ..storage import Game
from . import theme
from .common import cover_crop, load_image, placeholder, rounded

COVER_RATIO = 1.5  # 2:3, padrão das grids do SteamGridDB
TEXT_H = 44
SIDE_PAD = 26


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "")
    return "".join(c for c in s if not unicodedata.combining(c)).lower()


# --------------------------------------------------------------------------- canvas do grid
class GridCanvas(QWidget):
    clicked = Signal(object)
    context = Signal(object, QPoint)
    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.all_games: list[Game] = []
        self.games: list[Game] = []
        self.query = ""
        self.cover_w = 180
        self.top_pad = 84
        self.bottom_pad = 130
        self.view_h = 0
        self.hover = -1
        self.empty_text = ""
        self._cache: dict = {}
        self.cols, self.cell_w, self.cell_h = 1, 200.0, 300

    # ---- dados
    def set_games(self, games):
        self.all_games = list(games)
        self._apply_filter()

    def set_query(self, q: str):
        self.query = q
        self._apply_filter()

    def _apply_filter(self):
        terms = norm(self.query).split()
        self.games = ([g for g in self.all_games if all(t in norm(g.name) for t in terms)]
                      if terms else list(self.all_games))
        self.hover = -1
        self.relayout()

    def invalidate(self, game: Game | None = None):
        if game is None:
            self._cache.clear()
        else:
            for k in [k for k in self._cache if k[0] == game.id]:
                self._cache.pop(k, None)
        self.update()
        self.changed.emit()

    # ---- geometria
    def cover_h(self) -> int:
        return int(self.cover_w * COVER_RATIO)

    def relayout(self):
        avail = max(1, self.width() - 2 * SIDE_PAD)
        self.cols = max(1, avail // (self.cover_w + 26))
        self.cell_w = avail / self.cols
        self.cell_h = self.cover_h() + TEXT_H + 26
        rows = (len(self.games) + self.cols - 1) // self.cols
        h = self.top_pad + rows * self.cell_h + self.bottom_pad
        self.setFixedHeight(int(max(h, self.view_h)))
        self.update()
        self.changed.emit()

    def cell_rect(self, i: int) -> QRectF:
        r, c = divmod(i, self.cols)
        return QRectF(SIDE_PAD + c * self.cell_w, self.top_pad + r * self.cell_h, self.cell_w, self.cell_h)

    def cover_rect(self, i: int) -> QRectF:
        cr = self.cell_rect(i)
        x = cr.x() + (cr.width() - self.cover_w) / 2
        return QRectF(round(x), cr.y() + 10, self.cover_w, self.cover_h())

    def index_at(self, pos) -> int:
        x, y = pos.x() - SIDE_PAD, pos.y() - self.top_pad
        if x < 0 or y < 0:
            return -1
        c, r = int(x // self.cell_w), int(y // self.cell_h)
        if c >= self.cols:
            return -1
        i = r * self.cols + c
        if i >= len(self.games):
            return -1
        return i if self.cover_rect(i).adjusted(-4, -6, 4, TEXT_H).contains(pos) else -1

    # ---- desenho
    def _pix(self, g: Game):
        dpr = self.devicePixelRatioF()
        key = (g.id, g.cover_path, self.cover_w, dpr)
        pm = self._cache.get(key)
        if pm is None:
            w, h = self.cover_w, self.cover_h()
            img = load_image(g.cover_path)
            pm = cover_crop(img, w, h, dpr) if not img.isNull() else placeholder(g.name, w, h, dpr)
            pm = rounded(pm, 10)
            self._cache[key] = pm
        return pm

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        if not self.games:
            if self.empty_text or self.query:
                p.setPen(QColor(theme.MUTED))
                f = p.font()
                f.setPixelSize(15)
                p.setFont(f)
                txt = f"Nenhum jogo encontrado para “{self.query}”." if self.query else self.empty_text
                p.drawText(QRect(0, 0, self.width(), max(self.view_h, 200)), Qt.AlignCenter, txt)
            return
        clip = e.rect()
        first_row = max(0, int((clip.top() - self.top_pad - 20) // self.cell_h))
        last_row = int((clip.bottom() - self.top_pad) // self.cell_h) + 1
        f = QFont(p.font())
        for r in range(first_row, last_row + 1):
            for c in range(self.cols):
                i = r * self.cols + c
                if i >= len(self.games):
                    break
                self._paint_item(p, i, f)

    def _paint_item(self, p: QPainter, i: int, f: QFont):
        g = self.games[i]
        hover = i == self.hover
        cover = self.cover_rect(i)
        if hover:
            cover.translate(0, -5)
        for k, a in enumerate((44, 28, 14)):
            sp = QPainterPath()
            sp.addRoundedRect(cover.adjusted(-k - 1, -k + 3, k + 1, k + 7), 12 + k, 12 + k)
            p.fillPath(sp, QColor(0, 0, 0, a + (22 if hover else 0)))
        p.drawPixmap(cover.topLeft().toPoint(), self._pix(g))
        path = QPainterPath()
        path.addRoundedRect(cover, 10, 10)
        p.setPen(QPen(QColor(theme.ACCENT_HOVER), 2.4) if hover else QPen(QColor(255, 255, 255, 26), 1))
        p.drawPath(path)

        cr = self.cell_rect(i)
        f.setPixelSize(13)
        f.setWeight(QFont.DemiBold)
        p.setFont(f)
        p.setPen(QColor(248, 249, 251) if hover else QColor(222, 225, 230))
        tr = QRect(int(cr.x() + 6), int(cover.bottom() + 9), int(cr.width() - 12), 18)
        p.drawText(tr, Qt.AlignHCenter | Qt.AlignVCenter, p.fontMetrics().elidedText(g.name, Qt.ElideRight, tr.width()))
        sub = " · ".join(s for s in (g.year, "Multiplayer" if g.multiplayer else "") if s)
        if sub:
            f.setPixelSize(11)
            f.setWeight(QFont.Normal)
            p.setFont(f)
            p.setPen(QColor(theme.MUTED))
            p.drawText(QRect(tr.x(), tr.bottom() + 2, tr.width(), 16), Qt.AlignHCenter | Qt.AlignVCenter, sub)

    # ---- mouse
    def _set_hover(self, i: int):
        if i != self.hover:
            old, self.hover = self.hover, i
            for j in (old, i):
                if 0 <= j < len(self.games):
                    self.update(self.cell_rect(j).adjusted(-20, -20, 20, 20).toRect())
            self.setCursor(Qt.PointingHandCursor if i >= 0 else Qt.ArrowCursor)
            self.changed.emit()

    def mouseMoveEvent(self, e):
        self._set_hover(self.index_at(e.position().toPoint()))

    def leaveEvent(self, e):
        self._set_hover(-1)

    def mouseReleaseEvent(self, e):
        i = self.index_at(e.position().toPoint())
        if i < 0:
            return
        if e.button() == Qt.LeftButton:
            self.clicked.emit(self.games[i])
        elif e.button() == Qt.RightButton:
            self.context.emit(self.games[i], self.mapToGlobal(e.position().toPoint()))


class GameGrid(QScrollArea):
    """Área de rolagem transparente que vai até as bordas da janela, com rolagem suave."""
    game_clicked = Signal(object)
    game_context = Signal(object, QPoint)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.canvas = GridCanvas()
        self.setWidget(self.canvas)
        self.setWidgetResizable(False)
        self.setFrameShape(QFrame.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setStyleSheet(
            "QScrollArea { background: transparent; border: none; }"
            "QScrollBar:vertical { background: transparent; width: 8px; margin: 70px 3px 110px 0; }"
            "QScrollBar::handle:vertical { background: rgba(201,210,221,0.22); border-radius: 2px; min-height: 40px; }"
            "QScrollBar::handle:vertical:hover { background: rgba(201,210,221,0.45); }"
            "QScrollBar::add-line, QScrollBar::sub-line, QScrollBar::add-page, QScrollBar::sub-page"
            " { background: none; height: 0; }")
        self.viewport().setAutoFillBackground(False)
        self.canvas.setAutoFillBackground(False)
        self.canvas.clicked.connect(self.game_clicked)
        self.canvas.context.connect(self.game_context)
        sb = self.verticalScrollBar()
        self._target = 0
        self._anim = QPropertyAnimation(sb, b"value", self)
        self._anim.setDuration(420)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)

    @property
    def empty_text(self):
        return self.canvas.empty_text

    @empty_text.setter
    def empty_text(self, v):
        self.canvas.empty_text = v
        self.canvas.update()

    def set_games(self, games):
        self.canvas.set_games(games)

    def set_filter(self, q: str):
        self.canvas.set_query(q)
        self._anim.stop()
        self.verticalScrollBar().setValue(0)

    def refresh_game(self, gid: str = ""):
        self.canvas.update()
        self.canvas.changed.emit()

    def invalidate(self, game=None):
        self.canvas.invalidate(game)

    def set_cover_width(self, w: int):
        sb = self.verticalScrollBar()
        frac = sb.value() / sb.maximum() if sb.maximum() else 0
        self.canvas.cover_w = w
        self.canvas._cache.clear()
        self.canvas.relayout()
        sb.setValue(int(frac * sb.maximum()))

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self.canvas.view_h = self.viewport().height()
        self.canvas.setFixedWidth(self.viewport().width())
        self.canvas.relayout()

    def wheelEvent(self, e):
        sb = self.verticalScrollBar()
        if not e.pixelDelta().isNull() and e.phase() != Qt.NoScrollPhase:
            self._anim.stop()
            sb.setValue(sb.value() - e.pixelDelta().y())  # touchpad de precisão: já vem suave
            e.accept()
            return
        dy = e.angleDelta().y()
        if dy == 0:
            return super().wheelEvent(e)
        base = self._target if self._anim.state() == QPropertyAnimation.Running else sb.value()
        step = max(90, int(self.canvas.cell_h * 0.55))
        self._target = max(sb.minimum(), min(sb.maximum(), int(base - dy / 120 * step)))
        self._anim.stop()
        self._anim.setStartValue(sb.value())
        self._anim.setEndValue(self._target)
        self._anim.start()
        e.accept()


# --------------------------------------------------------------------------- dock
def blur(pm: QPixmap, factor: int = 14) -> QPixmap:
    """Desfoque rápido: reduz e amplia de novo com filtro suave, em duas passadas."""
    if pm.isNull():
        return pm
    dpr = pm.devicePixelRatio()
    w, h = pm.width(), pm.height()
    q = lambda img, a, b: img.scaled(max(1, a), max(1, b), Qt.IgnoreAspectRatio, Qt.SmoothTransformation)  # noqa: E731
    out = q(q(q(q(pm, w // 4, h // 4), w // factor, h // factor), w // 4, h // 4), w, h)
    out.setDevicePixelRatio(dpr)
    return out


class DockButton(QToolButton):
    def __init__(self, icon_name: str, tip: str, parent=None):
        super().__init__(parent)
        self.icon_name = icon_name
        self.setToolTip(tip)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(54, 64)
        self._scale = 1.0
        self._anim = QPropertyAnimation(self, b"scale", self)
        self._anim.setDuration(140)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self.setStyleSheet("QToolButton { background: transparent; border: none; }")

    def get_scale(self):
        return self._scale

    def set_scale(self, v):
        self._scale = v
        self.update()

    scale = Property(float, get_scale, set_scale)

    def _to(self, v):
        self._anim.stop()
        self._anim.setStartValue(self._scale)
        self._anim.setEndValue(v)
        self._anim.start()

    def enterEvent(self, e):
        self._to(1.18)
        super().enterEvent(e)

    def leaveEvent(self, e):
        self._to(1.0)
        super().leaveEvent(e)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        s = 40 * self._scale
        x = (self.width() - s) / 2
        y = (self.height() - s) / 2 - (self._scale - 1) * 12
        r = QRectF(x, y, s, s)
        path = QPainterPath()
        path.addRoundedRect(r, 11 * self._scale, 11 * self._scale)
        hov = self.underMouse()
        p.fillPath(path, QColor(255, 255, 255, 34 if hov else 14))
        p.setPen(QColor(255, 255, 255, 40 if hov else 22))
        p.drawPath(path)
        isz = int(21 * self._scale)
        pm = theme.pixmap(self.icon_name, isz, theme.SILVER_HI if hov else theme.SILVER)
        p.drawPixmap(int(r.center().x() - isz / 2), int(r.center().y() - isz / 2), pm)
        if self.isDown():
            p.fillPath(path, QColor(0, 0, 0, 60))


class SearchBox(QLineEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setPlaceholderText("Pesquisar jogos…")
        self.setClearButtonEnabled(True)
        self.addAction(theme.icon("search", theme.SILVER_LO, 16), QLineEdit.LeadingPosition)
        self.setFixedSize(220, 38)
        self.setStyleSheet(
            "QLineEdit { background: rgba(255,255,255,0.07); border: 1px solid rgba(255,255,255,0.14);"
            " border-radius: 11px; padding: 0 8px 0 2px; font-size: 13px; color: #eef1f5; }"
            f"QLineEdit:focus {{ border-color: {theme.ACCENT}; background: rgba(255,255,255,0.10); }}")

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Escape:
            self.clear()
            self.clearFocus()
            return
        super().keyPressEvent(e)


class Dock(QFrame):
    add_game = Signal()
    open_emulator = Signal()
    open_roms = Signal()
    open_settings = Signal()
    size_changed = Signal(int)
    search_changed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.backdrop = QPixmap()
        lay = QHBoxLayout(self)
        lay.setContentsMargins(15, 0, 10, 0)
        lay.setSpacing(2)

        self.search = SearchBox()
        self.search.textChanged.connect(self.search_changed)
        self.btn_add = DockButton("add", "Adicionar jogo manualmente")
        self.btn_emu = DockButton("gamepad", "Abrir o emulador sem jogo")
        self.btn_roms = DockButton("folder", "Abrir a pasta de ROMs")
        self.btn_cfg = DockButton("settings", "Configurações")
        self.btn_add.clicked.connect(self.add_game)
        self.btn_emu.clicked.connect(self.open_emulator)
        self.btn_roms.clicked.connect(self.open_roms)
        self.btn_cfg.clicked.connect(self.open_settings)

        slider_box = QWidget()
        slider_box.setAttribute(Qt.WA_TranslucentBackground)
        sl = QHBoxLayout(slider_box)
        sl.setContentsMargins(10, 0, 10, 0)
        sl.setSpacing(8)
        small = QLabel()
        small.setPixmap(theme.pixmap("grid_small", 15, theme.SILVER_LO))
        big = QLabel()
        big.setPixmap(theme.pixmap("grid_big", 17, theme.SILVER_LO))
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(110, 300)
        self.slider.setFixedWidth(110)
        self.slider.setToolTip("Tamanho das capas")
        self.slider.setCursor(Qt.PointingHandCursor)
        self.slider.valueChanged.connect(self.size_changed)
        sl.addWidget(small)
        sl.addWidget(self.slider)
        sl.addWidget(big)

        lay.addWidget(self.search)
        lay.addSpacing(10)
        lay.addWidget(self._sep())
        lay.addSpacing(4)
        for w in (self.btn_add, self.btn_emu, self.btn_roms):
            lay.addWidget(w)
        lay.addSpacing(4)
        lay.addWidget(self._sep())
        lay.addWidget(slider_box)
        lay.addWidget(self._sep())
        lay.addSpacing(4)
        lay.addWidget(self.btn_cfg)
        self.setFixedHeight(68)

    def _sep(self):
        s = QFrame()
        s.setFixedSize(1, 30)
        s.setStyleSheet("background: rgba(255,255,255,0.14);")
        return s

    def set_backdrop(self, pm: QPixmap):
        self.backdrop = pm
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        path = QPainterPath()
        path.addRoundedRect(r, 20, 20)
        p.save()
        p.setClipPath(path)
        if not self.backdrop.isNull():
            p.drawPixmap(0, 0, self.backdrop)
        p.fillRect(self.rect(), QColor(16, 18, 23, 140))
        g = QLinearGradient(0, 0, 0, self.height())
        g.setColorAt(0, QColor(255, 255, 255, 30))
        g.setColorAt(0.5, QColor(255, 255, 255, 6))
        g.setColorAt(1, QColor(255, 255, 255, 0))
        p.fillRect(self.rect(), g)
        p.restore()
        p.setPen(QPen(QColor(220, 228, 238, 55), 1))
        p.drawPath(path)


# --------------------------------------------------------------------------- logo
class LogoBox(QWidget):
    """Caixa prata com o nome. Arraste para mover a janela; duplo clique maximiza."""
    double_clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(172, 42)
        self.setToolTip("Arraste para mover · duplo clique para maximizar")
        self.setCursor(Qt.OpenHandCursor)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(1, 1, -1, -3)
        sh = QPainterPath()
        sh.addRoundedRect(r.adjusted(0, 2, 0, 3), 12, 12)
        p.fillPath(sh, QColor(0, 0, 0, 100))
        path = QPainterPath()
        path.addRoundedRect(r, 12, 12)
        g = QLinearGradient(0, r.top(), 0, r.bottom())
        g.setColorAt(0, QColor(theme.SILVER_HI))
        g.setColorAt(0.48, QColor(theme.SILVER))
        g.setColorAt(0.52, QColor("#b6c3d2"))
        g.setColorAt(1, QColor("#9fadbf"))
        p.fillPath(path, g)
        p.setPen(QPen(QColor(255, 255, 255, 160), 1))
        p.drawPath(path)
        f = QFont(self.font())
        f.setPixelSize(18)
        f.setWeight(QFont.DemiBold)
        f.setItalic(False)
        p.setFont(f)
        p.setPen(QColor(theme.DARK_TEXT))
        p.drawText(r, Qt.AlignCenter, "MD Launcher")

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton and self.window().windowHandle():
            self.window().windowHandle().startSystemMove()

    def mouseDoubleClickEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.double_clicked.emit()


# --------------------------------------------------------------------------- botões da janela (padrão Windows)
class CaptionButton(QToolButton):
    R = 10

    def __init__(self, kind: str, tip: str, side: str = "", parent=None):
        super().__init__(parent)
        self.kind, self.side = kind, side
        self.setToolTip(tip)
        self.setFixedSize(46, 34)
        self.setStyleSheet("background: transparent; border: none;")

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        hov, down = self.underMouse(), self.isDown()
        if hov or down:
            w, h, R = self.width(), self.height(), self.R
            r = {"left": QRectF(0.5, 0.5, w + R, h - 1), "right": QRectF(-R, 0.5, w + R - 0.5, h - 1)}.get(
                self.side, QRectF(-R, 0, w + 2 * R, h))
            path = QPainterPath()
            path.addRoundedRect(r, R, R)
            p.setClipRect(self.rect())
            if self.kind == "close":
                p.fillPath(path, QColor("#c42b1c") if not down else QColor("#a32517"))
            else:
                p.fillPath(path, QColor(255, 255, 255, 40 if down else 24))
            p.setClipping(False)
        p.setRenderHint(QPainter.Antialiasing, False)
        col = QColor("#ffffff") if (hov and self.kind == "close") else QColor(theme.SILVER)
        p.setPen(QPen(col, 1))
        cx, cy = self.width() // 2, self.height() // 2
        if self.kind == "min":
            p.drawLine(cx - 5, cy, cx + 5, cy)
        elif self.kind == "max":
            p.drawRect(cx - 5, cy - 5, 10, 10)
        elif self.kind == "restore":
            p.drawRect(cx - 5, cy - 3, 8, 8)
            p.drawLine(cx - 3, cy - 5, cx + 5, cy - 5)
            p.drawLine(cx + 5, cy - 5, cx + 5, cy + 3)
        elif self.kind == "close":
            p.setRenderHint(QPainter.Antialiasing, True)
            p.setPen(QPen(col, 1.1))
            p.drawLine(QPoint(cx - 5, cy - 5), QPoint(cx + 5, cy + 5))
            p.drawLine(QPoint(cx + 5, cy - 5), QPoint(cx - 5, cy + 5))


class WindowControls(QWidget):
    """Minimizar, maximizar e fechar (padrão Windows) numa caixa prata escura de cantos curvos."""
    R = 10

    def __init__(self, win: QWidget):
        super().__init__(win)
        self.win = win
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        self.b_min = CaptionButton("min", "Minimizar", "left")
        self.b_max = CaptionButton("max", "Maximizar")
        self.b_close = CaptionButton("close", "Fechar", "right")
        for b in (self.b_min, self.b_max, self.b_close):
            lay.addWidget(b)
        self.b_close.clicked.connect(win.close)
        self.b_min.clicked.connect(win.showMinimized)
        self.b_max.clicked.connect(self.toggle_max)
        self.setFixedSize(46 * 3, 34)

    def toggle_max(self):
        if self.win.isMaximized():
            self.win.showNormal()
        else:
            self.win.showMaximized()

    def sync(self):
        m = self.win.isMaximized()
        self.b_max.kind = "restore" if m else "max"
        self.b_max.setToolTip("Restaurar" if m else "Maximizar")
        self.b_max.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        g = QLinearGradient(0, 0, 0, self.height())
        g.setColorAt(0, QColor("#4b535e"))
        g.setColorAt(0.5, QColor("#373d46"))
        g.setColorAt(1, QColor("#2a2f36"))
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        sh = QPainterPath()
        sh.addRoundedRect(r, self.R, self.R)
        p.fillPath(sh, g)
        p.setPen(QPen(QColor(220, 228, 238, 62), 1))
        p.drawPath(sh)


class StatusPill(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background: rgba(14,16,21,0.85); border: 1px solid rgba(220,228,238,0.16);"
                           f" border-radius: 10px; padding: 6px 12px; font-size: 12px; color: {theme.SILVER};")
        self.hide()

    def setText(self, t: str):
        super().setText(t)
        self.setVisible(bool(t))
        self.adjustSize()
