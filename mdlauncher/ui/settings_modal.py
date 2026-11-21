"""Modal de configurações gerais e assistente de primeira execução."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QCheckBox, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QListWidget,
                               QProgressBar, QPushButton, QScrollArea, QStackedWidget, QVBoxLayout,
                               QWidget)

from .. import __version__
from ..emulators import PROFILES, detect_profile
from ..scanner import scan_folder
from ..storage import Settings, data_dir
from . import theme
from .common import Overlay, run_async
from .forms import LINK_IGDB, LINK_SGDB, PathField, header, hint, section

EXE_FILTER = "Executável (*.exe);;Todos (*.*)"


def _profile_text(path: str) -> str:
    p = detect_profile(path) if path else None
    if not path:
        return ""
    if not p:
        return ("Emulador não reconhecido — tudo bem, funciona com qualquer um. "
                "Se ele tiver argumento de tela cheia, informe abaixo.")
    note = f" {p.note}" if p.note else ""
    fs = f"<code>{p.fullscreen}</code>" if p.fullscreen else "nenhum"
    return f"Detectado: <b>{p.label}</b> · tela cheia: {fs}.{note}"


class _Grid:
    """Grade de 2 colunas (rótulo + campo) que lida bem com textos de ajuda com quebra de linha."""

    def __init__(self, widget: QWidget):
        self.g = QGridLayout(widget)
        self.g.setContentsMargins(0, 0, 0, 0)
        self.g.setHorizontalSpacing(12)
        self.g.setVerticalSpacing(8)
        self.g.setColumnMinimumWidth(0, 170)
        self.g.setColumnStretch(1, 1)
        self.r = 0

    def addRow(self, label: str, w: QWidget):
        if label:
            l = QLabel(label)
            self.g.addWidget(l, self.r, 0, Qt.AlignVCenter)
        self.g.addWidget(w, self.r, 1)
        self.r += 1


class EmulatorFields(QWidget):
    """Bloco reaproveitado: exe do emulador + modelo de argumentos + argumento de tela cheia."""

    def __init__(self, s: Settings):
        super().__init__()
        f = _Grid(self)
        self.exe = PathField("file", EXE_FILTER, "C:\\Emuladores\\...\\emulador.exe")
        self.exe.setText(s.emulator_path)
        self.info = hint(_profile_text(s.emulator_path))
        self.tpl = QLineEdit(s.launch_template)
        self.tpl.setPlaceholderText('{fullscreen} "{rom}"')
        self.fs = QLineEdit(s.fullscreen_args)
        self.fs.setPlaceholderText("ex.: -fullscreen, -f, --fullscreen")
        f.addRow("Emulador (.exe)", self.exe)
        f.addRow("", self.info)
        f.addRow("Modelo de argumentos", self.tpl)
        f.addRow("Argumento de tela cheia", self.fs)
        f.addRow("", hint("<code>{rom}</code> vira o caminho da ROM e <code>{fullscreen}</code> vira o argumento "
                          "de tela cheia quando o botão estiver ligado. Presets: "
                          + ", ".join(f"{p.label} <code>{p.fullscreen or '—'}</code>" for p in PROFILES) + "."))
        self._last = s.emulator_path
        self.exe.changed.connect(self._on_exe)

    def _on_exe(self, path: str):
        self.info.setText(_profile_text(path))
        p = detect_profile(path)
        if p and path != self._last:
            self.tpl.setText(p.template)
            self.fs.setText(p.fullscreen)
        self._last = path

    def apply(self, s: Settings):
        s.emulator_path = self.exe.text()
        s.launch_template = self.tpl.text().strip() or '"{rom}"'
        s.fullscreen_args = self.fs.text().strip()


class KeyFields(QWidget):
    def __init__(self, s: Settings):
        super().__init__()
        f = _Grid(self)
        self.sgdb = QLineEdit(s.sgdb_key)
        self.sgdb.setEchoMode(QLineEdit.PasswordEchoOnEdit)
        self.sgdb.setPlaceholderText("Chave da API do SteamGridDB")
        self.cid = QLineEdit(s.igdb_client_id)
        self.cid.setPlaceholderText("Client ID (Twitch)")
        self.sec = QLineEdit(s.igdb_client_secret)
        self.sec.setEchoMode(QLineEdit.PasswordEchoOnEdit)
        self.sec.setPlaceholderText("Client Secret (Twitch)")
        f.addRow("SteamGridDB", self.sgdb)
        f.addRow("", hint(f"Capas e heroes. Pegue sua chave grátis em <a style='color:{theme.LINK}' href='{LINK_SGDB}'>"
                          "steamgriddb.com › Preferências › API</a>."))
        f.addRow("IGDB Client ID", self.cid)
        f.addRow("IGDB Secret", self.sec)
        f.addRow("", hint(f"Opcional: data de lançamento, multiplayer e artes extras. "
                          f"<a style='color:{theme.LINK}' href='{LINK_IGDB}'>Como criar (Twitch Developers)</a>. "
                          "Sem chaves, o launcher ainda busca capas no Libretro Thumbnails."))

    def apply(self, s: Settings):
        s.sgdb_key = self.sgdb.text().strip()
        s.igdb_client_id = self.cid.text().strip()
        s.igdb_client_secret = self.sec.text().strip()


class SettingsModal(Overlay):
    saved = Signal(bool)        # True = pastas de ROM mudaram (reescanear)
    rescan = Signal()
    refetch = Signal(bool)      # True = rebaixar tudo, False = só o que falta
    open_data = Signal()

    def __init__(self, parent, s: Settings):
        super().__init__(parent, card_size=(820, 720))
        self.s = s
        root = QVBoxLayout(self.card)
        root.setContentsMargins(26, 22, 26, 20)
        root.setSpacing(12)
        root.addWidget(header("Configurações", self.close_overlay, f"MD Launcher {__version__}"))

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        body = QWidget()
        v = QVBoxLayout(body)
        v.setContentsMargins(0, 0, 10, 0)
        v.setSpacing(10)
        scroll.setWidget(body)
        root.addWidget(scroll, 1)

        v.addWidget(section("Emulador"))
        self.emu = EmulatorFields(s)
        v.addWidget(self.emu)
        self.fs_default = QCheckBox("Tela cheia ligada por padrão em jogos novos")
        self.fs_default.setChecked(s.fullscreen_default)
        self.minimize = QCheckBox("Minimizar o launcher enquanto o jogo roda")
        self.minimize.setChecked(s.minimize_on_play)
        self.extract = QCheckBox("Extrair ROMs de .zip antes de abrir (para emuladores que não leem zip)")
        self.extract.setChecked(s.extract_zip)
        for c in (self.fs_default, self.minimize, self.extract):
            v.addWidget(c)

        v.addWidget(section("Pastas de ROMs"))
        self.folders = QListWidget()
        self.folders.setFixedHeight(96)
        self.folders.addItems(s.rom_folders)
        v.addWidget(self.folders)
        fr = QHBoxLayout()
        b_add = QPushButton("Adicionar pasta…")
        b_add.clicked.connect(self._add_folder)
        b_rm = QPushButton("Remover selecionada")
        b_rm.clicked.connect(lambda: [self.folders.takeItem(self.folders.row(i)) for i in self.folders.selectedItems()])
        self.subdirs = QCheckBox("Incluir subpastas")
        self.subdirs.setChecked(s.scan_subfolders)
        fr.addWidget(b_add)
        fr.addWidget(b_rm)
        fr.addStretch(1)
        fr.addWidget(self.subdirs)
        v.addLayout(fr)

        v.addWidget(section("Capas e informações"))
        self.keys = KeyFields(s)
        v.addWidget(self.keys)

        v.addWidget(section("Biblioteca"))
        lr = QHBoxLayout()
        b1 = QPushButton("  Reescanear pastas")
        b1.setIcon(theme.icon("refresh"))
        b1.clicked.connect(lambda: (self.save(), self.rescan.emit()))
        b2 = QPushButton("  Buscar artes que faltam")
        b2.setIcon(theme.icon("image"))
        b2.clicked.connect(lambda: (self.save(), self.refetch.emit(False)))
        b3 = QPushButton("Rebaixar tudo")
        b3.setToolTip("Busca de novo capa, hero e dados de todos os jogos (substitui as artes atuais)")
        b3.clicked.connect(lambda: (self.save(), self.refetch.emit(True)))
        b4 = QPushButton("Pasta de dados")
        b4.setToolTip(str(data_dir()))
        b4.clicked.connect(self.open_data)
        for b in (b1, b2, b3, b4):
            lr.addWidget(b)
        lr.addStretch(1)
        v.addLayout(lr)
        v.addStretch(1)

        foot = QHBoxLayout()
        foot.addStretch(1)
        bc = QPushButton("Cancelar")
        bc.clicked.connect(self.close_overlay)
        bs = QPushButton("Salvar")
        bs.setObjectName("primary")
        bs.setFixedWidth(130)
        bs.clicked.connect(lambda: (self.save(), self.close_overlay()))
        foot.addWidget(bc)
        foot.addWidget(bs)
        root.addLayout(foot)

    def _add_folder(self):
        from PySide6.QtCore import QDir
        from PySide6.QtWidgets import QFileDialog
        p = QFileDialog.getExistingDirectory(self, "Pasta de ROMs")
        if p:
            self.folders.addItem(QDir.toNativeSeparators(p))

    def save(self):
        s = self.s
        old = (list(s.rom_folders), s.scan_subfolders)
        self.emu.apply(s)
        self.keys.apply(s)
        s.fullscreen_default = self.fs_default.isChecked()
        s.minimize_on_play = self.minimize.isChecked()
        s.extract_zip = self.extract.isChecked()
        s.scan_subfolders = self.subdirs.isChecked()
        s.rom_folders = [self.folders.item(i).text() for i in range(self.folders.count())]
        s.save()
        self.saved.emit(old != (s.rom_folders, s.scan_subfolders))


# =========================================================================== assistente
class WizardModal(Overlay):
    finished = Signal()

    def __init__(self, parent, s: Settings):
        super().__init__(parent, card_size=(760, 560), dismissable=False)
        self.s = s
        root = QVBoxLayout(self.card)
        root.setContentsMargins(34, 30, 34, 26)
        root.setSpacing(14)

        steps = QHBoxLayout()
        self.dots = []
        for name in ("Boas-vindas", "Emulador", "ROMs", "Capas"):
            l = QLabel(name)
            self.dots.append(l)
            steps.addWidget(l)
            steps.addStretch(1)
        root.addLayout(steps)

        self.stack = QStackedWidget()
        root.addWidget(self.stack, 1)

        # 0 — boas-vindas
        p0 = QWidget()
        v0 = QVBoxLayout(p0)
        v0.addStretch(1)
        logo = QLabel("MD Launcher")
        logo.setStyleSheet(f"font-size: 30px; font-weight: 600; color: {theme.DARK_TEXT}; background: {theme.SILVER_GRAD};"
                           " border: 1px solid #e4eaf1; border-radius: 14px; padding: 10px 26px;")
        v0.addWidget(logo, 0, Qt.AlignHCenter)
        t = QLabel("Sua coleção de Mega Drive com cara de biblioteca de verdade.")
        t.setStyleSheet(f"color: {theme.MUTED}; font-size: 15px;")
        v0.addWidget(t, 0, Qt.AlignHCenter)
        v0.addSpacing(18)
        v0.addWidget(hint("Em três passos: escolha o emulador, aponte a pasta das suas ROMs e (opcional) "
                          "cole a chave do SteamGridDB para baixar capas e heroes automaticamente."), 0)
        v0.addStretch(2)
        self.stack.addWidget(p0)

        # 1 — emulador
        p1 = QWidget()
        v1 = QVBoxLayout(p1)
        v1.addWidget(self._title("Qual emulador vai rodar os jogos?",
                                 "Qualquer emulador de Mega Drive serve: RetroArch, Kega Fusion, BlastEm, ares, Gens…"))
        self.emu = EmulatorFields(s)
        v1.addWidget(self.emu)
        v1.addStretch(1)
        self.stack.addWidget(p1)

        # 2 — pasta de roms
        p2 = QWidget()
        v2 = QVBoxLayout(p2)
        v2.addWidget(self._title("Onde estão suas ROMs?",
                                 "Arquivos .md, .gen, .smd, .bin e também .zip com a ROM dentro."))
        self.roms = PathField("dir")
        self.roms.setText(s.rom_folders[0] if s.rom_folders else "")
        self.roms.changed.connect(self._count)
        v2.addWidget(self.roms)
        self.subdirs = QCheckBox("Incluir subpastas")
        self.subdirs.setChecked(s.scan_subfolders)
        self.subdirs.toggled.connect(lambda _: self._count(self.roms.text()))
        v2.addWidget(self.subdirs)
        self.count = QLabel("")
        self.count.setStyleSheet("font-size: 14px;")
        v2.addWidget(self.count)
        v2.addStretch(1)
        self.stack.addWidget(p2)

        # 3 — chaves
        p3 = QWidget()
        v3 = QVBoxLayout(p3)
        v3.addWidget(self._title("Capas, heroes e informações",
                                 "Cole sua chave do SteamGridDB. O IGDB é opcional e traz data e multiplayer."))
        self.keys = KeyFields(s)
        v3.addWidget(self.keys)
        v3.addStretch(1)
        self.stack.addWidget(p3)

        foot = QHBoxLayout()
        self.b_back = QPushButton("Voltar")
        self.b_back.clicked.connect(lambda: self.go(self.stack.currentIndex() - 1))
        self.b_next = QPushButton("Começar")
        self.b_next.setObjectName("primary")
        self.b_next.setFixedWidth(150)
        self.b_next.clicked.connect(self._next)
        foot.addWidget(self.b_back)
        foot.addStretch(1)
        foot.addWidget(self.b_next)
        root.addLayout(foot)
        self.go(0)
        if s.rom_folders:
            self._count(s.rom_folders[0])

    def _title(self, t, sub):
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 0, 0, 10)
        a = QLabel(t)
        a.setStyleSheet("font-size: 22px; font-weight: 800;")
        b = QLabel(sub)
        b.setWordWrap(True)
        b.setStyleSheet(f"color: {theme.MUTED}; font-size: 13px;")
        v.addWidget(a)
        v.addWidget(b)
        return w

    def go(self, i: int):
        i = max(0, min(3, i))
        self.stack.setCurrentIndex(i)
        self.b_back.setVisible(i > 0)
        self.b_next.setText(["Começar", "Avançar", "Avançar", "Concluir"][i])
        for n, d in enumerate(self.dots):
            on = n == i
            done = n < i
            d.setStyleSheet(f"font-size: 12px; font-weight: 700; padding: 5px 12px; border-radius: 12px;"
                            f"background: {'rgba(169,191,216,0.22)' if on else 'transparent'};"
                            f"color: {'#fff' if on else ('#d0d0d6' if done else '#6f6f79')};")

    def _count(self, path: str):
        self.count.setText("Procurando ROMs…" if path else "")
        if not path:
            return
        rec = self.subdirs.isChecked()

        def work():
            return sum(1 for _ in scan_folder(path, rec))

        def done(n, p=path):
            if p != self.roms.text():
                return
            self.count.setText(f"<b style='color:#7ee787'>{n} jogo(s) de Mega Drive encontrados</b>" if n
                               else "<span style='color:#e6c07b'>Nenhuma ROM de Mega Drive nessa pasta.</span>")

        run_async(work, done)

    def _next(self):
        i = self.stack.currentIndex()
        if i == 1 and not self.emu.exe.text():
            self.emu.info.setText("<span style='color:#e6c07b'>Escolha o .exe do emulador para continuar.</span>")
            return
        if i == 2 and not self.roms.text():
            self.count.setText("<span style='color:#e6c07b'>Escolha a pasta das ROMs.</span>")
            return
        if i < 3:
            self.go(i + 1)
            return
        s = self.s
        self.emu.apply(s)
        self.keys.apply(s)
        folder = self.roms.text()
        s.rom_folders = [folder] + [f for f in s.rom_folders if f != folder]
        s.scan_subfolders = self.subdirs.isChecked()
        s.first_run_done = True
        s.save()
        self.finished.emit()
        self.close_overlay()
