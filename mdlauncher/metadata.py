"""Fontes de metadados e artes: SteamGridDB, IGDB (Twitch) e Libretro Thumbnails."""
from __future__ import annotations

import json
import re
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from .storage import Game, cache_dir

UA = "MDLauncher/1.0 (+https://github.com/leoblaidd/MDlauncher)"
TIMEOUT = 20
_ctx = ssl.create_default_context()


class SourceError(Exception):
    pass


def _request(url: str, headers: dict | None = None, data: bytes | None = None, method: str | None = None):
    h = {"User-Agent": UA}
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, data=data, headers=h, method=method)
    return urllib.request.urlopen(req, timeout=TIMEOUT, context=_ctx)


def _json(url: str, headers: dict | None = None, data: bytes | None = None):
    try:
        with _request(url, headers, data, "POST" if data is not None else "GET") as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            raise SourceError("Chave/credencial inválida") from e
        if e.code == 404:
            return None
        raise SourceError(f"HTTP {e.code}") from e
    except urllib.error.URLError as e:
        raise SourceError(f"Sem conexão: {e.reason}") from e


def download(url: str, dest_stem: str) -> str:
    """Baixa uma imagem para o cache e devolve o caminho local."""
    ext = Path(urllib.parse.urlparse(url).path).suffix.lower()
    if ext not in {".png", ".jpg", ".jpeg", ".webp"}:
        ext = ".png"
    dest = cache_dir() / f"{dest_stem}{ext}"
    for old in cache_dir().glob(f"{dest_stem}.*"):
        try:
            old.unlink()
        except OSError:
            pass
    with _request(url) as r:
        data = r.read()
    dest.write_bytes(data)
    return str(dest)


def fetch_bytes(url: str) -> bytes:
    with _request(url) as r:
        return r.read()


@dataclass
class Candidate:
    """Um jogo encontrado numa fonte."""
    source: str
    id: object
    name: str
    release_date: str = ""
    multiplayer: object = None
    players: str = ""
    developer: str = ""
    extra: dict = field(default_factory=dict)

    def label(self) -> str:
        y = f" ({self.release_date[:4]})" if self.release_date else ""
        return f"{self.name}{y}"


@dataclass
class Art:
    url: str
    thumb: str
    kind: str  # "cover" | "hero"
    source: str
    width: int = 0
    height: int = 0


def _ts_to_date(ts) -> str:
    try:
        return datetime.fromtimestamp(int(ts), tz=timezone.utc).strftime("%Y-%m-%d")
    except Exception:
        return ""


# --------------------------------------------------------------------------- SteamGridDB
class SteamGridDB:
    NAME = "SteamGridDB"
    BASE = "https://www.steamgriddb.com/api/v2"

    def __init__(self, key: str):
        self.key = key.strip()

    @property
    def enabled(self) -> bool:
        return bool(self.key)

    def _get(self, path: str):
        d = _json(f"{self.BASE}{path}", {"Authorization": f"Bearer {self.key}"})
        if not d or not d.get("success"):
            return []
        return d.get("data") or []

    def search(self, term: str) -> list[Candidate]:
        out = []
        for it in self._get(f"/search/autocomplete/{urllib.parse.quote(term)}")[:12]:
            out.append(Candidate(self.NAME, it.get("id"), it.get("name", ""),
                                 _ts_to_date(it["release_date"]) if it.get("release_date") else ""))
        return out

    def covers(self, gid) -> list[Art]:
        items = self._get(f"/grids/game/{gid}?dimensions=600x900,342x482,660x930&types=static&nsfw=false")
        return [Art(i["url"], i.get("thumb") or i["url"], "cover", self.NAME, i.get("width", 0), i.get("height", 0))
                for i in items]

    def heroes(self, gid) -> list[Art]:
        items = self._get(f"/heroes/game/{gid}?types=static&nsfw=false")
        return [Art(i["url"], i.get("thumb") or i["url"], "hero", self.NAME, i.get("width", 0), i.get("height", 0))
                for i in items]


