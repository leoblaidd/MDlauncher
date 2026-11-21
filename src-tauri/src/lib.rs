//! MD Launcher — backend em Rust (Tauri 2). A interface fica em ../src (HTML/CSS/JS).

mod emulators;
mod metadata;
mod scanner;
mod storage;

use metadata::{Art, Candidate, Igdb, Libretro, SteamGridDB};
use serde::Serialize;
use std::collections::HashSet;
use std::path::Path;
use std::sync::Mutex;
use std::time::Instant;
use storage::{cache_dir, data_dir, now, Game, Library, Settings};
use tauri::{AppHandle, Emitter, Manager, State};

pub struct AppState {
    settings: Mutex<Settings>,
    lib: Mutex<Library>,
    running: Mutex<HashSet<String>>,
    selftest: bool,
}

#[derive(Serialize)]
struct InitState {
    version: String,
    settings: Settings,
    games: Vec<Game>,
    data_dir: String,
    selftest: bool,
}

#[derive(Serialize)]
struct ScanResult {
    games: Vec<Game>,
    new_count: usize,
}

#[derive(Serialize)]
struct Arts {
    covers: Vec<Art>,
    heroes: Vec<Art>,
}

#[derive(Serialize, Clone)]
struct Finished {
    id: String,
    seconds: i64,
    game: Option<Game>,
}

fn sources(s: &Settings) -> (SteamGridDB, Igdb) {
    (SteamGridDB { key: s.sgdb_key.clone() }, Igdb { cid: s.igdb_client_id.clone(), secret: s.igdb_client_secret.clone() })
}

fn get_game(state: &State<'_, AppState>, id: &str) -> Result<Game, String> {
    state.lib.lock().unwrap().games.get(id).cloned().ok_or_else(|| "Jogo não encontrado".to_string())
}

fn store(state: &State<'_, AppState>, g: Game) -> Result<Game, String> {
    let mut lib = state.lib.lock().unwrap();
    lib.add(g.clone());
    lib.save()?;
    Ok(g)
}

// --------------------------------------------------------------------------- estado
#[tauri::command]
fn get_state(app: AppHandle, state: State<'_, AppState>) -> InitState {
    InitState {
        version: app.package_info().version.to_string(),
        settings: state.settings.lock().unwrap().clone(),
        games: state.lib.lock().unwrap().list(),
        data_dir: data_dir().to_string_lossy().to_string(),
        selftest: state.selftest,
    }
}

#[tauri::command]
fn save_settings(state: State<'_, AppState>, settings: Settings) -> Result<(), String> {
    settings.save()?;
    *state.settings.lock().unwrap() = settings;
    Ok(())
}

#[tauri::command]
fn update_game(state: State<'_, AppState>, mut game: Game) -> Result<Game, String> {
    if let Ok(old) = get_game(&state, &game.id) {
        if old.rom_path != game.rom_path && !game.rom_path.is_empty() {
            game.rom_entry = scanner::inspect_file(Path::new(&game.rom_path)).1;
        }
    }
    store(&state, game)
}

#[tauri::command]
fn remove_game(state: State<'_, AppState>, id: String) -> Result<(), String> {
    let mut lib = state.lib.lock().unwrap();
    lib.remove(&id);
    lib.save()
}

// --------------------------------------------------------------------------- ROMs
#[tauri::command]
async fn scan(state: State<'_, AppState>) -> Result<ScanResult, String> {
    let (folders, rec) = {
        let s = state.settings.lock().unwrap();
        (s.rom_folders.clone(), s.scan_subfolders)
    };
    let found = tauri::async_runtime::spawn_blocking(move || {
        folders.iter().flat_map(|f| scanner::scan_folder(f, rec)).collect::<Vec<_>>()
    })
    .await
    .map_err(|e| e.to_string())?;
    let mut lib = state.lib.lock().unwrap();
    let mut new_count = 0;
    for g in found {
        if !lib.games.contains_key(&g.id) {
            lib.add(g);
            new_count += 1;
        }
    }
    lib.save()?;
    Ok(ScanResult { games: lib.list(), new_count })
}

#[tauri::command]
async fn count_roms(folder: String, recursive: bool) -> Result<usize, String> {
    tauri::async_runtime::spawn_blocking(move || scanner::scan_folder(&folder, recursive).len())
        .await
        .map_err(|e| e.to_string())
}

