//! Fontes de metadados e artes: SteamGridDB, IGDB (Twitch) e Libretro Thumbnails.

use crate::storage::{cache_dir, Game};
use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::path::Path;
use std::sync::{Mutex, OnceLock};
use std::time::{Duration, Instant};

const UA: &str = "MDLauncher/2.0 (+https://github.com/leoblaidd/MDlauncher)";

fn client() -> &'static reqwest::Client {
    static C: OnceLock<reqwest::Client> = OnceLock::new();
    C.get_or_init(|| {
        reqwest::Client::builder().user_agent(UA).timeout(Duration::from_secs(20)).build().expect("http client")
    })
}

fn err(e: reqwest::Error) -> String {
    if e.is_connect() || e.is_timeout() {
        format!("Sem conexão: {e}")
    } else {
        e.to_string()
    }
}

async fn check(r: reqwest::Response) -> Result<Option<reqwest::Response>, String> {
    match r.status().as_u16() {
        200..=299 => Ok(Some(r)),
        401 | 403 => Err("Chave/credencial inválida".into()),
        404 => Ok(None),
        c => Err(format!("HTTP {c}")),
    }
}

#[derive(Serialize, Deserialize, Clone, Debug, Default)]
#[serde(default)]
pub struct Candidate {
    pub source: String,
    pub id: Value,
    pub name: String,
    pub release_date: String,
    pub multiplayer: Option<bool>,
    pub players: String,
    pub developer: String,
    pub extra: Value,
}

#[derive(Serialize, Deserialize, Clone, Debug, Default)]
#[serde(default)]
pub struct Art {
    pub url: String,
    pub thumb: String,
    pub kind: String,
    pub source: String,
    pub width: i64,
    pub height: i64,
}

fn ts_to_date(ts: i64) -> String {
    chrono::DateTime::from_timestamp(ts, 0).map(|d| d.format("%Y-%m-%d").to_string()).unwrap_or_default()
}

pub async fn download(url: &str, stem: &str) -> Result<String, String> {
    let ext = Path::new(url.split('?').next().unwrap_or(url))
        .extension()
        .map(|e| e.to_string_lossy().to_lowercase())
        .filter(|e| ["png", "jpg", "jpeg", "webp"].contains(&e.as_str()))
        .unwrap_or_else(|| "png".into());
    let r = client().get(url).send().await.map_err(err)?;
    let r = check(r).await?.ok_or("Imagem não encontrada")?;
    let bytes = r.bytes().await.map_err(err)?;
    remove_stem(stem);
    let dest = cache_dir().join(format!("{stem}.{ext}"));
    std::fs::write(&dest, &bytes).map_err(|e| e.to_string())?;
    Ok(dest.to_string_lossy().to_string())
}

pub fn remove_stem(stem: &str) {
    if let Ok(rd) = std::fs::read_dir(cache_dir()) {
        for e in rd.flatten() {
            let p = e.path();
            if p.file_stem().map(|s| s.to_string_lossy() == stem).unwrap_or(false) {
                let _ = std::fs::remove_file(p);
            }
        }
    }
}

// --------------------------------------------------------------------------- SteamGridDB
pub struct SteamGridDB {
    pub key: String,
}

impl SteamGridDB {
    pub const NAME: &'static str = "SteamGridDB";
    const BASE: &'static str = "https://www.steamgriddb.com/api/v2";

    pub fn enabled(&self) -> bool {
        !self.key.trim().is_empty()
    }

    async fn get(&self, path: &str) -> Result<Vec<Value>, String> {
        let r = client()
            .get(format!("{}{}", Self::BASE, path))
            .bearer_auth(self.key.trim())
            .send()
            .await
            .map_err(err)?;
        let Some(r) = check(r).await? else { return Ok(vec![]) };
        let v: Value = r.json().await.map_err(err)?;
        if !v["success"].as_bool().unwrap_or(false) {
            return Ok(vec![]);
        }
        Ok(v["data"].as_array().cloned().unwrap_or_default())
    }

    pub async fn search(&self, term: &str) -> Result<Vec<Candidate>, String> {
        let items = self.get(&format!("/search/autocomplete/{}", urlencoding::encode(term))).await?;
        Ok(items
            .into_iter()
            .take(12)
            .map(|it| Candidate {
                source: Self::NAME.into(),
                id: it["id"].clone(),
                name: it["name"].as_str().unwrap_or("").into(),
                release_date: it["release_date"].as_i64().map(ts_to_date).unwrap_or_default(),
                ..Default::default()
            })
            .collect())
    }

