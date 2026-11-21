<p align="center">
  <img src="assets/icon.png" width="110" alt="MD Launcher">
</p>

<h1 align="center">MD Launcher</h1>

<p align="center">
  Launcher em Qt para a sua coleção de <b>Mega Drive / Genesis</b>, no estilo DuckStation, PCSX2 e RPCS3,<br>
  funcionando com <b>qualquer emulador</b>.
</p>

<p align="center">
  <a href="https://github.com/leoblaidd/MDlauncher/releases/latest"><b>⬇ Baixar a última versão</b></a>
</p>

![Biblioteca](docs/biblioteca.png)

> As capas das imagens acima são de exemplo. No uso real, elas vêm do SteamGridDB, do IGDB ou do Libretro.

## Por que existe

Os emuladores de Mega Drive rodam muito bem, mas nenhum tem uma biblioteca bonita com capas, tempo de jogo e
informações. O MD Launcher é só isso: uma tela com as capas dos seus jogos. Você clica, dá play e o seu
emulador favorito abre o jogo.

## Recursos

- **Interface limpa, sem barra de título:** fundo xadrez escuro inspirado nas caixas de Mega Drive, botões de
  fechar, minimizar e maximizar no canto superior esquerdo e o nome no canto direito. Para arrastar a janela,
  puxe pelo topo; dois cliques maximizam. As bordas redimensionam.
- **Grid de capas** com zoom ajustável pelo controle deslizante do dock.
- **Modal do jogo** com hero estilo Steam no topo, capa sobreposta, nome, data de lançamento, multiplayer,
  desenvolvedora e **contador de horas jogadas**.
- **Botão Jogar + Tela cheia:** o botão de tela cheia adiciona o argumento certo para o seu emulador (veja a tabela).
- **Funciona com qualquer emulador:** você escolhe o `.exe` e, se quiser, o modelo de argumentos.
- **Detecção de ROMs:** `.md`, `.gen`, `.smd`, `.bin`, `.68k`, `.sgd`, `.mdx` e `.zip` com a ROM dentro. Arquivos
  `.bin` são checados pelo cabeçalho `SEGA` para não confundir com ROMs de outros consoles.
- **Capas, heroes e informações automáticas:**
  1. **SteamGridDB:** capa (grid 600×900) e hero.
  2. **IGDB:** data de lançamento, multiplayer, número de jogadores, desenvolvedora e artes que faltarem.
  3. **Libretro Thumbnails:** box art e tela de título, sem precisar de chave (fallback).
- **Editor completo:** nome, data, multiplayer, jogadores, desenvolvedora, tempo jogado, caminho da ROM/ZIP,
  emulador e argumentos específicos do jogo. Para as artes, escolha a fonte (SteamGridDB, IGDB ou Libretro),
  busque, veja as opções em miniatura e clique para definir. Também dá para usar um arquivo local.
- **Dock estilo macOS:** adicionar jogo manualmente · abrir o emulador sem jogo · abrir a pasta de ROMs ·
  tamanho das capas · configurações.
- **Menu de contexto** no grid (botão direito): jogar, editar, mostrar no Explorer, buscar artes de novo e remover.
- **Assistente de primeira execução:** emulador → pasta de ROMs → chaves de API.
- **Instalador** que pergunta onde instalar, além de uma versão portátil em `.zip`.

| Modal do jogo | Edição |
|---|---|
| ![Jogo](docs/jogo.png) | ![Editar](docs/editar.png) |

## Instalação

