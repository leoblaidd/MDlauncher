# MD Launcher 2.0.0

O MD Launcher foi reescrito em **Tauri 2 (Rust + HTML)**. A interface e as funções são as mesmas da 1.1, mas
o app ficou mais leve: o instalador ficou bem menor e o launcher abre mais rápido.

## Downloads

| Arquivo | Para quem |
|---|---|
| `MDLauncher-2.0.0-Setup.exe` | Instalador para Windows 10/11 (64 bits). Pergunta onde instalar e cria atalhos. |
| `MDLauncher-2.0.0-Portable.exe` | Versão portátil: um único `.exe`, sem instalar. |

## Novidades

### Nova base: Tauri + Rust
- Interface refeita em HTML/CSS com o mesmo visual da 1.1: fundo com grade, paleta prata com tons azulados,
  logo em caixa prata, botões no padrão do Windows e dock flutuante.
- O vidro do dock agora usa o desfoque nativo do navegador do Windows (WebView2). Ficou mais suave e acompanha
  as capas em tempo real.
- Parte de arquivos, rede e emulador reescrita em Rust.
- Instalador NSIS menor que o anterior. Ele pergunta onde instalar e instala só para o seu usuário, sem pedir
  permissão de administrador.

### Modal de edição
- As caixas **Buscar em** e de **resultados** agora têm uma seta e um ícone, deixando claro que dá para clicar e
  ver mais opções. Ao passar o mouse, elas mudam de cor. Os outros menus de escolha (como Multiplayer) também
  ganharam a seta.

### Mantido da 1.1
- Grid de capas até a borda, com rolagem suave.
- Pesquisa no dock (`Ctrl+F`, `Esc` limpa).
- Modal do jogo com hero, capa, data, multiplayer, desenvolvedora e contador de horas.
- Botões Jogar e Tela cheia, com presets para RetroArch, Kega Fusion, BlastEm, ares, Mednafen, Gens/GS e DGen.
- Edição manual com SteamGridDB, IGDB e Libretro.
- Assistente de primeira execução, menu de botão direito e a opção de minimizar o launcher enquanto o jogo roda.
- Ao sair do jogo, a janela volta exatamente como estava (maximizada ou não).

## Atualizando da 1.x
- Seus dados continuam em `%APPDATA%\MDLauncher`, no mesmo formato. A biblioteca, as capas e o tempo jogado
  aparecem normalmente na 2.0.
- O instalador é novo, então a 1.x continua instalada à parte. Depois de abrir a 2.0, desinstale o
  "MD Launcher" antigo em **Configurações do Windows → Aplicativos**. Isso não apaga seus dados.
- O executável não tem assinatura digital, então o SmartScreen pode avisar. Clique em **Mais informações →
  Executar assim mesmo**.
