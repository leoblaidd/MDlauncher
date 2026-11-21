"""Grid de capas, dock estilo macOS e botões da janela."""
from __future__ import annotations

from PySide6.QtCore import (QAbstractListModel, QEasingCurve, QModelIndex, QPoint, QPropertyAnimation,
                            QRect, QRectF, QSize, Qt, Signal, Property)
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QListView, QSlider, QStyle,
                               QStyledItemDelegate, QToolButton, QWidget)

from ..storage import Game
from . import theme
from .common import cover_crop, load_image, placeholder, rounded

COVER_RATIO = 1.5  # 2:3, padrão das grids do SteamGridDB
TEXT_H = 46


# --------------------------------------------------------------------------- modelo
class GameModel(QAbstractListModel):
    def __init__(self):
        super().__init__()
        self.games: list[Game] = []

    def set_games(self, games: list[Game]):
        self.beginResetModel()
        self.games = list(games)
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.games)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        g = self.games[index.row()]
        if role == Qt.DisplayRole:
            return g.name
        if role == Qt.UserRole:
            return g
        if role == Qt.ToolTipRole:
            return g.name
        return None

    def refresh(self, gid: str):
        for i, g in enumerate(self.games):
            if g.id == gid:
                ix = self.index(i)
                self.dataChanged.emit(ix, ix)
                return


# --------------------------------------------------------------------------- delegate
class CoverDelegate(QStyledItemDelegate):
    def __init__(self, view):
        super().__init__(view)
        self.view = view
        self.cover_w = 180
        self._cache: dict = {}

    def set_cover_width(self, w: int):
        self.cover_w = w
        self._cache.clear()

    def invalidate(self, game: Game | None = None):
        if game is None:
            self._cache.clear()
        else:
            for k in [k for k in self._cache if k[0] == game.id]:
                self._cache.pop(k, None)

    def cover_h(self) -> int:
        return int(self.cover_w * COVER_RATIO)

    def sizeHint(self, option, index):
        return QSize(self.cover_w + 24, self.cover_h() + TEXT_H + 16)

    def _pix(self, g: Game):
        dpr = self.view.devicePixelRatioF()
        key = (g.id, g.cover_path, self.cover_w, dpr)
        pm = self._cache.get(key)
        if pm is None:
            w, h = self.cover_w, self.cover_h()
            img = load_image(g.cover_path)
            pm = cover_crop(img, w, h, dpr) if not img.isNull() else placeholder(g.name, w, h, dpr)
            pm = rounded(pm, 10)
            self._cache[key] = pm
        return pm

    def paint(self, p: QPainter, option, index):
        g: Game = index.data(Qt.UserRole)
        p.save()
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        r = option.rect
        hover = bool(option.state & QStyle.State_MouseOver)
        sel = bool(option.state & QStyle.State_Selected) and self.view.hasFocus()
        w, h = self.cover_w, self.cover_h()
        x = r.x() + (r.width() - w) // 2
        y = r.y() + 8 - (5 if hover else 0)
        cover = QRectF(x, y, w, h)

        # sombra
        for i, a in enumerate((40, 26, 14)):
            sp = QPainterPath()
            sp.addRoundedRect(cover.adjusted(-i - 1, -i + 3, i + 1, i + 6), 12 + i, 12 + i)
            p.fillPath(sp, QColor(0, 0, 0, a + (20 if hover else 0)))

        p.drawPixmap(QPoint(int(x), int(y)), self._pix(g))

        path = QPainterPath()
        path.addRoundedRect(cover, 10, 10)
        if hover or sel:
            p.setPen(QPen(QColor(theme.RED), 2.5))
            p.drawPath(path)
        else:
            p.setPen(QPen(QColor(255, 255, 255, 26), 1))
            p.drawPath(path)

        # título + ano
        f = QFont(p.font())
        f.setPixelSize(13)
        f.setWeight(QFont.DemiBold)
        p.setFont(f)
        p.setPen(QColor(245, 245, 248) if hover else QColor(222, 222, 228))
        tr = QRect(r.x() + 6, int(y + h + 8), r.width() - 12, 18)
        p.drawText(tr, Qt.AlignHCenter | Qt.AlignVCenter, p.fontMetrics().elidedText(g.name, Qt.ElideRight, tr.width()))
        sub = " · ".join(s for s in (g.year, "Multiplayer" if g.multiplayer else "") if s)
        if sub:
            f.setPixelSize(11)
            f.setWeight(QFont.Normal)
            p.setFont(f)
            p.setPen(QColor(theme.MUTED))
            p.drawText(QRect(tr.x(), tr.bottom() + 2, tr.width(), 16), Qt.AlignHCenter | Qt.AlignVCenter, sub)
        p.restore()