    fn arts(items: Vec<Value>, kind: &str) -> Vec<Art> {
        items
            .into_iter()
            .filter_map(|i| {
                let url = i["url"].as_str()?.to_string();
                Some(Art {
                    thumb: i["thumb"].as_str().unwrap_or(&url).to_string(),
                    url,
                    kind: kind.into(),
                    source: Self::NAME.into(),
                    width: i["width"].as_i64().unwrap_or(0),
                    height: i["height"].as_i64().unwrap_or(0),
                })
            })
            .collect()
    }

    pub async fn covers(&self, gid: &Value) -> Result<Vec<Art>, String> {
        let items = self
            .get(&format!("/grids/game/{}?dimensions=600x900,342x482,660x930&types=static&nsfw=false", id_str(gid)))
            .await?;
        Ok(Self::arts(items, "cover"))
    }

    pub async fn heroes(&self, gid: &Value) -> Result<Vec<Art>, String> {
        let items = self.get(&format!("/heroes/game/{}?types=static&nsfw=false", id_str(gid))).await?;
        Ok(Self::arts(items, "hero"))
    }
}

fn id_str(v: &Value) -> String {
    match v {
        Value::String(s) => s.clone(),
        other => other.to_string(),
    }
}

// --------------------------------------------------------------------------- IGDB
pub struct Igdb {
    pub cid: String,
    pub secret: String,
}

static TOKEN: Mutex<Option<(String, String, Instant)>> = Mutex::new(None);

impl Igdb {
    pub const NAME: &'static str = "IGDB";
    const PLATFORM_MD: i64 = 29;

    pub fn enabled(&self) -> bool {
        !self.cid.trim().is_empty() && !self.secret.trim().is_empty()
    }

    async fn token(&self) -> Result<String, String> {
        if let Some((cid, tok, exp)) = TOKEN.lock().unwrap().clone() {
            if cid == self.cid && exp > Instant::now() + Duration::from_secs(60) {
                return Ok(tok);
            }
        }
        let r = client()
            .post("https://id.twitch.tv/oauth2/token")
            .query(&[("client_id", self.cid.trim()), ("client_secret", self.secret.trim()), ("grant_type", "client_credentials")])
            .send()
            .await
            .map_err(err)?;
        let r = check(r).await?.ok_or("Credenciais IGDB inválidas")?;
        let v: Value = r.json().await.map_err(err)?;
        let tok = v["access_token"].as_str().ok_or("Credenciais IGDB inválidas")?.to_string();
        let exp = Instant::now() + Duration::from_secs(v["expires_in"].as_u64().unwrap_or(3600));
        *TOKEN.lock().unwrap() = Some((self.cid.clone(), tok.clone(), exp));
        Ok(tok)
    }

    async fn query(&self, body: String) -> Result<Vec<Value>, String> {
        let tok = self.token().await?;
        let r = client()
            .post("https://api.igdb.com/v4/games")
            .header("Client-ID", self.cid.trim())
            .bearer_auth(tok)
            .header("Accept", "application/json")
            .body(body)
            .send()
            .await
            .map_err(err)?;
        let Some(r) = check(r).await? else { return Ok(vec![]) };
        let v: Value = r.json().await.map_err(err)?;
        Ok(v.as_array().cloned().unwrap_or_default())
    }

    fn img(id: &str, size: &str) -> String {
        format!("https://images.igdb.com/igdb/image/upload/t_{size}/{id}.jpg")
    }

    pub async fn search(&self, term: &str) -> Result<Vec<Candidate>, String> {
        let safe = term.replace('"', "");
        let fields = "fields name,first_release_date,game_modes.name,multiplayer_modes.offlinemax,\
                      multiplayer_modes.offlinecoopmax,involved_companies.company.name,involved_companies.developer,\
                      cover.image_id,artworks.image_id,screenshots.image_id;";
        let mut res = self
            .query(format!("search \"{safe}\"; {fields} where platforms = ({}); limit 12;", Self::PLATFORM_MD))
            .await?;
        if res.is_empty() {
            res = self.query(format!("search \"{safe}\"; {fields} limit 12;")).await?;
        }
        Ok(res.into_iter().map(|g| Self::to_candidate(g)).collect())
    }