# --------------------------------------------------------------------------- IGDB
class IGDB:
    NAME = "IGDB"
    PLATFORM_MD = 29  # Sega Mega Drive/Genesis
    _token_cache: dict = {}

    def __init__(self, client_id: str, client_secret: str):
        self.cid = client_id.strip()
        self.secret = client_secret.strip()

    @property
    def enabled(self) -> bool:
        return bool(self.cid and self.secret)

    def _token(self) -> str:
        c = self._token_cache.get(self.cid)
        if c and c[1] > time.time() + 60:
            return c[0]
        q = urllib.parse.urlencode({"client_id": self.cid, "client_secret": self.secret,
                                    "grant_type": "client_credentials"})
        d = _json(f"https://id.twitch.tv/oauth2/token?{q}", data=b"")
        if not d or "access_token" not in d:
            raise SourceError("Credenciais IGDB inválidas")
        self._token_cache[self.cid] = (d["access_token"], time.time() + int(d.get("expires_in", 3600)))
        return d["access_token"]

    def _query(self, endpoint: str, body: str):
        headers = {"Client-ID": self.cid, "Authorization": f"Bearer {self._token()}", "Accept": "application/json"}
        return _json(f"https://api.igdb.com/v4/{endpoint}", headers, body.encode("utf-8")) or []

    @staticmethod
    def img(image_id: str, size: str) -> str:
        return f"https://images.igdb.com/igdb/image/upload/t_{size}/{image_id}.jpg"

    def search(self, term: str) -> list[Candidate]:
        safe = term.replace('"', "")
        fields = ("fields name,first_release_date,game_modes.name,multiplayer_modes.offlinemax,"
                  "multiplayer_modes.offlinecoopmax,involved_companies.company.name,involved_companies.developer,"
                  "cover.image_id,artworks.image_id,screenshots.image_id;")
        res = self._query("games", f'search "{safe}"; {fields} where platforms = ({self.PLATFORM_MD}); limit 12;')
        if not res:  # tenta sem filtro de plataforma
            res = self._query("games", f'search "{safe}"; {fields} limit 12;')
        out = []
        for g in res:
            modes = [m.get("name", "") for m in g.get("game_modes", []) if isinstance(m, dict)]
            multi = None
            if modes:
                multi = any(k in " ".join(modes).lower() for k in ("multiplayer", "co-operative", "split screen"))
            mx = 0
            for mm in g.get("multiplayer_modes", []) or []:
                if isinstance(mm, dict):
                    mx = max(mx, mm.get("offlinemax") or 0, mm.get("offlinecoopmax") or 0)
            players = f"1-{mx}" if mx > 1 else ("1" if multi is False else "")
            dev = ""
            for ic in g.get("involved_companies", []) or []:
                if isinstance(ic, dict) and ic.get("developer") and isinstance(ic.get("company"), dict):
                    dev = ic["company"].get("name", "")
                    break
            out.append(Candidate(self.NAME, g.get("id"), g.get("name", ""),
                                 _ts_to_date(g["first_release_date"]) if g.get("first_release_date") else "",
                                 multi, players, dev, extra=g))
        return out

    def covers(self, cand: Candidate) -> list[Art]:
        c = cand.extra.get("cover")
        if isinstance(c, dict) and c.get("image_id"):
            return [Art(self.img(c["image_id"], "cover_big_2x"), self.img(c["image_id"], "cover_big"), "cover", self.NAME)]
        return []

    def heroes(self, cand: Candidate) -> list[Art]:
        out = []
        for key in ("artworks", "screenshots"):
            for a in cand.extra.get(key, []) or []:
                if isinstance(a, dict) and a.get("image_id"):
                    out.append(Art(self.img(a["image_id"], "1080p"), self.img(a["image_id"], "screenshot_med"),
                                   "hero", self.NAME))
        return out


