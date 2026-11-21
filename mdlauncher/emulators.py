"""Perfis de emulador (argumentos de tela cheia) e execução de jogos com contagem de tempo."""
from __future__ import annotations

import os
import shlex
import subprocess
import sys
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path

from .storage import Game, Settings


@dataclass
class Profile:
    key: str
    label: str
    fullscreen: str
    template: str
    note: str = ""


# Argumentos pesquisados na documentação/fóruns de cada emulador.
PROFILES = [
    Profile("retroarch", "RetroArch", "-f",
            '-L "cores\\genesis_plus_gx_libretro.dll" {fullscreen} "{rom}"',
            "Troque o core no modelo se usar PicoDrive ou BlastEm (ex.: picodrive_libretro.dll)."),
    Profile("fusion", "Kega Fusion", "-fullscreen", '-gen -auto {fullscreen} "{rom}"',
            "Em tela cheia, ESC fecha o emulador."),
    Profile("blastem", "BlastEm", "-f", '{fullscreen} "{rom}"',
            "-f ALTERNA o modo: se o blastem.cfg já estiver em fullscreen, ele abre em janela."),
    Profile("ares", "ares", "--fullscreen", '--system "Mega Drive" {fullscreen} "{rom}"'),
    Profile("mednafen", "Mednafen", "-video.fs 1", '{fullscreen} "{rom}"'),
    Profile("gens", "Gens/GS", "--fs --quickexit", '{fullscreen} "{rom}"',
            "--quickexit faz o ESC fechar o emulador. O Gens 2.x antigo pode ignorar esses argumentos."),
    Profile("dgen", "DGen", "-f", '{fullscreen} "{rom}"'),
    Profile("exodus", "Exodus", "", '"{rom}"', "Exodus não tem argumento de tela cheia."),
]


def detect_profile(exe_path: str) -> Profile | None:
    stem = Path(exe_path).stem.lower()
    for p in PROFILES:
        if p.key in stem or (p.key == "fusion" and "kega" in stem):
            return p
    return None


def build_command(game: Game, settings: Settings, fullscreen: bool, rom_override: str = "") -> tuple[list[str] | str, str]:
    emu = game.emulator_override or settings.emulator_path
    if not emu:
        raise RuntimeError("Nenhum emulador configurado. Abra Configurações e escolha o .exe do emulador.")
    if not Path(emu).exists():
        raise RuntimeError(f"Emulador não encontrado:\n{emu}")
    tpl = game.template_override or settings.launch_template or '"{rom}"'
    rom = rom_override or game.rom_path
    fs = settings.fullscreen_args if fullscreen else ""
    if "{rom}" not in tpl:
        tpl = tpl + ' "{rom}"'
    args = tpl.replace("{fullscreen}", fs).replace("{rom}", rom)
    args = " ".join(args.split())  # remove espaços duplos deixados pelo {fullscreen} vazio
    cwd = str(Path(emu).parent)
    if sys.platform.startswith("win"):
        return f'"{emu}" {args}', cwd
    return [emu] + shlex.split(args), cwd


def prepare_rom(game: Game, settings: Settings) -> str:
    """Extrai a ROM do .zip para uma pasta temporária, se o usuário pediu isso."""
    if not (settings.extract_zip and game.rom_path.lower().endswith(".zip") and game.rom_entry):
        return ""
    out = Path(tempfile.gettempdir()) / "MDLauncher"
    out.mkdir(exist_ok=True)
    target = out / Path(game.rom_entry).name
    with zipfile.ZipFile(game.rom_path) as zf:
        with zf.open(game.rom_entry) as src, open(target, "wb") as dst:
            dst.write(src.read())
    return str(target)


def spawn(cmd, cwd: str) -> subprocess.Popen:
    return subprocess.Popen(cmd, cwd=cwd)


def open_emulator(settings: Settings) -> None:
    emu = settings.emulator_path
    if not emu or not Path(emu).exists():
        raise RuntimeError("Nenhum emulador configurado.")
    subprocess.Popen([emu], cwd=str(Path(emu).parent))


def open_in_explorer(path: str) -> None:
    p = Path(path)
    if sys.platform.startswith("win"):
        if p.is_file():
            subprocess.Popen(f'explorer /select,"{p}"')
        else:
            os.startfile(str(p))  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(p if p.is_dir() else p.parent)])
    else:
        subprocess.Popen(["xdg-open", str(p if p.is_dir() else p.parent)])
