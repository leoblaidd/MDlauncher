"""Janela principal: fundo xadrez, grid de capas, dock, título e orquestração."""
from __future__ import annotations

import threading
import time
from pathlib import Path

from PySide6.QtCore import QByteArray, QObject, QPoint, Qt, QTimer, Signal
from PySide6.QtGui import QAction, QCursor, QPainter
from PySide6.QtWidgets import QFileDialog, QHBoxLayout, QLabel, QMenu, QVBoxLayout, QWidget

from .. import emulators, metadata as md
from ..scanner import game_from_file, scan_folder
from ..storage import Game, Library, Settings, data_dir
from . import theme
from .common import Overlay, paint_background, run_async
from .edit_modal import ROM_FILTER, EditModal
from .game_modal import GameModal
from .settings_modal import SettingsModal, WizardModal
from .widgets import Dock, GameGrid, WindowControls

EDGE = 6


class RunnerSignals(QObject):
    finished = Signal(str, int)
    error = Signal(str, str)


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MD Launcher")
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)
        self.setMouseTracking(True)
        self.setMinimumSize(760, 560)
        self.settings = Settings.load()
        self.library = Library()
        self.running: dict[str, float] = {}
        self.game_modal: GameModal | None = None
        self.fetch_total = 0
        self.fetch_done = 0
        self.runner = RunnerSignals()
        self.runner.finished.connect(self._game_finished)
        self.runner.error.connect(lambda gid, e: self.toast(e))

        root = QVBoxLayout(self)
        root.setContentsMargins(EDGE, EDGE, EDGE, EDGE)
        root.setSpacing(0)

        # barra "invisível": botões à esquerda, nome à direita
        top = QWidget()
        top.setFixedHeight(54)
        top.setAttribute(Qt.WA_TransparentForMouseEvents, False)
        tl = QHBoxLayout(top)
        tl.setContentsMargins(14, 0, 22, 0)
        self.controls = WindowControls(self)
        tl.addWidget(self.controls)
        tl.addStretch(1)
        self.status = QLabel("")
        self.status.setStyleSheet(f"color: {theme.MUTED}; font-size: 12px; padding-right: 16px;")
        tl.addWidget(self.status)
        self.brand = QLabel(f"<span style='color:{theme.RED}'>MD</span>&nbsp;Launcher")
        self.brand.setTextFormat(Qt.RichText)
        self.brand.setStyleSheet("font-size: 21px; font-weight: 900; font-style: italic; letter-spacing: 0.5px;")
        tl.addWidget(self.brand)
        root.addWidget(top)
        self.top = top

        self.grid = GameGrid()
        self.grid.game_clicked.connect(self.open_game)
        self.grid.game_context.connect(self._context_menu)
        root.addWidget(self.grid, 1)

        self.dock = Dock(self)
        self.dock.slider.setValue(self.settings.cover_size)
        self.grid.set_cover_width(self.settings.cover_size)
        self.dock.size_changed.connect(self._cover_size)
        self.dock.add_game.connect(self.add_game)
        self.dock.open_emulator.connect(self.open_emulator)
        self.dock.open_roms.connect(self.open_roms)
        self.dock.open_settings.connect(self.open_settings)

        self._save_timer = QTimer(self, singleShot=True, interval=600)
        self._save_timer.timeout.connect(self.library.save)
        self._size_timer = QTimer(self, singleShot=True, interval=400)
        self._size_timer.timeout.connect(self.settings.save)

        self.refresh_grid()
        if self.settings.window_geometry:
            self.restoreGeometry(QByteArray.fromBase64(self.settings.window_geometry.encode()))
        else:
            self.resize(1280, 800)

    # ------------------------------------------------------------------ inicialização
    def start(self):
        if not self.settings.first_run_done:
            QTimer.singleShot(250, self.show_wizard)
        else:
            self.rescan(silent=True)

    def show_wizard(self):
        w = WizardModal(self, self.settings)
        w.finished.connect(lambda: self.rescan(silent=False))
        w.open()

    # ------------------------------------------------------------------ biblioteca
    def refresh_grid(self):
        self.grid.model_.set_games(self.library.sorted())
        if not self.library.games:
            self.grid.empty_text = ("Nenhum jogo ainda.\nUse o botão ⚙ do dock para configurar o emulador e a pasta de ROMs,\n"
                                    "ou + para adicionar um jogo manualmente.")
        else:
            self.grid.empty_text = ""
        self.grid.viewport().update()

    def schedule_save(self):
        self._save_timer.start()

    def rescan(self, silent: bool = False):
        folders = list(self.settings.rom_folders)
        rec = self.settings.scan_subfolders
        if not folders:
            return
        self.status.setText("Procurando ROMs…")

        def work():
            found = []
            for f in folders:
                found.extend(scan_folder(f, rec))
            return found

        def done(found):
            new = []
            for g in found:
                if g.id not in self.library.games:
                    g.fullscreen = None
                    self.library.add(g)
                    new.append(g)
            self.library.save()
            self.refresh_grid()
            pending = [g for g in self.library.games.values() if not g.metadata_done]
            self.status.setText(f"{len(new)} jogo(s) novo(s)" if new else "")
            if pending:
                self.fetch_metadata(pending)
            elif not silent:
                QTimer.singleShot(2500, lambda: self.status.setText(""))

        run_async(work, done, lambda e: self.status.setText(f"Erro ao escanear: {e}"))

    def fetch_metadata(self, games: list[Game], force: bool = False):
        s = self.settings
        sgdb = md.SteamGridDB(s.sgdb_key)
        igdb = md.IGDB(s.igdb_client_id, s.igdb_client_secret)
        self.fetch_total += len(games)
        self._update_fetch_status()
        for g in games:
            if force:
                g.cover_path = g.hero_path = ""
                g.cover_source = g.hero_source = ""
                g.release_date = ""
                g.multiplayer = None
                g.players = g.developer = ""

            def work(game=g):
                return md.auto_fetch(game, sgdb, igdb)

            def done(game):
                self.fetch_done += 1
                self.grid.delegate.invalidate(game)
                self.grid.model_.refresh(game.id)
                if self.game_modal and self.game_modal.game.id == game.id:
                    self.game_modal.refresh()
                self._update_fetch_status()
                self.schedule_save()

            def err(e):
                self.fetch_done += 1
                self._update_fetch_status()

            run_async(work, done, err)

    def _update_fetch_status(self):
        if self.fetch_done >= self.fetch_total:
            self.fetch_total = self.fetch_done = 0
            self.status.setText("Capas atualizadas ✓")
            QTimer.singleShot(3000, lambda: self.status.setText("") if not self.fetch_total else None)
        else:
            self.status.setText(f"Baixando capas e informações… {self.fetch_done}/{self.fetch_total}")

    # ------------------------------------------------------------------ ações do dock
    def add_game(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Adicionar jogo(s)", self.settings.rom_folders[0]
                                                if self.settings.rom_folders else "", ROM_FILTER)
        added = []
        for f in files:
            g = game_from_file(f)
            if not g:
                continue
            if g.id in self.library.games:
                added.append(self.library.games[g.id])
                continue
            self.library.add(g)
            added.append(g)
        if not added:
            return
        self.library.save()
        self.refresh_grid()
        self.fetch_metadata([g for g in added if not g.metadata_done])
        if len(added) == 1:
            self.open_edit(added[0], is_new=True)

    def open_emulator(self):
        try:
            emulators.open_emulator(self.settings)
        except Exception as e:  # noqa: BLE001
            self.toast(str(e))

    def open_roms(self):
        if not self.settings.rom_folders:
            self.toast("Nenhuma pasta de ROMs configurada.")
            return
        emulators.open_in_explorer(self.settings.rom_folders[0])

    def open_settings(self):
        m = SettingsModal(self, self.settings)
        m.saved.connect(lambda changed: self.rescan() if changed else None)
        m.rescan.connect(lambda: self.rescan())
        m.refetch.connect(lambda force: self.fetch_metadata(
            list(self.library.games.values()) if force else
            [g for g in self.library.games.values() if not g.cover_path or not g.hero_path], force))
        m.open_data.connect(lambda: emulators.open_in_explorer(str(data_dir())))
        m.open()

    def _cover_size(self, v: int):
        self.settings.cover_size = v
        self.grid.set_cover_width(v)
        self._size_timer.start()

    # ------------------------------------------------------------------ jogo
    def fullscreen_for(self, g: Game) -> bool:
        return self.settings.fullscreen_default if g.fullscreen is None else bool(g.fullscreen)

    def open_game(self, g: Game):
        if not g:
            return
        m = GameModal(self, g, self.fullscreen_for(g), g.id in self.running)
        m.play_requested.connect(self.play)
        m.edit_requested.connect(lambda game: self.open_edit(game))
        m.fullscreen_changed.connect(self._set_fs)
        m.closed.connect(lambda: setattr(self, "game_modal", None))
        self.game_modal = m
        m.open()

    def _set_fs(self, g: Game, on: bool):
        g.fullscreen = on
        self.schedule_save()

    def open_edit(self, g: Game, is_new: bool = False):
        m = EditModal(self, g, self.settings, is_new)
        m.saved.connect(self._edited)
        m.removed.connect(self._removed)
        m.open()

    def _edited(self, g: Game):
        self.library.save()
        self.grid.delegate.invalidate(g)
        self.refresh_grid()
        if self.game_modal and self.game_modal.game.id == g.id:
            self.game_modal.refresh()

    def _removed(self, g: Game):
        self.library.remove(g.id)
        self.library.save()
        if self.game_modal and self.game_modal.game.id == g.id:
            self.game_modal.close_overlay()
        self.refresh_grid()

    def play(self, g: Game, fullscreen: bool):
        if g.id in self.running:
            return
        try:
            rom = emulators.prepare_rom(g, self.settings)
            cmd, cwd = emulators.build_command(g, self.settings, fullscreen, rom)
            proc = emulators.spawn(cmd, cwd)
        except Exception as e:  # noqa: BLE001
            self.toast(str(e))
            return
        start = time.monotonic()
        self.running[g.id] = start
        g.last_played = time.time()
        self.schedule_save()
        if self.game_modal and self.game_modal.game.id == g.id:
            self.game_modal.set_running(True)

        def wait():
            try:
                proc.wait()
            finally:
                self.runner.finished.emit(g.id, int(time.monotonic() - start))

        threading.Thread(target=wait, daemon=True).start()
        if self.settings.minimize_on_play:
            QTimer.singleShot(400, self.showMinimized)

    def _game_finished(self, gid: str, seconds: int):
        self.running.pop(gid, None)
        g = self.library.games.get(gid)
        if g:
            g.playtime += max(0, seconds)
            self.library.save()
            self.grid.model_.refresh(gid)
            if self.game_modal and self.game_modal.game.id == gid:
                self.game_modal.set_running(False)
                self.game_modal.refresh()
        if self.isMinimized() and not self.running:
            self.showNormal()
            self.activateWindow()

    def _context_menu(self, g: Game, pos: QPoint):
        menu = QMenu(self)
        a_play = QAction(theme.icon("play"), "Jogar", menu)
        a_play.triggered.connect(lambda: self.play(g, self.fullscreen_for(g)))
        a_open = QAction("Detalhes", menu)
        a_open.triggered.connect(lambda: self.open_game(g))
        a_edit = QAction(theme.icon("edit"), "Editar…", menu)
        a_edit.triggered.connect(lambda: self.open_edit(g))
        a_loc = QAction(theme.icon("folder"), "Mostrar ROM no Explorer", menu)
        a_loc.triggered.connect(lambda: emulators.open_in_explorer(g.rom_path))
        a_ref = QAction(theme.icon("refresh"), "Buscar artes de novo", menu)
        a_ref.triggered.connect(lambda: self.fetch_metadata([g], True))
        a_rm = QAction(theme.icon("trash"), "Remover da biblioteca", menu)
        a_rm.triggered.connect(lambda: self._removed(g))
        for a in (a_play, a_open, a_edit, a_loc, a_ref):
            menu.addAction(a)
        menu.addSeparator()
        menu.addAction(a_rm)
        menu.exec(pos)

    # ------------------------------------------------------------------ aviso rápido
    def toast(self, text: str):
        lbl = QLabel(text, self)
        lbl.setWordWrap(True)
        lbl.setMaximumWidth(520)
        lbl.setStyleSheet("background: #2a1210; border: 1px solid #e2231a; border-radius: 10px; padding: 12px 16px;"
                          " font-size: 13px;")
        lbl.adjustSize()
        lbl.move((self.width() - lbl.width()) // 2, 70)
        lbl.show()
        lbl.raise_()
        QTimer.singleShot(4500, lbl.deleteLater)

    # ------------------------------------------------------------------ janela sem borda
    def paintEvent(self, _):
        p = QPainter(self)
        paint_background(p, self.rect())

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self.dock.adjustSize()
        dw = self.dock.sizeHint().width()
        self.dock.setGeometry((self.width() - dw) // 2, self.height() - self.dock.height() - 14, dw, self.dock.height())
        self.dock.raise_()
        for ch in self.children():
            if isinstance(ch, Overlay) and ch.isVisible():
                ch.raise_()

    def changeEvent(self, e):
        if e.type() == e.Type.WindowStateChange:
            self.controls.sync()
            m = 0 if self.isMaximized() else EDGE
            self.layout().setContentsMargins(m, m, m, m)
        super().changeEvent(e)

    def _edges(self, pos):
        if self.isMaximized():
            return Qt.Edges()
        r = self.rect()
        e = Qt.Edges()
        if pos.x() <= EDGE:
            e |= Qt.LeftEdge
        if pos.x() >= r.width() - EDGE:
            e |= Qt.RightEdge
        if pos.y() <= EDGE:
            e |= Qt.TopEdge
        if pos.y() >= r.height() - EDGE:
            e |= Qt.BottomEdge
        return e

    def mousePressEvent(self, ev):
        if ev.button() == Qt.LeftButton:
            pos = ev.position().toPoint()
            edges = self._edges(pos)
            if edges:
                self.windowHandle().startSystemResize(edges)
                return
            if pos.y() <= self.top.geometry().bottom():
                self.windowHandle().startSystemMove()
                return
        super().mousePressEvent(ev)

    def mouseDoubleClickEvent(self, ev):
        if ev.position().toPoint().y() <= self.top.geometry().bottom():
            self.controls.toggle_max()

    def mouseMoveEvent(self, ev):
        e = self._edges(ev.position().toPoint())
        if e in (Qt.LeftEdge | Qt.TopEdge, Qt.RightEdge | Qt.BottomEdge):
            self.setCursor(Qt.SizeFDiagCursor)
        elif e in (Qt.RightEdge | Qt.TopEdge, Qt.LeftEdge | Qt.BottomEdge):
            self.setCursor(Qt.SizeBDiagCursor)
        elif e & (Qt.LeftEdge | Qt.RightEdge):
            self.setCursor(Qt.SizeHorCursor)
        elif e & (Qt.TopEdge | Qt.BottomEdge):
            self.setCursor(Qt.SizeVerCursor)
        else:
            self.unsetCursor()
        super().mouseMoveEvent(ev)

    def closeEvent(self, e):
        self.settings.window_geometry = bytes(self.saveGeometry().toBase64()).decode()
        self.settings.save()
        self.library.save()
        super().closeEvent(e)
