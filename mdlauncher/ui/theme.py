"""Cores, folha de estilo e ícones SVG do MD Launcher."""
from __future__ import annotations

from functools import lru_cache

from PySide6.QtCore import QByteArray, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

RED = "#e2231a"        # vermelho Mega Drive
RED_HOVER = "#ff3b30"
GOLD = "#f5c542"
BG = "#0a0a0c"
CARD = "#141418"
CARD_2 = "#1b1b21"
LINE = "#2a2a32"
TEXT = "#f2f2f5"
MUTED = "#9a9aa6"

FONT_STACK = '"Segoe UI Variable Text", "Segoe UI", "Inter", "Helvetica Neue", Arial, sans-serif'

QSS = f"""
* {{ font-family: {FONT_STACK}; color: {TEXT}; outline: none; }}
QToolTip {{ background: #1d1d23; color: {TEXT}; border: 1px solid {LINE}; padding: 5px 8px; border-radius: 6px; }}
QLabel#muted {{ color: {MUTED}; }}
QLabel#h1 {{ font-size: 26px; font-weight: 800; }}
QLabel#h2 {{ font-size: 17px; font-weight: 700; }}
QLabel#section {{ color: {MUTED}; font-size: 11px; font-weight: 700; letter-spacing: 1px; text-transform: uppercase; }}
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QPlainTextEdit {{
    background: #0f0f13; border: 1px solid {LINE}; border-radius: 8px; padding: 7px 10px;
    selection-background-color: {RED};
}}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {{ border-color: {RED}; }}
QComboBox::drop-down {{ border: none; width: 24px; }}
QComboBox QAbstractItemView {{ background: #16161b; border: 1px solid {LINE}; selection-background-color: {RED}; }}
QPushButton {{
    background: {CARD_2}; border: 1px solid {LINE}; border-radius: 8px; padding: 8px 14px; font-weight: 600;
}}
QPushButton:hover {{ background: #24242c; border-color: #3a3a46; }}
QPushButton:pressed {{ background: #18181e; }}
QPushButton:disabled {{ color: #5c5c66; }}
QPushButton#primary {{ background: {RED}; border: 1px solid {RED}; color: white; }}
QPushButton#primary:hover {{ background: {RED_HOVER}; }}
QPushButton#primary:disabled {{ background: #5a1a17; border-color: #5a1a17; color: #c9a3a0; }}
QPushButton#danger {{ color: #ff6b62; }}
QPushButton#ghost {{ background: transparent; border: none; }}
QPushButton#ghost:hover {{ background: rgba(255,255,255,0.08); }}
QPushButton#toggle:checked {{ background: rgba(226,35,26,0.18); border-color: {RED}; color: white; }}
QCheckBox {{ spacing: 8px; }}
QCheckBox::indicator {{ width: 18px; height: 18px; border-radius: 5px; border: 1px solid #4a4a55; background: #0f0f13; }}
QCheckBox::indicator:checked {{ background: {RED}; border-color: {RED}; image: url(:/check); }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 4px 2px; }}
QScrollBar::handle:vertical {{ background: rgba(255,255,255,0.16); border-radius: 3px; min-height: 40px; }}
QScrollBar::handle:vertical:hover {{ background: rgba(255,255,255,0.3); }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px 4px; }}
QScrollBar::handle:horizontal {{ background: rgba(255,255,255,0.16); border-radius: 3px; min-width: 40px; }}
QScrollBar::add-line, QScrollBar::sub-line, QScrollBar::add-page, QScrollBar::sub-page {{ background: none; height: 0; width: 0; }}
QSlider::groove:horizontal {{ height: 4px; background: rgba(255,255,255,0.18); border-radius: 2px; }}
QSlider::sub-page:horizontal {{ background: {RED}; border-radius: 2px; }}
QSlider::handle:horizontal {{ background: white; width: 14px; height: 14px; margin: -5px 0; border-radius: 7px; }}
QProgressBar {{ background: #0f0f13; border: 1px solid {LINE}; border-radius: 6px; height: 10px; text-align: center; font-size: 10px; }}
QProgressBar::chunk {{ background: {RED}; border-radius: 5px; }}
QListWidget {{ background: #0f0f13; border: 1px solid {LINE}; border-radius: 8px; padding: 6px; }}
QListWidget::item {{ border-radius: 6px; padding: 4px; }}
QListWidget::item:selected {{ background: rgba(226,35,26,0.25); border: 2px solid {RED}; }}
QListWidget::item:hover {{ background: rgba(255,255,255,0.06); }}
QScrollArea {{ background: transparent; border: none; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}
QMenu {{ background: #17171c; border: 1px solid {LINE}; border-radius: 8px; padding: 6px; }}
QMenu::item {{ padding: 7px 18px; border-radius: 5px; }}
QMenu::item:selected {{ background: {RED}; }}
QMenu::separator {{ height: 1px; background: {LINE}; margin: 5px 8px; }}
"""

