# MD Launcher 1.0.0

Primeira versão do **MD Launcher**, uma biblioteca com capas para seus jogos de Mega Drive / Genesis que
funciona com qualquer emulador.

## Downloads

| Arquivo | Para quem |
|---|---|
| `MDLauncher-1.0.0-Setup.exe` | Instalador para Windows 10/11 (64 bits). Pergunta onde instalar e cria atalhos. |
| `MDLauncher-1.0.0-Portable.zip` | Versão portátil: é só extrair e abrir o `MDLauncher.exe`. |

## Novidades

### Biblioteca
- Grid de capas com fundo xadrez escuro inspirado nas caixas do Mega Drive.
- Janela sem barra de título: botões de fechar, minimizar e maximizar no canto superior esquerdo e o nome no
  canto direito.
- Controle deslizante no dock para aumentar ou diminuir as capas.
- Menu de botão direito: jogar, editar, mostrar no Explorer, buscar artes de novo e remover.

### Modal do jogo
- Hero estilo Steam no topo, com a capa sobreposta.
- Nome, data de lançamento, multiplayer, número de jogadores e desenvolvedora.
- **Contador de horas jogadas**, atualizado sozinho quando o emulador fecha, e a data da última vez que você jogou.
- Botão **Jogar** e botão **Tela cheia**, que adiciona o argumento certo do seu emulador.
- Botão **Editar**.

### Edição manual
- Edite nome, data, multiplayer, jogadores, desenvolvedora e tempo jogado.
- Troque o caminho da ROM/ZIP e defina um emulador ou argumentos só para aquele jogo.
- Escolha a fonte das artes (**SteamGridDB**, **IGDB** ou **Libretro**), busque, veja as miniaturas e clique para
  definir a capa e o hero. Também aceita imagens do computador.

### Capas e informações automáticas
- **SteamGridDB:** capa e hero.
- **IGDB:** data de lançamento, multiplayer, jogadores, desenvolvedora e artes extras.
- **Libretro Thumbnails:** box art e tela de título sem precisar de chave (fallback).

### Emuladores
- Funciona com qualquer emulador, usando um modelo de argumentos com `{rom}` e `{fullscreen}`.
- Presets automáticos de tela cheia para RetroArch, Kega Fusion, BlastEm, ares, Mednafen, Gens/GS e DGen.
- Opção de extrair a ROM do `.zip` antes de abrir, para emuladores que não leem zip.
- Opção de minimizar o launcher enquanto o jogo roda.

### ROMs
- Reconhece `.md`, `.gen`, `.smd`, `.bin`, `.68k`, `.sgd`, `.mdx` e `.zip` com a ROM dentro.
- Arquivos `.bin` são validados pelo cabeçalho `SEGA`.
- Nomes limpos automaticamente: `Castlevania - Bloodlines (USA).zip` vira **Castlevania: Bloodlines**.

### Dock
- ➕ Adicionar jogo manualmente
- 🎮 Abrir o emulador sem jogo
- 📁 Abrir a pasta de ROMs
- ▦ Tamanho das capas
- ⚙ Configurações

### Primeira execução
- Assistente em 3 passos: emulador → pasta de ROMs → chaves do SteamGridDB/IGDB. Depois disso, o launcher
  escaneia as ROMs e baixa as artes sozinho.

## Observações

- O executável não tem assinatura digital, então o SmartScreen pode avisar. Clique em **Mais informações →
  Executar assim mesmo**.
- O BlastEm usa `-f` como *alternância*: se o `blastem.cfg` já estiver em tela cheia, o botão faz o contrário.
- Seus dados ficam em `%APPDATA%\MDLauncher`. Desinstalar o app não apaga a biblioteca.
