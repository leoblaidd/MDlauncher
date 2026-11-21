"""Varredura de pastas: identifica ROMs de Mega Drive (soltas ou dentro de .zip)."""
from __future__ import annotations

import os
import re
import zipfile
from pathlib import Path

from .storage import Game, game_id_for

MD_EXTS = {".md", ".gen", ".smd", ".bin", ".68k", ".sgd", ".mdx"}
ZIP_EXTS = {".zip"}
MAX_ROM = 8 * 1024 * 1024  # o maior cartucho de MD tem ~5 MB; acima disso é outra coisa (ex.: Sega CD)


def _looks_like_md(head: bytes, ext: str, size: int) -> bool:
    if size > MAX_ROM or size < 0x200:
        return False
    if ext == ".smd":  # formato intercalado do Super Magic Drive: sem cabeçalho legível
        return True
    if b"SEGA" in head[0x100:0x110]:
        return True
    # .md/.gen/.68k quase sempre são MD mesmo sem cabeçalho padrão (protótipos, hacks)
    return ext in {".md", ".gen", ".68k", ".sgd", ".mdx"}


def inspect_file(path: Path) -> tuple[bool, str]:
    """Retorna (é_md, entrada_interna)."""
    ext = path.suffix.lower()
    try:
        if ext in ZIP_EXTS:
            with zipfile.ZipFile(path) as zf:
                for info in zf.infolist():
                    iext = os.path.splitext(info.filename)[1].lower()
                    if info.is_dir() or iext not in MD_EXTS:
                        continue
                    with zf.open(info) as fh:
                        head = fh.read(0x200)
                    if _looks_like_md(head, iext, info.file_size):
                        return True, info.filename
            return False, ""
        if ext in MD_EXTS:
            size = path.stat().st_size
            with open(path, "rb") as fh:
                head = fh.read(0x200)
            return _looks_like_md(head, ext, size), ""
    except (OSError, zipfile.BadZipFile):
        pass
    return False, ""


_TAG_RE = re.compile(r"\s*[\(\[][^\)\]]*[\)\]]")


def clean_name(stem: str) -> str:
    """'Sonic The Hedgehog 2 (World) (Rev A) [!]' -> 'Sonic The Hedgehog 2'"""
    name = stem.replace("_", " ")
    name = _TAG_RE.sub("", name).strip()
    name = re.sub(r"\s{2,}", " ", name)
    m = re.match(r"^(.*), (The|A|An|O|Os|A|As)$", name, re.I)
    if m:
        name = f"{m.group(2)} {m.group(1)}"
    name = name.replace(" - ", ": ", 1) if re.search(r" - ", name) and not re.search(r":", name) else name
    return name or stem


def scan_folder(folder: str, recursive: bool = True):
    """Gera objetos Game para cada ROM de MD encontrada."""
    root = Path(folder)
    if not root.is_dir():
        return
    it = root.rglob("*") if recursive else root.glob("*")
    for p in it:
        if not p.is_file():
            continue
        if p.suffix.lower() not in MD_EXTS | ZIP_EXTS:
            continue
        ok, entry = inspect_file(p)
        if not ok:
            continue
        yield Game(id=game_id_for(str(p)), name=clean_name(p.stem), rom_path=str(p), rom_entry=entry)


def game_from_file(path: str) -> Game | None:
    p = Path(path)
    ok, entry = inspect_file(p)
    if not ok and p.suffix.lower() not in MD_EXTS | ZIP_EXTS:
        return None
    return Game(id=game_id_for(str(p)), name=clean_name(p.stem), rom_path=str(p), rom_entry=entry)
