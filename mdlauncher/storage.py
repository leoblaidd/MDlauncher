"""Persistência de configurações e da biblioteca de jogos (JSON em %APPDATA%\\MDLauncher)."""
from __future__ import annotations

import hashlib
import json
import os
import sys
import threading
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path


def data_dir() -> Path:
    if sys.platform.startswith("win"):
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    override = os.environ.get("MDLAUNCHER_HOME")
    d = Path(override) if override else base / "MDLauncher"
    d.mkdir(parents=True, exist_ok=True)
    (d / "cache").mkdir(exist_ok=True)
    return d


def cache_dir() -> Path:
    return data_dir() / "cache"


def _atomic_write(path: Path, data: dict) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


@dataclass
class Settings:
    emulator_path: str = ""
    launch_template: str = '{fullscreen} "{rom}"'
    fullscreen_args: str = ""
    rom_folders: list = field(default_factory=list)
    sgdb_key: str = ""
    igdb_client_id: str = ""
    igdb_client_secret: str = ""
    cover_size: int = 180
    extract_zip: bool = False
    fullscreen_default: bool = False
    minimize_on_play: bool = True
    scan_subfolders: bool = True
    first_run_done: bool = False
    window_geometry: str = ""

    @classmethod
    def load(cls) -> "Settings":
        p = data_dir() / "settings.json"
        s = cls()
        if p.exists():
            try:
                raw = json.loads(p.read_text(encoding="utf-8"))
                for k, v in raw.items():
                    if hasattr(s, k):
                        setattr(s, k, v)
            except Exception:
                pass
        return s

    def save(self) -> None:
        _atomic_write(data_dir() / "settings.json", asdict(self))


def game_id_for(path: str) -> str:
    return hashlib.sha1(os.path.normcase(os.path.abspath(path)).encode("utf-8")).hexdigest()[:16]


@dataclass
class Game:
    id: str
    name: str
    rom_path: str
    rom_entry: str = ""          # arquivo interno, quando a ROM está dentro de um .zip
    release_date: str = ""       # AAAA-MM-DD (ou só AAAA)
    multiplayer: object = None   # True / False / None (desconhecido)
    players: str = ""
    developer: str = ""
    cover_path: str = ""
    hero_path: str = ""
    cover_source: str = ""
    hero_source: str = ""
    sgdb_id: int = 0
    igdb_id: int = 0
    emulator_override: str = ""
    template_override: str = ""
    fullscreen: object = None    # None = usa o padrão das configurações
    playtime: int = 0            # segundos
    last_played: float = 0.0
    added: float = field(default_factory=time.time)
    metadata_done: bool = False

    @property
    def year(self) -> str:
        return (self.release_date or "")[:4]


class Library:
    def __init__(self) -> None:
        self.path = data_dir() / "library.json"
        self.games: dict[str, Game] = {}
        self._lock = threading.RLock()
        self.load()

    def load(self) -> None:
        if not self.path.exists():
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            return
        fields = Game.__dataclass_fields__.keys()
        for item in raw.get("games", []):
            try:
                g = Game(**{k: v for k, v in item.items() if k in fields})
                self.games[g.id] = g
            except TypeError:
                continue

    def save(self) -> None:
        with self._lock:
            data = {"version": 1, "games": [asdict(g) for g in self.games.values()]}
            _atomic_write(self.path, data)

    def add(self, game: Game) -> None:
        with self._lock:
            self.games[game.id] = game

    def remove(self, gid: str) -> None:
        with self._lock:
            g = self.games.pop(gid, None)
        if g:
            for p in (g.cover_path, g.hero_path):
                try:
                    if p and Path(p).is_relative_to(cache_dir()):
                        Path(p).unlink(missing_ok=True)
                except Exception:
                    pass

    def sorted(self) -> list[Game]:
        with self._lock:
            return sorted(self.games.values(), key=lambda g: g.name.lower())