_S = 'fill="none" stroke="{c}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"'
ICONS = {
    "add": f'<rect x="4" y="3" width="16" height="18" rx="3" {_S}/><path d="M12 8v8M8 12h8" {_S}/>',
    "gamepad": f'<path d="M6.5 8h11a4.5 4.5 0 0 1 4.3 5.8l-1 3.4a2.4 2.4 0 0 1-4 1L14.6 16H9.4l-2.2 2.2a2.4 2.4 0 0 1-4-1l-1-3.4A4.5 4.5 0 0 1 6.5 8z" {_S}/>'
               f'<path d="M7.5 11v3M6 12.5h3" {_S}/><circle cx="15.5" cy="11.5" r=".6" fill="{{c}}"/><circle cx="17.5" cy="13.5" r=".6" fill="{{c}}"/>',
    "folder": f'<path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" {_S}/>',
    "settings": f'<circle cx="12" cy="12" r="3" {_S}/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z" {_S}/>',
    "play": '<path d="M7 4.5v15a1 1 0 0 0 1.5.86l12.4-7.5a1 1 0 0 0 0-1.72L8.5 3.64A1 1 0 0 0 7 4.5z" fill="{c}"/>',
    "fullscreen": f'<path d="M4 9V5a1 1 0 0 1 1-1h4M15 4h4a1 1 0 0 1 1 1v4M20 15v4a1 1 0 0 1-1 1h-4M9 20H5a1 1 0 0 1-1-1v-4" {_S}/>',
    "edit": f'<path d="M12 20h9M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4z" {_S}/>',
    "close": f'<path d="M6 6l12 12M18 6L6 18" {_S}/>',
    "min": f'<path d="M5 12h14" {_S}/>',
    "max": f'<rect x="5" y="5" width="14" height="14" rx="2" {_S}/>',
    "restore": f'<rect x="4" y="8" width="12" height="12" rx="2" {_S}/><path d="M8 8V6a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2h-2" {_S}/>',
    "clock": f'<circle cx="12" cy="12" r="9" {_S}/><path d="M12 7v5l3 2" {_S}/>',
    "calendar": f'<rect x="3" y="5" width="18" height="16" rx="2" {_S}/><path d="M16 3v4M8 3v4M3 10h18" {_S}/>',
    "users": f'<circle cx="9" cy="8" r="3.5" {_S}/><path d="M2.5 20a6.5 6.5 0 0 1 13 0M16 4.6a3.5 3.5 0 0 1 0 6.8M18.5 14a6.5 6.5 0 0 1 3 6" {_S}/>',
    "user": f'<circle cx="12" cy="8" r="4" {_S}/><path d="M4.5 21a7.5 7.5 0 0 1 15 0" {_S}/>',
    "grid_small": '<g fill="{c}"><rect x="4" y="4" width="4" height="4" rx="1"/><rect x="10" y="4" width="4" height="4" rx="1"/><rect x="16" y="4" width="4" height="4" rx="1"/><rect x="4" y="10" width="4" height="4" rx="1"/><rect x="10" y="10" width="4" height="4" rx="1"/><rect x="16" y="10" width="4" height="4" rx="1"/><rect x="4" y="16" width="4" height="4" rx="1"/><rect x="10" y="16" width="4" height="4" rx="1"/><rect x="16" y="16" width="4" height="4" rx="1"/></g>',
    "grid_big": '<g fill="{c}"><rect x="3" y="3" width="8" height="8" rx="2"/><rect x="13" y="3" width="8" height="8" rx="2"/><rect x="3" y="13" width="8" height="8" rx="2"/><rect x="13" y="13" width="8" height="8" rx="2"/></g>',
    "search": f'<circle cx="11" cy="11" r="7" {_S}/><path d="M20 20l-3.5-3.5" {_S}/>',
    "image": f'<rect x="3" y="4" width="18" height="16" rx="2" {_S}/><circle cx="8.5" cy="9.5" r="1.5" {_S}/><path d="M21 16l-5-5-9 9" {_S}/>',
    "trash": f'<path d="M4 7h16M10 11v6M14 11v6M5 7l1 12a2 2 0 0 0 2 2h8a2 2 0 0 0 2-2l1-12M9 7V4h6v3" {_S}/>',
    "check": '<path d="M5 12.5l4.5 4.5L19 7.5" fill="none" stroke="{c}" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>',
    "refresh": f'<path d="M20 11a8 8 0 0 0-14.9-3.5M4 4v4h4M4 13a8 8 0 0 0 14.9 3.5M20 20v-4h-4" {_S}/>',
    "cart": f'<path d="M5 3h14v12l-2 2v4H7v-4l-2-2z" {_S}/><path d="M8 7h8M8 10h8" {_S}/>',
}


def svg(name: str, color: str = TEXT) -> bytes:
    body = ICONS[name].replace("{c}", color).replace("{{c}}", color)
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">{body}</svg>'.encode()


@lru_cache(maxsize=512)
def pixmap(name: str, size: int = 24, color: str = TEXT, dpr: float = 2.0) -> QPixmap:
    r = QSvgRenderer(QByteArray(svg(name, color)))
    pm = QPixmap(int(size * dpr), int(size * dpr))
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    r.render(p, QRectF(0, 0, size * dpr, size * dpr))
    p.end()
    pm.setDevicePixelRatio(dpr)
    return pm


def icon(name: str, color: str = TEXT, size: int = 24) -> QIcon:
    ic = QIcon()
    ic.addPixmap(pixmap(name, size, color), QIcon.Normal)
    ic.addPixmap(pixmap(name, size, "#6a6a74"), QIcon.Disabled)
    return ic


def color(hexstr: str, alpha: int = 255) -> QColor:
    c = QColor(hexstr)
    c.setAlpha(alpha)
    return c


def fmt_playtime(sec: int) -> str:
    sec = int(sec or 0)
    if sec < 60:
        return "Nunca jogado" if sec == 0 else "Menos de 1 min"
    h, m = divmod(sec // 60, 60)
    if h == 0:
        return f"{m} min"
    return f"{h} h {m:02d} min"


def fmt_date(d: str) -> str:
    if not d:
        return ""
    parts = d.split("-")
    if len(parts) == 3:
        return f"{parts[2]}/{parts[1]}/{parts[0]}"
    return d