# --------------------------------------------------------------------------- Libretro
class Libretro:
    """Thumbnails do projeto libretro — grátis e sem chave. Usa nomes no padrão No-Intro."""
    NAME = "Libretro"
    BASE = "https://thumbnails.libretro.com/Sega%20-%20Mega%20Drive%20-%20Genesis"
    enabled = True

    @staticmethod
    def _safe(name: str) -> str:
        return re.sub(r'[&*/:`<>?\\|"]', "_", name)

    def _exists(self, folder: str, name: str) -> str:
        url = f"{self.BASE}/{folder}/{urllib.parse.quote(self._safe(name))}.png"
        try:
            with _request(url, method="HEAD") as r:
                if r.status == 200:
                    return url
        except Exception:
            pass
        return ""

    def candidates_for(self, stem: str, clean: str) -> list[str]:
        names = [stem]
        base = clean.replace(": ", " - ")
        for reg in ("(USA, Europe)", "(USA)", "(World)", "(Europe)", "(Japan, USA)", "(Brazil)", "(Japan)"):
            names.append(f"{base} {reg}")
        seen, out = set(), []
        for n in names:
            if n not in seen:
                seen.add(n)
                out.append(n)
        return out

    def find(self, stem: str, clean: str, folder: str) -> str:
        for n in self.candidates_for(stem, clean):
            u = self._exists(folder, n)
            if u:
                return u
        return ""

    def arts(self, stem: str, clean: str) -> list[Art]:
        out = []
        c = self.find(stem, clean, "Named_Boxarts")
        if c:
            out.append(Art(c, c, "cover", self.NAME))
        for folder in ("Named_Titles", "Named_Snaps"):
            h = self.find(stem, clean, folder)
            if h:
                out.append(Art(h, h, "hero", self.NAME))
        return out


# --------------------------------------------------------------------------- Pipeline automático
def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def best_match(cands: list[Candidate], name: str) -> Candidate | None:
    if not cands:
        return None
    target = _norm(name)
    for c in cands:
        if _norm(c.name) == target:
            return c
    for c in cands:
        if target and (target in _norm(c.name) or _norm(c.name) in target):
            return c
    return cands[0]


def auto_fetch(game: Game, sgdb: SteamGridDB, igdb: IGDB, log=lambda m: None) -> Game:
    """Preenche capa, hero, data e multiplayer de um jogo, usando as fontes disponíveis em cascata."""
    name = game.name
    stem = Path(game.rom_entry or game.rom_path).stem

    # 1) SteamGridDB — capa e hero
    if sgdb.enabled:
        try:
            m = best_match(sgdb.search(name), name)
            if m:
                game.sgdb_id = int(m.id or 0)
                if m.release_date and not game.release_date:
                    game.release_date = m.release_date
                if not game.cover_path:
                    arts = sgdb.covers(m.id)
                    if arts:
                        game.cover_path = download(arts[0].url, f"{game.id}_cover")
                        game.cover_source = sgdb.NAME
                if not game.hero_path:
                    arts = sgdb.heroes(m.id)
                    if arts:
                        game.hero_path = download(arts[0].url, f"{game.id}_hero")
                        game.hero_source = sgdb.NAME
        except Exception as e:
            log(f"SteamGridDB: {e}")

    # 2) IGDB — data, multiplayer, desenvolvedora e artes que faltarem
    if igdb.enabled:
        try:
            m = best_match(igdb.search(name), name)
            if m:
                game.igdb_id = int(m.id or 0)
                if m.release_date:
                    game.release_date = game.release_date or m.release_date
                if m.multiplayer is not None and game.multiplayer is None:
                    game.multiplayer = m.multiplayer
                if m.players and not game.players:
                    game.players = m.players
                if m.developer and not game.developer:
                    game.developer = m.developer
                if not game.cover_path:
                    arts = igdb.covers(m)
                    if arts:
                        game.cover_path = download(arts[0].url, f"{game.id}_cover")
                        game.cover_source = igdb.NAME
                if not game.hero_path:
                    arts = igdb.heroes(m)
                    if arts:
                        game.hero_path = download(arts[0].url, f"{game.id}_hero")
                        game.hero_source = igdb.NAME
        except Exception as e:
            log(f"IGDB: {e}")

    # 3) Libretro — fallback sem chave
    if not game.cover_path or not game.hero_path:
        try:
            lr = Libretro()
            for a in lr.arts(stem, name):
                if a.kind == "cover" and not game.cover_path:
                    game.cover_path = download(a.url, f"{game.id}_cover")
                    game.cover_source = lr.NAME
                elif a.kind == "hero" and not game.hero_path:
                    game.hero_path = download(a.url, f"{game.id}_hero")
                    game.hero_source = lr.NAME
        except Exception as e:
            log(f"Libretro: {e}")

    game.metadata_done = True
    return game