# --------------------------------------------------------------------------- grid
class GameGrid(QListView):
    game_clicked = Signal(object)
    game_context = Signal(object, QPoint)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.model_ = GameModel()
        self.setModel(self.model_)
        self.delegate = CoverDelegate(self)
        self.setItemDelegate(self.delegate)
        self.setViewMode(QListView.IconMode)
        self.setResizeMode(QListView.Adjust)
        self.setMovement(QListView.Static)
        self.setUniformItemSizes(True)
        self.setSelectionMode(QListView.SingleSelection)
        self.setMouseTracking(True)
        self.setVerticalScrollMode(QListView.ScrollPerPixel)
        self.verticalScrollBar().setSingleStep(24)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setFrameShape(QFrame.NoFrame)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.viewport().setAttribute(Qt.WA_TranslucentBackground)
        self.setStyleSheet("QListView { background: transparent; border: none; }")
        self.setViewportMargins(18, 4, 18, 110)  # espaço para o dock
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._ctx)
        self.clicked.connect(lambda ix: self.game_clicked.emit(ix.data(Qt.UserRole)))
        self.activated.connect(lambda ix: self.game_clicked.emit(ix.data(Qt.UserRole)))
        self.empty_text = ""
        self.set_cover_width(180)

    def _ctx(self, pos):
        ix = self.indexAt(pos)
        if ix.isValid():
            self.game_context.emit(ix.data(Qt.UserRole), self.viewport().mapToGlobal(pos))

    def set_cover_width(self, w: int):
        self.delegate.set_cover_width(w)
        self._relayout()

    def _relayout(self):
        hint = self.delegate.sizeHint(None, QModelIndex())
        # distribui as colunas para preencher a largura disponível
        avail = max(1, self.viewport().width() - 4)
        cols = max(1, avail // hint.width())
        cell_w = avail // cols
        self.setGridSize(QSize(cell_w, hint.height() + 6))
        self.viewport().update()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._relayout()

    def paintEvent(self, e):
        super().paintEvent(e)
        if self.model_.rowCount() == 0 and self.empty_text:
            p = QPainter(self.viewport())
            p.setPen(QColor(theme.MUTED))
            f = p.font()
            f.setPixelSize(15)
            p.setFont(f)
            p.drawText(self.viewport().rect(), Qt.AlignCenter, self.empty_text)


# --------------------------------------------------------------------------- dock
class DockButton(QToolButton):
    def __init__(self, icon_name: str, tip: str, parent=None):
        super().__init__(parent)
        self.icon_name = icon_name
        self.setToolTip(tip)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(58, 62)
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
        self._to(1.22)
        super().enterEvent(e)

    def leaveEvent(self, e):
        self._to(1.0)
        super().leaveEvent(e)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        s = 42 * self._scale
        x = (self.width() - s) / 2
        y = self.height() - s - 8 - (self._scale - 1) * 14
        r = QRectF(x, y, s, s)
        path = QPainterPath()
        path.addRoundedRect(r, 11 * self._scale, 11 * self._scale)
        p.fillPath(path, QColor(255, 255, 255, 30 if self.underMouse() else 16))
        p.setPen(QColor(255, 255, 255, 30))
        p.drawPath(path)
        isz = int(22 * self._scale)
        pm = theme.pixmap(self.icon_name, isz, "#ffffff" if self.underMouse() else "#e6e6ea")
        p.drawPixmap(int(r.center().x() - isz / 2), int(r.center().y() - isz / 2), pm)
        if self.isDown():
            p.fillPath(path, QColor(0, 0, 0, 60))


class Dock(QFrame):
    add_game = Signal()
    open_emulator = Signal()
    open_roms = Signal()
    open_settings = Signal()
    size_changed = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("dock")
        self.setAttribute(Qt.WA_StyledBackground, False)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 0, 12, 0)
        lay.setSpacing(2)

        self.btn_add = DockButton("add", "Adicionar jogo manualmente")
        self.btn_emu = DockButton("gamepad", "Abrir o emulador sem jogo")
        self.btn_roms = DockButton("folder", "Abrir a pasta de ROMs")
        self.btn_cfg = DockButton("settings", "Configurações")
        self.btn_add.clicked.connect(self.add_game)
        self.btn_emu.clicked.connect(self.open_emulator)
        self.btn_roms.clicked.connect(self.open_roms)
        self.btn_cfg.clicked.connect(self.open_settings)

        slider_box = QWidget()
        sl = QHBoxLayout(slider_box)
        sl.setContentsMargins(10, 14, 10, 0)
        sl.setSpacing(8)
        small = QLabel()
        small.setPixmap(theme.pixmap("grid_small", 16, "#a8a8b2"))
        big = QLabel()
        big.setPixmap(theme.pixmap("grid_big", 18, "#a8a8b2"))
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(110, 300)
        self.slider.setFixedWidth(120)
        self.slider.setToolTip("Tamanho das capas")
        self.slider.setCursor(Qt.PointingHandCursor)
        self.slider.valueChanged.connect(self.size_changed)
        sl.addWidget(small)
        sl.addWidget(self.slider)
        sl.addWidget(big)

        for w in (self.btn_add, self.btn_emu, self.btn_roms):
            lay.addWidget(w)
        lay.addWidget(self._sep())
        lay.addWidget(slider_box)
        lay.addWidget(self._sep())
        lay.addWidget(self.btn_cfg)
        self.setFixedHeight(76)

    def _sep(self):
        s = QFrame()
        s.setFixedSize(1, 34)
        s.setStyleSheet("background: rgba(255,255,255,0.14); margin-top: 14px;")
        return s

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(1, 10, -1, -1)
        path = QPainterPath()
        path.addRoundedRect(r, 20, 20)
        p.fillPath(path, QColor(22, 22, 27, 215))
        p.setPen(QColor(255, 255, 255, 34))
        p.drawPath(path)