#[tauri::command]
fn add_files(state: State<'_, AppState>, paths: Vec<String>) -> Result<Vec<Game>, String> {
    let mut lib = state.lib.lock().unwrap();
    let mut out = vec![];
    for p in paths {
        let Some(g) = scanner::game_from_file(&p) else { continue };
        if let Some(existing) = lib.games.get(&g.id) {
            out.push(existing.clone());
        } else {
            lib.add(g.clone());
            out.push(g);
        }
    }
    lib.save()?;
    Ok(out)
}

// --------------------------------------------------------------------------- metadados
#[tauri::command]
async fn auto_fetch(state: State<'_, AppState>, id: String, force: bool) -> Result<Game, String> {
    let mut g = get_game(&state, &id)?;
    if force {
        g.cover_path.clear();
        g.hero_path.clear();
        g.cover_source.clear();
        g.hero_source.clear();
        g.release_date.clear();
        g.multiplayer = None;
        g.players.clear();
        g.developer.clear();
    }
    let (sgdb, igdb) = sources(&state.settings.lock().unwrap());
    let fetched = metadata::auto_fetch(g, sgdb, igdb).await;
    // preserva o que o usuário possa ter mudado enquanto a busca rodava
    let mut cur = get_game(&state, &id).unwrap_or_else(|_| fetched.clone());
    for (dst, src) in [
        (&mut cur.cover_path, &fetched.cover_path),
        (&mut cur.hero_path, &fetched.hero_path),
        (&mut cur.cover_source, &fetched.cover_source),
        (&mut cur.hero_source, &fetched.hero_source),
        (&mut cur.release_date, &fetched.release_date),
        (&mut cur.players, &fetched.players),
        (&mut cur.developer, &fetched.developer),
    ] {
        if force || dst.is_empty() {
            *dst = src.clone();
        }
    }
    if force || cur.multiplayer.is_none() {
        cur.multiplayer = fetched.multiplayer;
    }
    cur.sgdb_id = fetched.sgdb_id;
    cur.igdb_id = fetched.igdb_id;
    cur.metadata_done = true;
    store(&state, cur)
}

#[tauri::command]
async fn search(state: State<'_, AppState>, source: String, term: String, id: String) -> Result<Vec<Candidate>, String> {
    let (sgdb, igdb) = sources(&state.settings.lock().unwrap());
    match source.as_str() {
        SteamGridDB::NAME => sgdb.search(&term).await,
        Igdb::NAME => igdb.search(&term).await,
        _ => {
            let g = get_game(&state, &id)?;
            Ok(vec![Candidate {
                source: Libretro::NAME.into(),
                id: metadata::rom_stem(&g).into(),
                name: term,
                ..Default::default()
            }])
        }
    }
}

#[tauri::command]
async fn get_arts(state: State<'_, AppState>, candidate: Candidate) -> Result<Arts, String> {
    let (sgdb, _) = sources(&state.settings.lock().unwrap());
    match candidate.source.as_str() {
        SteamGridDB::NAME => {
            Ok(Arts { covers: sgdb.covers(&candidate.id).await?, heroes: sgdb.heroes(&candidate.id).await? })
        }
        Igdb::NAME => Ok(Arts { covers: Igdb::covers(&candidate), heroes: Igdb::heroes(&candidate) }),
        _ => {
            let stem = candidate.id.as_str().unwrap_or("").to_string();
            let arts = Libretro::arts(&stem, &candidate.name).await;
            let (covers, heroes): (Vec<Art>, Vec<Art>) = arts.into_iter().partition(|a| a.kind == "cover");
            Ok(Arts { covers, heroes })
        }
    }
}

