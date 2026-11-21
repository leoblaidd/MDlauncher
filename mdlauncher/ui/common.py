"""Utilitários de UI: tarefas assíncronas, fundo xadrez, overlay modal e carregamento de imagens."""
from __future__ import annotations

from PySide6.QtCore import (QEasingCurve, QObject, QPropertyAnimation, QRectF, QRunnable, Qt,
                            QThreadPool, Signal)
from PySide6.QtGui import (QBrush, QColor, QImage, QPainter, QPainterPath, QPixmap,
                           QRadialGradient, QLinearGradient)
from PySide6.QtWidgets import QGraphicsOpacityEffect, QWidget

from . import theme

# --------------------------------------------------------------------------- async
_pool = QThreadPool.globalInstance()
_pool.setMaxThreadCount(max(4, _pool.maxThreadCount()))
_alive: set = set()


class _Sig(QObject):
    done = Signal(object)
    error = Signal(str)


class _Task(QRunnable):
    def __init__(self, fn, sig):
        super().__init__()
        self.fn, self.sig = fn, sig

    def run(self):
        try:
            res = self.fn()
        except Exception as e:  # noqa: BLE001
            self.sig.error.emit(str(e) or e.__class__.__name__)
        else:
            self.sig.done.emit(res)


def run_async(fn, on_done=None, on_error=None) -> None:
    sig = _Sig()
    _alive.add(sig)

    def _fin(*_):
        _alive.discard(sig)

    if on_done:
        sig.done.connect(on_done)
    if on_error:
        sig.error.connect(on_error)
    sig.done.connect(_fin)
    sig.error.connect(_fin)
    _pool.start(_Task(fn, sig))


# --------------------------------------------------------------------------- imagens
def load_image(path: str) -> QImage:
    img = QImage(path) if path else QImage()
    return img