    fn to_candidate(g: Value) -> Candidate {
        let modes: Vec<String> = g["game_modes"]
            .as_array()
            .map(|a| a.iter().filter_map(|m| m["name"].as_str().map(|s| s.to_lowercase())).collect())
            .unwrap_or_default();
        let multi = if modes.is_empty() {
            None
        } else {
            let all = modes.join(" ");
            Some(["multiplayer", "co-operative", "split screen"].iter().any(|k| all.contains(k)))
        };
        let mut mx = 0;
        for mm in g["multiplayer_modes"].as_array().cloned().unwrap_or_default() {
            mx = mx.max(mm["offlinemax"].as_i64().unwrap_or(0)).max(mm["offlinecoopmax"].as_i64().unwrap_or(0));
        }
        let players = if mx > 1 {
            format!("1-{mx}")
        } else if multi == Some(false) {
            "1".into()
        } else {
            String::new()
        };
        let developer = g["involved_companies"]
            .as_array()
            .and_then(|a| {
                a.iter().find(|ic| ic["developer"].as_bool().unwrap_or(false)).and_then(|ic| ic["company"]["name"].as_str())
            })
            .unwrap_or("")
            .to_string();
        Candidate {
            source: Self::NAME.into(),
            id: g["id"].clone(),
            name: g["name"].as_str().unwrap_or("").into(),
            release_date: g["first_release_date"].as_i64().map(ts_to_date).unwrap_or_default(),
            multiplayer: multi,
            players,
            developer,
            extra: g,
        }
    }

    pub fn covers(c: &Candidate) -> Vec<Art> {
        match c.extra["cover"]["image_id"].as_str() {
            Some(id) => vec![Art {
                url: Self::img(id, "cover_big_2x"),
                thumb: Self::img(id, "cover_big"),
                kind: "cover".into(),
                source: Self::NAME.into(),
                ..Default::default()
            }],
            None => vec![],
        }
    }

    pub fn heroes(c: &Candidate) -> Vec<Art> {
        let mut out = vec![];
        for key in ["artworks", "screenshots"] {
            for a in c.extra[key].as_array().cloned().unwrap_or_default() {
                if let Some(id) = a["image_id"].as_str() {
                    out.push(Art {
                        url: Self::img(id, "1080p"),
                        thumb: Self::img(id, "screenshot_med"),
                        kind: "hero".into(),
                        source: Self::NAME.into(),
                        ..Default::default()
                    });
                }
            }
        }
        out
    }
}

// --------------------------------------------------------------------------- Libretro
pub struct Libretro;

impl Libretro {
    pub const NAME: &'static str = "Libretro";
    const BASE: &'static str = "https://thumbnails.libretro.com/Sega%20-%20Mega%20Drive%20-%20Genesis";

    fn safe(name: &str) -> String {
        name.chars().map(|c| if "&*/:`<>?\\|\"".contains(c) { '_' } else { c }).collect()
    }

    async fn exists(folder: &str, name: &str) -> Option<String> {
        let url = format!("{}/{}/{}.png", Self::BASE, folder, urlencoding::encode(&Self::safe(name)));
        match client().head(&url).send().await {
            Ok(r) if r.status().is_success() => Some(url),
            _ => None,
        }
    }

    fn candidates_for(stem: &str, clean: &str) -> Vec<String> {
        let mut names = vec![stem.to_string()];
        let base = clean.replace(": ", " - ");
        for reg in ["(USA, Europe)", "(USA)", "(World)", "(Europe)", "(Japan, USA)", "(Brazil)", "(Japan)"] {
            names.push(format!("{base} {reg}"));
        }
        let mut seen = std::collections::HashSet::new();
        names.retain(|n| seen.insert(n.clone()));
        names
    }

    async fn find(stem: &str, clean: &str, folder: &str) -> Option<String> {
        for n in Self::candidates_for(stem, clean) {
            if let Some(u) = Self::exists(folder, &n).await {
                return Some(u);
            }
        }
        None
    }

    pub async fn arts(stem: &str, clean: &str) -> Vec<Art> {
        let mut out = vec![];
        if let Some(c) = Self::find(stem, clean, "Named_Boxarts").await {
            out.push(Art { thumb: c.clone(), url: c, kind: "cover".into(), source: Self::NAME.into(), ..Default::default() });
        }
        for folder in ["Named_Titles", "Named_Snaps"] {
            if let Some(h) = Self::find(stem, clean, folder).await {
                out.push(Art { thumb: h.clone(), url: h, kind: "hero".into(), source: Self::NAME.into(), ..Default::default() });
            }
        }
        out
    }
}

