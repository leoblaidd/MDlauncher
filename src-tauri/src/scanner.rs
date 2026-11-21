//! Varredura de pastas: identifica ROMs de Mega Drive (soltas ou dentro de .zip).

use crate::storage::{game_id_for, now, Game};
use regex::Regex;
use std::fs::File;
use std::io::Read;
use std::path::Path;
use std::sync::OnceLock;

const MD_EXTS: &[&str] = &["md", "gen", "smd", "bin", "68k", "sgd", "mdx"];
const MAX_ROM: u64 = 8 * 1024 * 1024; // o maior cartucho tem ~5 MB; acima disso é outra coisa (ex.: Sega CD)

fn ext_of(p: &str) -> String {
    Path::new(p).extension().map(|e| e.to_string_lossy().to_lowercase()).unwrap_or_default()
}

fn looks_like_md(head: &[u8], ext: &str, size: u64) -> bool {
    if size > MAX_ROM || size < 0x200 {
        return false;
    }
    if ext == "smd" {
        return true; // formato intercalado: sem cabeçalho legível
    }
    if head.len() >= 0x110 && head[0x100..0x110].windows(4).any(|w| w == b"SEGA") {
        return true;
    }
    matches!(ext, "md" | "gen" | "68k" | "sgd" | "mdx")
}

/// Retorna (é_md, entrada_interna_do_zip)
pub fn inspect_file(path: &Path) -> (bool, String) {
    let ext = ext_of(&path.to_string_lossy());
    if ext == "zip" {
        let Ok(f) = File::open(path) else { return (false, String::new()) };
        let Ok(mut z) = zip::ZipArchive::new(f) else { return (false, String::new()) };
        for i in 0..z.len() {
            let Ok(mut e) = z.by_index(i) else { continue };
            if e.is_dir() {
                continue;
            }
            let name = e.name().to_string();
            let iext = ext_of(&name);
            if !MD_EXTS.contains(&iext.as_str()) {
                continue;
            }
            let size = e.size();
            let mut head = vec![0u8; 0x200];
            let n = read_up_to(&mut e, &mut head);
            head.truncate(n);
            if looks_like_md(&head, &iext, size) {
                return (true, name);
            }
        }
        return (false, String::new());
    }
    if MD_EXTS.contains(&ext.as_str()) {
        let Ok(meta) = std::fs::metadata(path) else { return (false, String::new()) };
        let Ok(mut f) = File::open(path) else { return (false, String::new()) };
        let mut head = vec![0u8; 0x200];
        let n = read_up_to(&mut f, &mut head);
        head.truncate(n);
        return (looks_like_md(&head, &ext, meta.len()), String::new());
    }
    (false, String::new())
}

fn read_up_to<R: Read>(r: &mut R, buf: &mut [u8]) -> usize {
    let mut n = 0;
    while n < buf.len() {
        match r.read(&mut buf[n..]) {
            Ok(0) | Err(_) => break,
            Ok(k) => n += k,
        }
    }
    n
}

/// 'Castlevania - Bloodlines (USA) [!]' -> 'Castlevania: Bloodlines'
pub fn clean_name(stem: &str) -> String {
    static TAG: OnceLock<Regex> = OnceLock::new();
    static ART: OnceLock<Regex> = OnceLock::new();
    let tag = TAG.get_or_init(|| Regex::new(r"\s*[\(\[][^\)\]]*[\)\]]").unwrap());
    let art = ART.get_or_init(|| Regex::new(r"(?i)^(.*), (The|A|An|O|Os|As)$").unwrap());
    let mut name = stem.replace('_', " ");
    name = tag.replace_all(&name, "").trim().to_string();
    name = name.split_whitespace().collect::<Vec<_>>().join(" ");
    if let Some(c) = art.captures(&name) {
        name = format!("{} {}", &c[2], &c[1]);
    }
    if name.contains(" - ") && !name.contains(':') {
        name = name.replacen(" - ", ": ", 1);
    }
    if name.is_empty() {
        stem.to_string()
    } else {
        name
    }
}

fn make_game(p: &Path, entry: String) -> Game {
    let ps = p.to_string_lossy().to_string();
    let stem = p.file_stem().map(|s| s.to_string_lossy().to_string()).unwrap_or_default();
    Game { id: game_id_for(&ps), name: clean_name(&stem), rom_path: ps, rom_entry: entry, added: now(), ..Default::default() }
}

pub fn scan_folder(folder: &str, recursive: bool) -> Vec<Game> {
    let root = Path::new(folder);
    if !root.is_dir() {
        return vec![];
    }
    let walker = walkdir::WalkDir::new(root).max_depth(if recursive { usize::MAX } else { 1 }).follow_links(true);
    let mut out = vec![];
    for e in walker.into_iter().filter_map(|e| e.ok()) {
        if !e.file_type().is_file() {
            continue;
        }
        let ext = ext_of(&e.path().to_string_lossy());
        if ext != "zip" && !MD_EXTS.contains(&ext.as_str()) {
            continue;
        }
        let (ok, entry) = inspect_file(e.path());
        if ok {
            out.push(make_game(e.path(), entry));
        }
    }
    out
}

pub fn game_from_file(path: &str) -> Option<Game> {
    let p = Path::new(path);
    let ext = ext_of(path);
    let (ok, entry) = inspect_file(p);
    if !ok && ext != "zip" && !MD_EXTS.contains(&ext.as_str()) {
        return None;
    }
    Some(make_game(p, entry))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn limpa_nomes() {
        assert_eq!(clean_name("Sonic The Hedgehog 2 (World) (Rev A)"), "Sonic The Hedgehog 2");
        assert_eq!(clean_name("Castlevania - Bloodlines (USA)"), "Castlevania: Bloodlines");
        assert_eq!(clean_name("Lion King, The (World)"), "The Lion King");
        assert_eq!(clean_name("ToeJam & Earl (USA, Europe) [!]"), "ToeJam & Earl");
    }

    #[test]
    fn cabecalho_md() {
        let mut rom = vec![0u8; 0x20000];
        rom[0x100..0x110].copy_from_slice(b"SEGA MEGA DRIVE ");
        assert!(looks_like_md(&rom[..0x200], "bin", rom.len() as u64));
        assert!(!looks_like_md(&[0u8; 0x200], "bin", 0x20000));
        assert!(!looks_like_md(&rom[..0x200], "bin", 20 * 1024 * 1024));
    }

    /// Compara com a versão em Python: MDL_SCAN_DIR=<pasta> cargo test -- --ignored --nocapture
    #[test]
    #[ignore]
    fn scan_local() {
        let dir = std::env::var("MDL_SCAN_DIR").unwrap();
        for g in scan_folder(&dir, true) {
            println!("{} | {} | {}", g.id, g.name, g.rom_entry);
        }
    }
}