def cover_crop(img: QImage | QPixmap, w: int, h: int, dpr: float = 1.0) -> QPixmap:
    """Redimensiona preenchendo (cover) e corta no centro."""
    pm = QPixmap.fromImage(img) if isinstance(img, QImage) else img
    if pm.isNull():
        return QPixmap()
    tw, th = int(w * dpr), int(h * dpr)
    scaled = pm.scaled(tw, th, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
    x = max(0, (scaled.width() - tw) // 2)
    y = max(0, (scaled.height() - th) // 2)
    out = scaled.copy(x, y, tw, th)
    out.setDevicePixelRatio(dpr)
    return out


def rounded(pm: QPixmap, radius: float) -> QPixmap:
    if pm.isNull():
        return pm
    dpr = pm.devicePixelRatio()
    out = QPixmap(pm.size())
    out.fill(Qt.transparent)
    out.setDevicePixelRatio(dpr)
    p = QPainter(out)
    p.setRenderHint(QPainter.Antialiasing)
    path = QPainterPath()
    path.addRoundedRect(QRectF(0, 0, pm.width() / dpr, pm.height() / dpr), radius, radius)
    p.setClipPath(path)
    p.drawPixmap(0, 0, pm)
    p.end()
    return out


def placeholder(name: str, w: int, h: int, dpr: float = 1.0) -> QPixmap:
    """Capa genérica estilo caixa de Mega Drive (grade preta + faixa vermelha)."""
    pm = QPixmap(int(w * dpr), int(h * dpr))
    pm.setDevicePixelRatio(dpr)
    pm.fill(QColor("#0d0d10"))
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(QColor(255, 255, 255, 22))
    step = max(10, w // 10)
    for x in range(0, w + step, step):
        p.drawLine(x, 0, x, h)
    for y in range(0, h + step, step):
        p.drawLine(0, y, w, y)
    band = max(16, h // 9)
    p.fillRect(QRectF(0, 0, w, band), QColor(theme.RED))
    f = p.font()
    f.setBold(True)
    f.setItalic(True)
    f.setPixelSize(max(9, int(band * 0.55)))
    p.setFont(f)
    p.setPen(QColor("white"))
    p.drawText(QRectF(8, 0, w - 16, band), Qt.AlignVCenter | Qt.AlignLeft, "MEGA DRIVE")
    f.setItalic(False)
    f.setPixelSize(max(11, w // 11))
    p.setFont(f)
    p.setPen(QColor(235, 235, 240))
    p.drawText(QRectF(10, band + 10, w - 20, h - band - 20), Qt.AlignCenter | Qt.TextWordWrap, name)
    p.end()
    return pm


# --------------------------------------------------------------------------- fundo xadrez
_tile_cache: dict = {}


def checker_brush(cell: int = 44) -> QBrush:
    if cell not in _tile_cache:
        pm = QPixmap(cell * 2, cell * 2)
        pm.fill(QColor("#0b0b0e"))
        p = QPainter(pm)
        p.fillRect(0, 0, cell, cell, QColor("#111115"))
        p.fillRect(cell, cell, cell, cell, QColor("#111115"))
        p.setPen(QColor(255, 255, 255, 10))
        p.drawLine(0, 0, cell * 2, 0)
        p.drawLine(0, cell, cell * 2, cell)
        p.drawLine(0, 0, 0, cell * 2)
        p.drawLine(cell, 0, cell, cell * 2)
        p.end()
        _tile_cache[cell] = QBrush(pm)
    return _tile_cache[cell]


def paint_background(p: QPainter, rect) -> None:
    p.fillRect(rect, checker_brush())
    # brilho vermelho discreto no topo + vinheta
    g = QRadialGradient(rect.width() * 0.85, -rect.height() * 0.15, rect.width() * 0.75)
    g.setColorAt(0, QColor(226, 35, 26, 34))
    g.setColorAt(1, QColor(226, 35, 26, 0))
    p.fillRect(rect, g)
    v = QRadialGradient(rect.center(), max(rect.width(), rect.height()) * 0.75)
    v.setColorAt(0.55, QColor(0, 0, 0, 0))
    v.setColorAt(1, QColor(0, 0, 0, 170))
    p.fillRect(rect, v)
    lg = QLinearGradient(0, rect.height() - 160, 0, rect.height())
    lg.setColorAt(0, QColor(0, 0, 0, 0))
    lg.setColorAt(1, QColor(0, 0, 0, 120))
    p.fillRect(rect, lg)


# --------------------------------------------------------------------------- overlay modal
class Overlay(QWidget):
    """Camada escura sobre a janela com um cartão central. Subclasses montam self.card."""
    closed = Signal()

    def __init__(self, parent: QWidget, card_size=(860, 560), dismissable: bool = True):
        super().__init__(parent)
        self.dismissable = dismissable
        self.card_size = card_size
        self.setAttribute(Qt.WA_StyledBackground, False)
        self.setFocusPolicy(Qt.StrongFocus)
        self.card = Card(self)
        self._fx = QGraphicsOpacityEffect(self)
        self._fx.setOpacity(0.0)
        self.setGraphicsEffect(self._fx)
        self._anim = QPropertyAnimation(self._fx, b"opacity", self)
        self._anim.setDuration(160)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self._anim.finished.connect(self._anim_finished)
        self._closing = False
        parent.installEventFilter(self)

    def open(self):
        self.setGeometry(self.parentWidget().rect())
        self._layout_card()
        self.show()
        self.raise_()
        self.setFocus()
        self._fx.setEnabled(True)
        self._closing = False
        self._anim.stop()
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(1.0)
        self._anim.start()

    def close_overlay(self):
        if self._closing:
            return
        self._closing = True
        self._fx.setEnabled(True)
        self._anim.stop()
        self._anim.setStartValue(self._fx.opacity())
        self._anim.setEndValue(0.0)
        self._anim.start()

    def _anim_finished(self):
        if self._closing:
            self._finish_close()
        else:
            self._fx.setEnabled(False)

    def _finish_close(self):
        self.hide()
        self.closed.emit()
        self.deleteLater()

    def eventFilter(self, obj, ev):
        if obj is self.parentWidget() and ev.type() == ev.Type.Resize:
            self.setGeometry(self.parentWidget().rect())
            self._layout_card()
        return False

    def _layout_card(self):
        w = min(self.card_size[0], self.width() - 40)
        h = min(self.card_size[1], self.height() - 40)
        self.card.setGeometry((self.width() - w) // 2, (self.height() - h) // 2, w, h)

    def paintEvent(self, _):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(0, 0, 0, 175))

    def mousePressEvent(self, ev):
        if self.dismissable and not self.card.geometry().contains(ev.position().toPoint()):
            self.close_overlay()
        ev.accept()

    def keyPressEvent(self, ev):
        if ev.key() == Qt.Key_Escape and self.dismissable:
            self.close_overlay()
        else:
            super().keyPressEvent(ev)


class Card(QWidget):
    def __init__(self, parent=None, radius: int = 16):
        super().__init__(parent)
        self.radius = radius

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5), self.radius, self.radius)
        p.fillPath(path, QColor(theme.CARD))
        p.setPen(QColor(255, 255, 255, 22))
        p.drawPath(path)
