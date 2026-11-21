//! Configurações e biblioteca (JSON em %APPDATA%\MDLauncher) — mesmo formato da versão 1.x.

use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::fs;
use std::path::{Path, PathBuf};
use std::time::{SystemTime, UNIX_EPOCH};

pub fn data_dir() -> PathBuf {
    let d = if let Ok(o) = std::env::var("MDLAUNCHER_HOME") {
        PathBuf::from(o)
    } else {
        dirs::data_dir().unwrap_or_else(|| PathBuf::from(".")).join("MDLauncher")
    };
    let _ = fs::create_dir_all(d.join("cache"));
    d
}

pub fn cache_dir() -> PathBuf {
    data_dir().join("cache")
}

pub fn now() -> f64 {
    SystemTime::now().duration_since(UNIX_EPOCH).map(|d| d.as_secs_f64()).unwrap_or(0.0)
}

fn atomic_write(path: &Path, text: &str) -> std::io::Result<()> {
    let tmp = path.with_extension("json.tmp");
    fs::write(&tmp, text)?;
    fs::rename(&tmp, path)
}

fn default_template() -> String {
    "{fullscreen} \"{rom}\"".into()
}
fn default_cover() -> i64 {
    180
}
fn yes() -> bool {
    true
}

#[derive(Serialize, Deserialize, Clone, Debug)]
pub struct Settings {
    #[serde(default)]
    pub emulator_path: String,
    #[serde(default = "default_template")]
    pub launch_template: String,
    #[serde(default)]
    pub fullscreen_args: String,
    #[serde(default)]
    pub rom_folders: Vec<String>,
    #[serde(default)]
    pub sgdb_key: String,
    #[serde(default)]
    pub igdb_client_id: String,
    #[serde(default)]
    pub igdb_client_secret: String,
    #[serde(default = "default_cover")]
    pub cover_size: i64,
    #[serde(default)]
    pub extract_zip: bool,
    #[serde(default)]
    pub fullscreen_default: bool,
    #[serde(default = "yes")]
    pub minimize_on_play: bool,
    #[serde(default = "yes")]
    pub scan_subfolders: bool,
    #[serde(default)]
    pub first_run_done: bool,
    #[serde(default)]
    pub window_geometry: String,
}

impl Default for Settings {
    fn default() -> Self {
        serde_json::from_str("{}").unwrap()
    }
}

impl Settings {
    pub fn load() -> Self {
        fs::read_to_string(data_dir().join("settings.json"))
            .ok()
            .and_then(|t| serde_json::from_str(&t).ok())
            .unwrap_or_default()
    }
    pub fn save(&self) -> Result<(), String> {
        let t = serde_json::to_string_pretty(self).map_err(|e| e.to_string())?;
        atomic_write(&data_dir().join("settings.json"), &t).map_err(|e| e.to_string())
    }
}

#[derive(Serialize, Deserialize, Clone, Debug, Default)]
#[serde(default)]
pub struct Game {
    pub id: String,
    pub name: String,
    pub rom_path: String,
    pub rom_entry: String,
    pub release_date: String,
    pub multiplayer: Option<bool>,
    pub players: String,
    pub developer: String,
    pub cover_path: String,
    pub hero_path: String,
    pub cover_source: String,
    pub hero_source: String,
    pub sgdb_id: i64,
    pub igdb_id: i64,
    pub emulator_override: String,
    pub template_override: String,
    pub fullscreen: Option<bool>,
    pub playtime: i64,
    pub last_played: f64,
    pub added: f64,
    pub metadata_done: bool,
}

/// Mesmo id da versão em Python: sha1(normcase(abspath(caminho)))[:16]
pub fn game_id_for(path: &str) -> String {
    let abs = std::path::absolute(path).unwrap_or_else(|_| PathBuf::from(path));
    let mut s = abs.to_string_lossy().to_string();
    if cfg!(windows) {
        s = s.replace('/', "\\").to_lowercase();
    }
    let h = sha1_smol::Sha1::from(s.as_bytes()).digest().to_string();
    h[..16].to_string()
}

#[derive(Default)]
pub struct Library {
    pub games: HashMap<String, Game>,
    pub order: Vec<String>, // mantém a ordem original do arquivo
}

#[derive(Serialize, Deserialize)]
struct LibFile {
    #[serde(default)]
    version: i64,
    #[serde(default)]
    games: Vec<serde_json::Value>,
}

impl Library {
    pub fn load() -> Self {
        let mut lib = Library::default();
        let Ok(t) = fs::read_to_string(data_dir().join("library.json")) else { return lib };
        let Ok(f) = serde_json::from_str::<LibFile>(&t) else { return lib };
        for v in f.games {
            if let Ok(g) = serde_json::from_value::<Game>(v) {
                if !g.id.is_empty() {
                    lib.add(g);
                }
            }
        }
        lib
    }

    pub fn add(&mut self, g: Game) {
        if !self.games.contains_key(&g.id) {
            self.order.push(g.id.clone());
        }
        self.games.insert(g.id.clone(), g);
    }

    pub fn remove(&mut self, id: &str) -> Option<Game> {
        self.order.retain(|x| x != id);
        let g = self.games.remove(id);
        if let Some(g) = &g {
            let cache = cache_dir();
            for p in [&g.cover_path, &g.hero_path] {
                if !p.is_empty() && Path::new(p).starts_with(&cache) {
                    let _ = fs::remove_file(p);
                }
            }
        }
        g
    }

    pub fn list(&self) -> Vec<Game> {
        let mut v: Vec<Game> = self.order.iter().filter_map(|id| self.games.get(id).cloned()).collect();
        v.sort_by_key(|g| g.name.to_lowercase());
        v
    }

    pub fn save(&self) -> Result<(), String> {
        let games: Vec<&Game> = self.order.iter().filter_map(|id| self.games.get(id)).collect();
        let t = serde_json::to_string_pretty(&serde_json::json!({"version": 1, "games": games}))
            .map_err(|e| e.to_string())?;
        atomic_write(&data_dir().join("library.json"), &t).map_err(|e| e.to_string())
    }
}