1. Baixe o `MDLauncher-1.0.0-Setup.exe` na página de [Releases](https://github.com/leoblaidd/MDlauncher/releases/latest).
2. Execute o instalador e escolha a pasta de instalação.
3. Abra o MD Launcher. O assistente pede:
   - o **.exe do emulador**;
   - a **pasta das ROMs**;
   - a **chave do SteamGridDB** (e, se quiser, as credenciais do IGDB).

> O Windows SmartScreen pode avisar que o app não é reconhecido, porque o executável não tem assinatura
> digital. Clique em **Mais informações → Executar assim mesmo**.

### Chaves de API

| Fonte | Para quê | Como conseguir |
|---|---|---|
| SteamGridDB | Capas e heroes | Crie uma conta em [steamgriddb.com](https://www.steamgriddb.com) e gere a chave em **Preferences → API**. |
| IGDB (opcional) | Data, multiplayer, desenvolvedora e artes extras | Registre um app no [Twitch Developers](https://dev.twitch.tv/console/apps) e use o **Client ID** e o **Client Secret** ([guia](https://api-docs.igdb.com/#account-creation)). |
| Libretro | Box art e tela de título | Não precisa de chave. |

## Emuladores e tela cheia

Quando você escolhe o `.exe`, o launcher reconhece os emuladores abaixo e já preenche o modelo de argumentos e o
argumento de tela cheia:

| Emulador | Tela cheia | Modelo sugerido | Observação |
|---|---|---|---|
| RetroArch | `-f` | `-L "cores\genesis_plus_gx_libretro.dll" {fullscreen} "{rom}"` | Troque o core se usar PicoDrive ou BlastEm. |
| Kega Fusion | `-fullscreen` | `-gen -auto {fullscreen} "{rom}"` | Em tela cheia, ESC fecha o emulador. |
| BlastEm | `-f` | `{fullscreen} "{rom}"` | O `-f` **alterna** o modo: se o `blastem.cfg` já estiver em fullscreen, abre em janela. |
| ares | `--fullscreen` | `--system "Mega Drive" {fullscreen} "{rom}"` | |
| Mednafen | `-video.fs 1` | `{fullscreen} "{rom}"` | |
| Gens/GS | `--fs --quickexit` | `{fullscreen} "{rom}"` | `--quickexit` faz o ESC fechar o emulador. |
| DGen | `-f` | `{fullscreen} "{rom}"` | |
| Outros | *(você informa)* | `{fullscreen} "{rom}"` | Qualquer emulador que aceite a ROM pela linha de comando. |

`{rom}` vira o caminho do arquivo e `{fullscreen}` vira o argumento de tela cheia quando o botão estiver ligado.
Cada jogo pode ter emulador e argumentos próprios na tela de edição.

Se o seu emulador não abre `.zip`, ligue **Extrair ROMs de .zip antes de abrir** em Configurações.

## Onde ficam os dados

`%APPDATA%\MDLauncher\`
- `settings.json`: configurações
- `library.json`: biblioteca, tempos de jogo e edições
- `cache\`: capas e heroes baixados

## Rodar a partir do código

```bash
pip install -r requirements.txt
python run.py
```

### Gerar o executável

O workflow [`build.yml`](.github/workflows/build.yml) faz o build no Windows com **PyInstaller** e
**Inno Setup** e publica a release automaticamente quando uma tag `v*` é enviada:

```bash
git tag v1.0.1 && git push origin v1.0.1
```

Para fazer na sua máquina (Windows):

```powershell
pip install -r requirements.txt pyinstaller
pyinstaller --noconfirm --windowed --name MDLauncher --icon assets/icon.ico --add-data "assets;assets" run.py
& "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe" installer\MDLauncher.iss
```

## Estrutura

```
mdlauncher/
  app.py            ponto de entrada
  storage.py        configurações e biblioteca (JSON)
  scanner.py        identificação de ROMs de Mega Drive e .zip
  metadata.py       SteamGridDB, IGDB e Libretro
  emulators.py      perfis de emulador, tela cheia e execução
  ui/               janela, grid, dock e modais (PySide6 / Qt 6)
installer/          script do Inno Setup
```

## Créditos

- Artes: [SteamGridDB](https://www.steamgriddb.com), [IGDB](https://www.igdb.com) e [Libretro Thumbnails](https://thumbnails.libretro.com).
- Interface feita com [Qt for Python (PySide6)](https://doc.qt.io/qtforpython-6/).
- Mega Drive e Sega são marcas da SEGA. Este projeto não tem ligação com a SEGA e não distribui ROMs: use as cópias
  dos seus próprios cartuchos.