/// Define capa ou hero: `url` (baixa), `path` (copia um arquivo local) ou nenhum dos dois (remove).
#[tauri::command]
async fn apply_art(
    state: State<'_, AppState>,
    id: String,
    kind: String,
    url: Option<String>,
    path: Option<String>,
    source: Option<String>,
) -> Result<Game, String> {
    let stem = format!("{id}_{kind}");
    let (file, src) = if let Some(u) = url.filter(|u| !u.is_empty()) {
        (metadata::download(&u, &stem).await?, source.unwrap_or_default())
    } else if let Some(p) = path.filter(|p| !p.is_empty()) {
        let ext = Path::new(&p).extension().map(|e| e.to_string_lossy().to_lowercase()).unwrap_or_else(|| "png".into());
        let bytes = std::fs::read(&p).map_err(|e| e.to_string())?;
        metadata::remove_stem(&stem);
        let dest = cache_dir().join(format!("{stem}.{ext}"));
        std::fs::write(&dest, bytes).map_err(|e| e.to_string())?;
        (dest.to_string_lossy().to_string(), "Arquivo local".to_string())
    } else {
        metadata::remove_stem(&stem);
        (String::new(), String::new())
    };
    let mut g = get_game(&state, &id)?;
    if kind == "cover" {
        g.cover_path = file;
        g.cover_source = src;
    } else {
        g.hero_path = file;
        g.hero_source = src;
    }
    store(&state, g)
}

// --------------------------------------------------------------------------- jogar
#[tauri::command]
fn play(app: AppHandle, state: State<'_, AppState>, id: String, fullscreen: bool) -> Result<Game, String> {
    if state.running.lock().unwrap().contains(&id) {
        return Err("Esse jogo já está rodando.".into());
    }
    let s = state.settings.lock().unwrap().clone();
    let mut g = get_game(&state, &id)?;
    let emu = emulators::emulator_for(&g, &s)?;
    let rom = emulators::prepare_rom(&g, &s)?;
    let args = emulators::build_args(&g, &s, fullscreen, &rom);
    let mut child = emulators::spawn(&emu, &args)?;
    g.last_played = now();
    let g = store(&state, g)?;
    state.running.lock().unwrap().insert(id.clone());
    let start = Instant::now();
    std::thread::spawn(move || {
        let _ = child.wait();
        let secs = start.elapsed().as_secs() as i64;
        let st = app.state::<AppState>();
        st.running.lock().unwrap().remove(&id);
        let game = {
            let mut lib = st.lib.lock().unwrap();
            let g = lib.games.get_mut(&id).map(|g| {
                g.playtime += secs.max(0);
                g.clone()
            });
            let _ = lib.save();
            g
        };
        let _ = app.emit("game-finished", Finished { id, seconds: secs, game });
    });
    Ok(g)
}

#[tauri::command]
fn open_emulator(state: State<'_, AppState>) -> Result<(), String> {
    let emu = state.settings.lock().unwrap().emulator_path.clone();
    if emu.is_empty() || !Path::new(&emu).exists() {
        return Err("Nenhum emulador configurado.".into());
    }
    emulators::spawn(Path::new(&emu), "").map(|_| ())
}

#[tauri::command]
fn open_path(path: String) -> Result<(), String> {
    emulators::open_in_explorer(&path)
}

#[tauri::command]
fn open_data_dir() -> Result<(), String> {
    emulators::open_in_explorer(&data_dir().to_string_lossy())
}

#[tauri::command]
fn open_url(app: AppHandle, url: String) -> Result<(), String> {
    use tauri_plugin_opener::OpenerExt;
    app.opener().open_url(url, None::<&str>).map_err(|e| e.to_string())
}

#[tauri::command]
fn selftest_done(app: AppHandle, ok: bool) {
    app.exit(if ok { 0 } else { 1 });
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let selftest = std::env::args().any(|a| a == "--selftest");
    let mut builder = tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_opener::init());
    if !selftest {
        builder = builder.plugin(tauri_plugin_window_state::Builder::default().build());
    }
    builder
        .manage(AppState {
            settings: Mutex::new(Settings::load()),
            lib: Mutex::new(Library::load()),
            running: Mutex::new(HashSet::new()),
            selftest,
        })
        .setup(move |app| {
            // libera as imagens da pasta de dados para o protocolo asset://
            let _ = app.asset_protocol_scope().allow_directory(data_dir(), true);
            if selftest {
                std::thread::spawn(|| {
                    std::thread::sleep(std::time::Duration::from_secs(60));
                    std::process::exit(2);
                });
            }
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            get_state,
            save_settings,
            update_game,
            remove_game,
            scan,
            count_roms,
            add_files,
            auto_fetch,
            search,
            get_arts,
            apply_art,
            play,
            open_emulator,
            open_path,
            open_data_dir,
            open_url,
            selftest_done
        ])
        .run(tauri::generate_context!())
        .expect("erro ao iniciar o MD Launcher");
}
