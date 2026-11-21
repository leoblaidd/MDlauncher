//! Execução de jogos: monta a linha de comando a partir do modelo e abre o emulador.

use crate::storage::{Game, Settings};
use std::path::{Path, PathBuf};
use std::process::{Child, Command};

pub fn build_args(game: &Game, s: &Settings, fullscreen: bool, rom: &str) -> String {
    let mut tpl = if !game.template_override.trim().is_empty() {
        game.template_override.clone()
    } else if !s.launch_template.trim().is_empty() {
        s.launch_template.clone()
    } else {
        "\"{rom}\"".into()
    };
    if !tpl.contains("{rom}") {
        tpl.push_str(" \"{rom}\"");
    }
    let fs = if fullscreen { s.fullscreen_args.as_str() } else { "" };
    let args = tpl.replace("{fullscreen}", fs).replace("{rom}", rom);
    args.split_whitespace().collect::<Vec<_>>().join(" ")
}

pub fn emulator_for(game: &Game, s: &Settings) -> Result<PathBuf, String> {
    let emu = if game.emulator_override.trim().is_empty() { &s.emulator_path } else { &game.emulator_override };
    if emu.trim().is_empty() {
        return Err("Nenhum emulador configurado. Abra Configurações e escolha o .exe do emulador.".into());
    }
    let p = PathBuf::from(emu.trim());
    if !p.exists() {
        return Err(format!("Emulador não encontrado:\n{}", p.display()));
    }
    Ok(p)
}

/// Extrai a ROM do .zip para uma pasta temporária, se a opção estiver ligada.
pub fn prepare_rom(game: &Game, s: &Settings) -> Result<String, String> {
    if !(s.extract_zip && game.rom_path.to_lowercase().ends_with(".zip") && !game.rom_entry.is_empty()) {
        return Ok(game.rom_path.clone());
    }
    let out = std::env::temp_dir().join("MDLauncher");
    std::fs::create_dir_all(&out).map_err(|e| e.to_string())?;
    let name = Path::new(&game.rom_entry).file_name().ok_or("Entrada inválida no zip")?;
    let target = out.join(name);
    let f = std::fs::File::open(&game.rom_path).map_err(|e| e.to_string())?;
    let mut z = zip::ZipArchive::new(f).map_err(|e| e.to_string())?;
    let mut e = z.by_name(&game.rom_entry).map_err(|e| e.to_string())?;
    let mut dst = std::fs::File::create(&target).map_err(|e| e.to_string())?;
    std::io::copy(&mut e, &mut dst).map_err(|e| e.to_string())?;
    Ok(target.to_string_lossy().to_string())
}

pub fn spawn(emu: &Path, args: &str) -> Result<Child, String> {
    let mut cmd = Command::new(emu);
    if let Some(dir) = emu.parent() {
        cmd.current_dir(dir);
    }
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        cmd.raw_arg(args); // repassa os argumentos exatamente como no modelo (aspas incluídas)
    }
    #[cfg(not(windows))]
    {
        cmd.args(split_args(args));
    }
    cmd.spawn().map_err(|e| format!("Não consegui abrir o emulador: {e}"))
}

#[cfg(not(windows))]
fn split_args(s: &str) -> Vec<String> {
    let mut out = vec![];
    let mut cur = String::new();
    let mut q = false;
    for c in s.chars() {
        match c {
            '"' => q = !q,
            ' ' if !q => {
                if !cur.is_empty() {
                    out.push(std::mem::take(&mut cur));
                }
            }
            _ => cur.push(c),
        }
    }
    if !cur.is_empty() {
        out.push(cur);
    }
    out
}

pub fn open_in_explorer(path: &str) -> Result<(), String> {
    let p = Path::new(path);
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        let mut c = Command::new("explorer");
        if p.is_file() {
            c.raw_arg(format!("/select,\"{}\"", p.display()));
        } else {
            c.arg(p);
        }
        c.spawn().map_err(|e| e.to_string())?;
    }
    #[cfg(not(windows))]
    {
        let target = if p.is_dir() { p.to_path_buf() } else { p.parent().map(|x| x.to_path_buf()).unwrap_or_default() };
        Command::new("xdg-open").arg(target).spawn().map_err(|e| e.to_string())?;
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn monta_argumentos() {
        let mut s = Settings::default();
        s.launch_template = "-gen -auto {fullscreen} \"{rom}\"".into();
        s.fullscreen_args = "-fullscreen".into();
        let g = Game::default();
        assert_eq!(build_args(&g, &s, true, "C:\\R\\Sonic 2.md"), "-gen -auto -fullscreen \"C:\\R\\Sonic 2.md\"");
        assert_eq!(build_args(&g, &s, false, "x.md"), "-gen -auto \"x.md\"");
        let g2 = Game { template_override: "-L core.dll".into(), ..Default::default() };
        assert_eq!(build_args(&g2, &s, false, "x.md"), "-L core.dll \"x.md\"");
    }
}