// --------------------------------------------------------------------------- pipeline automático
fn norm(s: &str) -> String {
    s.to_lowercase().chars().filter(|c| c.is_ascii_alphanumeric()).collect()
}

pub fn best_match(cands: &[Candidate], name: &str) -> Option<Candidate> {
    let t = norm(name);
    cands
        .iter()
        .find(|c| norm(&c.name) == t)
        .or_else(|| cands.iter().find(|c| !t.is_empty() && (norm(&c.name).contains(&t) || t.contains(&norm(&c.name)))))
        .or_else(|| cands.first())
        .cloned()
}

pub fn rom_stem(g: &Game) -> String {
    let src = if g.rom_entry.is_empty() { &g.rom_path } else { &g.rom_entry };
    Path::new(src).file_stem().map(|s| s.to_string_lossy().to_string()).unwrap_or_default()
}

/// Preenche capa, hero, data e multiplayer usando as fontes em cascata.
pub async fn auto_fetch(mut g: Game, sgdb: SteamGridDB, igdb: Igdb) -> Game {
    let name = g.name.clone();
    let stem = rom_stem(&g);

    if sgdb.enabled() {
        let r: Result<(), String> = async {
            if let Some(m) = best_match(&sgdb.search(&name).await?, &name) {
                g.sgdb_id = m.id.as_i64().unwrap_or(0);
                if g.release_date.is_empty() {
                    g.release_date = m.release_date.clone();
                }
                if g.cover_path.is_empty() {
                    if let Some(a) = sgdb.covers(&m.id).await?.first() {
                        g.cover_path = download(&a.url, &format!("{}_cover", g.id)).await?;
                        g.cover_source = SteamGridDB::NAME.into();
                    }
                }
                if g.hero_path.is_empty() {
                    if let Some(a) = sgdb.heroes(&m.id).await?.first() {
                        g.hero_path = download(&a.url, &format!("{}_hero", g.id)).await?;
                        g.hero_source = SteamGridDB::NAME.into();
                    }
                }
            }
            Ok(())
        }
        .await;
        if let Err(e) = r {
            eprintln!("SteamGridDB: {e}");
        }
    }

    if igdb.enabled() {
        let r: Result<(), String> = async {
            if let Some(m) = best_match(&igdb.search(&name).await?, &name) {
                g.igdb_id = m.id.as_i64().unwrap_or(0);
                if g.release_date.is_empty() {
                    g.release_date = m.release_date.clone();
                }
                if g.multiplayer.is_none() {
                    g.multiplayer = m.multiplayer;
                }
                if g.players.is_empty() {
                    g.players = m.players.clone();
                }
                if g.developer.is_empty() {
                    g.developer = m.developer.clone();
                }
                if g.cover_path.is_empty() {
                    if let Some(a) = Igdb::covers(&m).first() {
                        g.cover_path = download(&a.url, &format!("{}_cover", g.id)).await?;
                        g.cover_source = Igdb::NAME.into();
                    }
                }
                if g.hero_path.is_empty() {
                    if let Some(a) = Igdb::heroes(&m).first() {
                        g.hero_path = download(&a.url, &format!("{}_hero", g.id)).await?;
                        g.hero_source = Igdb::NAME.into();
                    }
                }
            }
            Ok(())
        }
        .await;
        if let Err(e) = r {
            eprintln!("IGDB: {e}");
        }
    }

    if g.cover_path.is_empty() || g.hero_path.is_empty() {
        for a in Libretro::arts(&stem, &name).await {
            if a.kind == "cover" && g.cover_path.is_empty() {
                if let Ok(p) = download(&a.url, &format!("{}_cover", g.id)).await {
                    g.cover_path = p;
                    g.cover_source = Libretro::NAME.into();
                }
            } else if a.kind == "hero" && g.hero_path.is_empty() {
                if let Ok(p) = download(&a.url, &format!("{}_hero", g.id)).await {
                    g.hero_path = p;
                    g.hero_source = Libretro::NAME.into();
                }
            }
        }
    }
    g.metadata_done = true;
    g
}
