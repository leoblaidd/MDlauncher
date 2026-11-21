"""Modal de edição: dados do jogo, ROM/emulador e escolha manual de capa/hero por fonte."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QIcon, QImage, QPixmap
from PySide6.QtWidgets import (QComboBox, QFileDialog, QFormLayout, QGridLayout, QHBoxLayout, QLabel,
                               QLineEdit, QListView, QListWidget, QListWidgetItem, QPushButton,
                               QScrollArea, QSpinBox, QVBoxLayout, QWidget)

from .. import metadata as md
from ..storage import Game, Settings, cache_dir
from . import theme
from .common import Overlay, cover_crop, load_image, placeholder, rounded, run_async
from .forms import PathField, header, hint, section

ROM_FILTER = "ROMs de Mega Drive (*.md *.gen *.smd *.bin *.68k *.sgd *.mdx *.zip);;Todos (*.*)"
IMG_FILTER = "Imagens (*.png *.jpg *.jpeg *.webp)"


class Preview(QLabel):
    def __init__(self, w, h, kind):
        super().__init__()
        self.w, self.h, self.kind = w, h, kind
        self.setFixedSize(w, h)
        self.setStyleSheet("background: #0f0f13; border: 1px solid #2a2a32; border-radius: 8px;")

    def show_image(self, img: QImage | None, name: str = ""):
        dpr = self.devicePixelRatioF()
        if img is not None and not img.isNull():
            pm = rounded(cover_crop(img, self.w, self.h, dpr), 8)
        elif self.kind == "cover":
            pm = rounded(placeholder(name, self.w, self.h, dpr), 8)
        else:
            self.setPixmap(QPixmap())
            self.setText("sem hero")
            self.setAlignment(Qt.AlignCenter)
            return
        self.setPixmap(pm)


class EditModal(Overlay):
    saved = Signal(object)
    removed = Signal(object)

    def __init__(self, parent, game: Game, settings: Settings, is_new: bool = False):
        super().__init__(parent, card_size=(1060, 720))
        self.game, self.settings = game, settings
        self.sel_cover: md.Art | str | None = None   # Art (url) ou caminho local
        self.sel_hero: md.Art | str | None = None
        self.cands: list[md.Candidate] = []
        self._search_token = 0
        self._confirm_remove = False

        root = QVBoxLayout(self.card)
        root.setContentsMargins(26, 22, 26, 20)
        root.setSpacing(14)
        root.addWidget(header("Adicionar jogo" if is_new else "Editar jogo", self.close_overlay,
                              Path(game.rom_path).name))

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        body = QWidget()
        scroll.setWidget(body)
        grid = QGridLayout(body)
        grid.setContentsMargins(0, 0, 8, 0)
        grid.setHorizontalSpacing(28)
        grid.setColumnStretch(1, 1)
        root.addWidget(scroll, 1)

        # ---------------- coluna esquerda: dados
        left = QVBoxLayout()
        left.setSpacing(8)
        left.addWidget(section("Informações"))
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignLeft)
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(9)
        self.f_name = QLineEdit(game.name)
        self.f_date = QLineEdit(game.release_date)
        self.f_date.setPlaceholderText("AAAA-MM-DD")
        self.f_multi = QComboBox()
        self.f_multi.addItems(["Desconhecido", "Sim", "Não"])
        self.f_multi.setCurrentIndex({None: 0, True: 1, False: 2}.get(game.multiplayer, 0))
        self.f_players = QLineEdit(game.players)
        self.f_players.setPlaceholderText("ex.: 1-2")
        self.f_dev = QLineEdit(game.developer)
        form.addRow("Nome", self.f_name)
        form.addRow("Lançamento", self.f_date)
        form.addRow("Multiplayer", self.f_multi)
        form.addRow("Jogadores", self.f_players)
        form.addRow("Desenvolvedora", self.f_dev)
        hrs = QHBoxLayout()
        self.f_h = QSpinBox()
        self.f_h.setRange(0, 99999)
        self.f_h.setSuffix(" h")
        self.f_m = QSpinBox()
        self.f_m.setRange(0, 59)
        self.f_m.setSuffix(" min")
        self.f_h.setValue(game.playtime // 3600)
        self.f_m.setValue((game.playtime % 3600) // 60)
        for sp in (self.f_h, self.f_m):
            sp.setMinimumHeight(36)
            sp.setStyleSheet("QSpinBox { padding: 4px 10px; } QSpinBox::up-button, QSpinBox::down-button { width: 0px; border: none; }")
        hrs.addWidget(self.f_h)
        hrs.addWidget(self.f_m)
        form.addRow("Tempo jogado", hrs)
        left.addLayout(form)

        left.addWidget(section("Arquivos"))
        form2 = QFormLayout()
        form2.setHorizontalSpacing(12)
        form2.setVerticalSpacing(9)
        self.f_rom = PathField("file", ROM_FILTER)
        self.f_rom.setText(game.rom_path)
        self.f_emu = PathField("file", "Executável (*.exe);;Todos (*.*)", "Padrão das configurações")
        self.f_emu.setText(game.emulator_override)
        self.f_tpl = QLineEdit(game.template_override)
        self.f_tpl.setPlaceholderText(settings.launch_template or '"{rom}"')
        form2.addRow("ROM / ZIP", self.f_rom)
        form2.addRow("Emulador", self.f_emu)
        form2.addRow("Argumentos", self.f_tpl)
        left.addLayout(form2)
        left.addWidget(hint("Deixe <b>Emulador</b> e <b>Argumentos</b> vazios para usar o padrão. "
                            "Use <code>{rom}</code> e <code>{fullscreen}</code> no modelo."))
        left.addStretch(1)
        lw = QWidget()
        lw.setLayout(left)
        lw.setFixedWidth(390)
        grid.addWidget(lw, 0, 0)

        # ---------------- coluna direita: artes
        right = QVBoxLayout()
        right.setSpacing(10)
        right.addWidget(section("Capa e hero"))
        prev = QHBoxLayout()
        prev.setSpacing(14)
        cv = QVBoxLayout()
        self.pv_cover = Preview(118, 177, "cover")
        b_cov_local = QPushButton("Arquivo local…")
        b_cov_local.clicked.connect(lambda: self._local("cover"))
        cv.addWidget(self.pv_cover)
        cv.addWidget(b_cov_local)
        hv = QVBoxLayout()
        self.pv_hero = Preview(400, 129, "hero")
        b_hero_local = QPushButton("Arquivo local…")
        b_hero_local.clicked.connect(lambda: self._local("hero"))
        b_hero_clear = QPushButton("Remover hero")
        b_hero_clear.setObjectName("ghost")
        b_hero_clear.clicked.connect(self._clear_hero)
        hb = QHBoxLayout()
        hb.addWidget(b_hero_local)
        hb.addWidget(b_hero_clear)
        hb.addStretch(1)
        hv.addWidget(self.pv_hero)
        hv.addLayout(hb)
        hv.addStretch(1)
        prev.addLayout(cv)
        prev.addLayout(hv, 1)
        right.addLayout(prev)

        right.addWidget(section("Buscar em"))
        srow = QHBoxLayout()
        self.src = QComboBox()
        self.sources = self._sources()
        for s in self.sources:
            self.src.addItem(s.NAME + ("" if s.enabled else " (sem chave)"))
        self.q = QLineEdit(game.name)
        self.q.setPlaceholderText("Nome do jogo")
        self.q.returnPressed.connect(self.search)
        b_search = QPushButton("  Buscar")
        b_search.setIcon(theme.icon("search", theme.DARK_TEXT))
        b_search.setObjectName("primary")
        b_search.clicked.connect(self.search)
        srow.addWidget(self.src)
        srow.addWidget(self.q, 1)
        srow.addWidget(b_search)
        right.addLayout(srow)

        crow = QHBoxLayout()
        self.cand = QComboBox()
        self.cand.setPlaceholderText("Resultados aparecem aqui")
        self.cand.currentIndexChanged.connect(self._cand_selected)
        self.b_apply = QPushButton("Usar data e multiplayer")
        self.b_apply.setToolTip("Copia data de lançamento, multiplayer, jogadores e desenvolvedora deste resultado")
        self.b_apply.clicked.connect(self._apply_info)
        self.b_apply.setEnabled(False)
        crow.addWidget(self.cand, 1)
        crow.addWidget(self.b_apply)
        right.addLayout(crow)

        self.status = QLabel("")
        self.status.setStyleSheet(f"color: {theme.MUTED}; font-size: 12px;")
        right.addWidget(self.status)

        right.addWidget(QLabel("Capas"))
        self.l_cov = self._art_list(QSize(92, 138), 172)
        self.l_cov.itemClicked.connect(lambda it: self._pick(it, "cover"))
        right.addWidget(self.l_cov)
        right.addWidget(QLabel("Heroes"))
        self.l_hero = self._art_list(QSize(240, 78), 112)
        self.l_hero.itemClicked.connect(lambda it: self._pick(it, "hero"))
        right.addWidget(self.l_hero)
        rw = QWidget()
        rw.setLayout(right)
        grid.addWidget(rw, 0, 1)

        # ---------------- rodapé
        foot = QHBoxLayout()
        self.b_remove = QPushButton("  Remover da biblioteca")
        self.b_remove.setObjectName("danger")
        self.b_remove.setIcon(theme.icon("trash", theme.SILVER))
        self.b_remove.clicked.connect(self._remove)
        self.b_remove.setVisible(not is_new)
        b_cancel = QPushButton("Cancelar")
        b_cancel.clicked.connect(self.close_overlay)
        self.b_save = QPushButton("Salvar")
        self.b_save.setObjectName("primary")
        self.b_save.setFixedWidth(130)
        self.b_save.clicked.connect(self.save)
        foot.addWidget(self.b_remove)
        foot.addStretch(1)
        foot.addWidget(b_cancel)
        foot.addWidget(self.b_save)
        root.addLayout(foot)

        self.pv_cover.show_image(load_image(game.cover_path), game.name)
        self.pv_hero.show_image(load_image(game.hero_path))
        # pré-seleciona a primeira fonte com chave
        for i, s in enumerate(self.sources):
            if s.enabled:
                self.src.setCurrentIndex(i)
                break

    # ------------------------------------------------------------------ fontes
    def _sources(self):
        return [md.SteamGridDB(self.settings.sgdb_key),
                md.IGDB(self.settings.igdb_client_id, self.settings.igdb_client_secret),
                md.Libretro()]

    def _art_list(self, size: QSize, height: int) -> QListWidget:
        l = QListWidget()
        l.setViewMode(QListView.IconMode)
        l.setFlow(QListView.LeftToRight)
        l.setWrapping(False)
        l.setIconSize(size)
        l.setFixedHeight(height)
        l.setMovement(QListView.Static)
        l.setSpacing(4)
        l.setHorizontalScrollMode(QListView.ScrollPerPixel)
        return l

    def search(self):
        src = self.sources[self.src.currentIndex()]
        if not src.enabled:
            self.status.setText(f"Adicione a chave do {src.NAME} em Configurações para buscar aqui.")
            return
        term = self.q.text().strip() or self.game.name
        self._search_token += 1
        tok = self._search_token
        self.status.setText(f"Buscando “{term}” no {src.NAME}…")
        self.cand.blockSignals(True)
        self.cand.clear()
        self.cand.blockSignals(False)
        self.l_cov.clear()
        self.l_hero.clear()

        if isinstance(src, md.Libretro):
            stem = Path(self.game.rom_entry or self.game.rom_path).stem
            fn = lambda: [md.Candidate(src.NAME, stem, term)]  # noqa: E731
        else:
            fn = lambda: src.search(term)  # noqa: E731

        def done(res):
            if tok != self._search_token:
                return
            self.cands = res or []
            if not self.cands:
                self.status.setText("Nada encontrado. Tente outro nome (ex.: sem subtítulo).")
                return
            self.status.setText(f"{len(self.cands)} resultado(s) no {src.NAME}.")
            self.cand.blockSignals(True)
            for c in self.cands:
                self.cand.addItem(c.label())
            self.cand.blockSignals(False)
            best = md.best_match(self.cands, term)
            self.cand.setCurrentIndex(self.cands.index(best) if best in self.cands else 0)
            self._cand_selected(self.cand.currentIndex())

        run_async(fn, done, lambda e: self.status.setText(f"Erro: {e}"))

    def _cand_selected(self, i: int):
        if i < 0 or i >= len(self.cands):
            return
        c = self.cands[i]
        src = self.sources[self.src.currentIndex()]
        self.b_apply.setEnabled(bool(c.release_date or c.multiplayer is not None or c.developer))
        self._search_token += 1
        tok = self._search_token
        self.l_cov.clear()
        self.l_hero.clear()
        self.status.setText(f"Carregando imagens de “{c.name}”…")

        def fetch():
            if isinstance(src, md.SteamGridDB):
                return src.covers(c.id), src.heroes(c.id)
            if isinstance(src, md.IGDB):
                return src.covers(c), src.heroes(c)
            arts = src.arts(str(c.id), c.name)
            return [a for a in arts if a.kind == "cover"], [a for a in arts if a.kind == "hero"]

        def done(res):
            if tok != self._search_token:
                return
            covers, heroes = res
            self.status.setText(f"{len(covers)} capa(s) e {len(heroes)} hero(es). Clique para escolher.")
            self._fill(self.l_cov, covers[:40], tok)
            self._fill(self.l_hero, heroes[:30], tok)

        run_async(fetch, done, lambda e: self.status.setText(f"Erro: {e}"))

    def _fill(self, lst: QListWidget, arts, tok):
        for a in arts:
            it = QListWidgetItem()
            it.setData(Qt.UserRole, a)
            it.setSizeHint(lst.iconSize() + QSize(10, 10))
            it.setToolTip(f"{a.width}×{a.height}" if a.width else a.source)
            lst.addItem(it)

            def load(u=a.thumb):
                return md.fetch_bytes(u)

            def done(data, item=it, l=lst):
                if tok != self._search_token:
                    return
                img = QImage.fromData(data)
                if img.isNull():
                    return
                sz = l.iconSize()
                item.setIcon(QIcon(rounded(cover_crop(img, sz.width(), sz.height(), self.devicePixelRatioF()), 6)))
                item.setData(Qt.UserRole + 1, img)

            run_async(load, done)

    def _pick(self, it: QListWidgetItem, kind: str):
        art = it.data(Qt.UserRole)
        img = it.data(Qt.UserRole + 1)
        if kind == "cover":
            self.sel_cover = art
            self.pv_cover.show_image(img, self.game.name)
        else:
            self.sel_hero = art
            self.pv_hero.show_image(img)

    def _local(self, kind: str):
        p, _ = QFileDialog.getOpenFileName(self, "Escolher imagem", "", IMG_FILTER)
        if not p:
            return
        if kind == "cover":
            self.sel_cover = p
            self.pv_cover.show_image(load_image(p), self.game.name)
        else:
            self.sel_hero = p
            self.pv_hero.show_image(load_image(p))

    def _clear_hero(self):
        self.sel_hero = ""
        self.pv_hero.show_image(None)

    def _apply_info(self):
        i = self.cand.currentIndex()
        if i < 0 or i >= len(self.cands):
            return
        c = self.cands[i]
        if c.release_date:
            self.f_date.setText(c.release_date)
        if c.multiplayer is not None:
            self.f_multi.setCurrentIndex(1 if c.multiplayer else 2)
        if c.players:
            self.f_players.setText(c.players)
        if c.developer:
            self.f_dev.setText(c.developer)
        self.status.setText("Dados aplicados — clique em Salvar para confirmar.")

    def _remove(self):
        if not self._confirm_remove:
            self._confirm_remove = True
            self.b_remove.setText("  Clique de novo para confirmar")
            return
        self.removed.emit(self.game)
        self.close_overlay()

    # ------------------------------------------------------------------ salvar
    def save(self):
        g = self.game
        g.name = self.f_name.text().strip() or g.name
        g.release_date = self.f_date.text().strip()
        g.multiplayer = {0: None, 1: True, 2: False}[self.f_multi.currentIndex()]
        g.players = self.f_players.text().strip()
        g.developer = self.f_dev.text().strip()
        g.playtime = self.f_h.value() * 3600 + self.f_m.value() * 60 + (g.playtime % 60)
        new_rom = self.f_rom.text()
        if new_rom and new_rom != g.rom_path:
            from ..scanner import inspect_file
            g.rom_path = new_rom
            g.rom_entry = inspect_file(Path(new_rom))[1]
        g.emulator_override = self.f_emu.text()
        g.template_override = self.f_tpl.text().strip()

        sel_c, sel_h = self.sel_cover, self.sel_hero
        self.b_save.setEnabled(False)
        self.b_save.setText("Salvando…")

        def apply_art(sel, kind):
            if sel is None:
                return
            if sel == "":
                setattr(g, f"{kind}_path", "")
                setattr(g, f"{kind}_source", "")
                return
            stem = f"{g.id}_{kind}"
            if isinstance(sel, md.Art):
                setattr(g, f"{kind}_path", md.download(sel.url, stem))
                setattr(g, f"{kind}_source", sel.source)
            else:
                import shutil
                dest = cache_dir() / f"{stem}{Path(sel).suffix.lower()}"
                for old in cache_dir().glob(f"{stem}.*"):
                    old.unlink(missing_ok=True)
                shutil.copyfile(sel, dest)
                setattr(g, f"{kind}_path", str(dest))
                setattr(g, f"{kind}_source", "Arquivo local")

        def work():
            apply_art(sel_c, "cover")
            apply_art(sel_h, "hero")
            return g

        def done(_):
            self.saved.emit(g)
            self.close_overlay()

        def err(e):
            self.b_save.setEnabled(True)
            self.b_save.setText("Salvar")
            self.status.setText(f"Não consegui baixar a imagem: {e}")

        run_async(work, done, err)