# --------------------------------------------------------------------------- botões da janela
class WinButton(QToolButton):
    def __init__(self, kind: str, color_hex: str, tip: str, parent=None):
        super().__init__(parent)
        self.kind = kind
        self.c = QColor(color_hex)
        self.setFixedSize(16, 16)
        self.setToolTip(tip)
        self.setCursor(Qt.PointingHandCursor)
        self.setStyleSheet("background: transparent; border: none;")
        self.group_hover = False

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        c = QColor(self.c)
        if self.isDown():
            c = c.darker(130)
        p.setBrush(c)
        p.setPen(QPen(c.darker(140), 0.8))
        p.drawEllipse(QRectF(1, 1, 14, 14))
        if self.group_hover:
            name = {"close": "close", "min": "min", "max": "max", "restore": "restore"}[self.kind]
            p.drawPixmap(3, 3, theme.pixmap(name, 10, "#3a0b08" if self.kind == "close" else "#3d2a00"))


class WindowControls(QWidget):
    def __init__(self, win: QWidget):
        super().__init__(win)
        self.win = win
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(9)
        self.b_close = WinButton("close", "#ff5f57", "Fechar")
        self.b_min = WinButton("min", "#febc2e", "Minimizar")
        self.b_max = WinButton("max", "#28c840", "Maximizar")
        self.b_max.kind = "max"
        for b in (self.b_close, self.b_min, self.b_max):
            lay.addWidget(b)
        self.b_close.clicked.connect(win.close)
        self.b_min.clicked.connect(win.showMinimized)
        self.b_max.clicked.connect(self.toggle_max)

    def toggle_max(self):
        if self.win.isMaximized():
            self.win.showNormal()
        else:
            self.win.showMaximized()

    def sync(self):
        self.b_max.kind = "restore" if self.win.isMaximized() else "max"
        self.b_max.setToolTip("Restaurar" if self.win.isMaximized() else "Maximizar")
        self.b_max.update()

    def enterEvent(self, e):
        for b in (self.b_close, self.b_min, self.b_max):
            b.group_hover = True
            b.update()

    def leaveEvent(self, e):
        for b in (self.b_close, self.b_min, self.b_max):
            b.group_hover = False
            b.update()
