"""Componentes de formulário reutilizados nos modais."""
from __future__ import annotations

from PySide6.QtCore import QDir, Qt, Signal
from PySide6.QtWidgets import (QFileDialog, QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout,
                               QWidget)

from . import theme


class PathField(QWidget):
    changed = Signal(str)

    def __init__(self, mode: str = "file", filter_: str = "", placeholder: str = "", parent=None):
        super().__init__(parent)
        self.mode, self.filter = mode, filter_
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)
        self.edit = QLineEdit()
        self.edit.setPlaceholderText(placeholder)
        self.edit.textChanged.connect(self.changed)
        self.btn = QPushButton("Procurar…")
        self.btn.setCursor(Qt.PointingHandCursor)
        self.btn.clicked.connect(self.browse)
        lay.addWidget(self.edit, 1)
        lay.addWidget(self.btn)

    def browse(self):
        cur = self.edit.text()
        if self.mode == "dir":
            p = QFileDialog.getExistingDirectory(self, "Escolher pasta", cur)
        else:
            p, _ = QFileDialog.getOpenFileName(self, "Escolher arquivo", cur, self.filter)
        if p:
            self.edit.setText(QDir.toNativeSeparators(p))

    def text(self) -> str:
        return self.edit.text().strip()

    def setText(self, t: str):
        self.edit.setText(t or "")


def section(title: str) -> QLabel:
    l = QLabel(title.upper())
    l.setObjectName("section")
    l.setStyleSheet(f"color: {theme.MUTED}; font-size: 11px; font-weight: 700; letter-spacing: 1px; padding-top: 6px;")
    return l


def hint(text: str) -> QLabel:
    l = QLabel(text)
    l.setWordWrap(True)
    l.setOpenExternalLinks(True)
    l.setTextFormat(Qt.RichText)
    l.setStyleSheet(f"color: {theme.MUTED}; font-size: 12px;")
    return l


def header(title: str, on_close=None, subtitle: str = "") -> QWidget:
    w = QWidget()
    lay = QHBoxLayout(w)
    lay.setContentsMargins(0, 0, 0, 0)
    col = QVBoxLayout()
    col.setSpacing(2)
    t = QLabel(title)
    t.setStyleSheet("font-size: 21px; font-weight: 800;")
    col.addWidget(t)
    if subtitle:
        s = QLabel(subtitle)
        s.setStyleSheet(f"color: {theme.MUTED}; font-size: 12px;")
        col.addWidget(s)
    lay.addLayout(col, 1)
    if on_close:
        b = QPushButton()
        b.setObjectName("ghost")
        b.setIcon(theme.icon("close"))
        b.setFixedSize(34, 34)
        b.setCursor(Qt.PointingHandCursor)
        b.clicked.connect(on_close)
        lay.addWidget(b, 0, Qt.AlignTop)
    return w


LINK_SGDB = "https://www.steamgriddb.com/profile/preferences/api"
LINK_IGDB = "https://api-docs.igdb.com/#account-creation"
