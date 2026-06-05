# SETUP — Preparar este ambiente shell

> **Para o Claude Code:** este arquivo é um roteiro executável. Leia-o por
> inteiro junto com `manifest.json` (no mesmo diretório) antes de agir.
> NÃO copie o `.zshrc` de origem cru — ele foi gerado em **debian** e contém
> linhas específicas dessa plataforma que quebram em outros SOs. O fluxo é
> **bidirecional** (WSL↔macOS↔Linux): na Fase 4 você remove as linhas cuja
> plataforma não corresponde a ESTE destino.

## Contexto da origem
- SO de origem: **debian** (WSL: True)
- Framework: **oh-my-zsh**
- Tema ativo: **dracula-pro**
- Linhas específicas de plataforma encontradas: wsl_windows: 10, debian_binary_rename: 2

## Dois princípios que valem para TODAS as fases

1. **Idempotência — nunca quebre o que já existe.** Antes de instalar qualquer
   coisa, cheque se ela já está presente (`command -v <bin>`, ou o `verify` do
   item). Se já existe e funciona: **NÃO reinstale**, apenas registre
   "já presente (vX.Y)" e siga. Rodar este setup duas vezes deve ser seguro.
   Toda sobrescrita de config é precedida de backup (ver Fase 0.5 e princípio 3).
2. **Verificação — não confie, teste.** Toda ferramenta instalada (ou já
   presente) DEVE passar pelo seu smoke-test (tabela na Fase 6). Uma ferramenta
   só conta como "ok" se o comando de verificação retorna sucesso. Ao final,
   apresente um relatório com o status real de cada item.
3. **Backup antes de tudo — todo revert tem que ser possível.** NENHUMA
   alteração em config do alvo acontece antes do backup da Fase 0.5. Se algo
   der errado em qualquer fase, o usuário pode reverter (ver seção "Reverter").

## Sua tarefa, Claude

Prepare ESTA máquina para reproduzir o ambiente descrito em `manifest.json`,
**adaptando ao SO atual**, seguindo os dois princípios acima. PEÇA CONFIRMAÇÃO
antes de qualquer passo com `sudo`, download de tema pago, ou sobrescrita de
arquivo existente.

### Fase 0 — Detectar e preparar
1. Detecte o SO atual (`uname -s`; em Linux, cheque `/proc/version` para saber
   se é WSL). Alvos possíveis: **macOS**, **Linux nativo**, **Windows+WSL**.
   Em macOS, garanta o Homebrew (`brew`); se faltar, instale-o
   (https://brew.sh) com confirmação.
2. **zsh pode NÃO estar instalado** (WSL/Linux recém-criado costuma vir só com
   bash). Rode `command -v zsh`:
   - Se faltar, **PERGUNTE ao usuário se deseja instalar o zsh** e, com o aceite,
     instale conforme o SO:
     - macOS: `brew install zsh` (em geral já vem; confirme a versão).
     - Debian/Ubuntu/WSL: `sudo apt update && sudo apt install -y zsh`.
     - Fedora: `sudo dnf install -y zsh` · Arch: `sudo pacman -S zsh`.
   - Após instalar, **ofereça torná-lo o shell padrão** com
     `chsh -s "$(command -v zsh)"` (requer logout/login para valer; avise).
     Não force — alguns ambientes (containers, WSL gerenciado) preferem deixar
     no bash e só invocar `zsh`. PERGUNTE antes.
   - Se o usuário recusar instalar o zsh, PARE e explique que o restante do
     setup depende dele.
3. Garanta `git` (necessário para clonar plugins/tema).
4. **Inventário do destino:** para cada item de `cli_tools`, `version_managers`
   e `frameworks` do manifest, rode `command -v` / o `verify` correspondente e
   monte uma lista "já presente" × "faltando". Você só vai instalar o que falta.

### Fase 0.5 — BACKUP OBRIGATÓRIO (antes de qualquer alteração)
**Não prossiga sem isto.** Rode o script de backup do repo:

```sh
./scripts/backup.sh
```

Ele cria `~/.shell-config-backups/<timestamp>/` com cópia de todas as configs
existentes (`.zshrc`, `.zshenv`, `.p10k.zsh`, `~/.config/micro`, `glow`, etc.),
um `MANIFEST.txt` e um `restore.sh` auto-suficiente. **Guarde o caminho impresso
na última linha** — você vai citá-lo ao usuário no relatório final e ele é o
ponto de revert. A partir daqui, toda escrita de config é segura porque há um
snapshot para voltar.

### Fase 1 — Framework
Se o **oh-my-zsh** faltar, instale (veja `frameworks` no manifest).
Se já existir, pule. Ele deve vir ANTES de plugins e temas.

### Fase 2 — Ferramentas CLI (só as faltantes)
Para cada item de `cli_tools` marcado como FALTANDO na Fase 0, instale com o
comando do SO atual (`install.macos` no Mac, `install.debian` no Linux/apt,
`install.fallback` se necessário). Respeite o `note` — em especial **bat** e
**fd**, cujo nome de binário depende do destino:
- **Destino Debian/Ubuntu/WSL:** os binários instalam como `batcat`/`fdfind`.
  Para usar `bat`/`fd`, **ADICIONE** ao `.zshrc`: `alias bat="batcat"` e
  `alias fd="fdfind"` (mesmo que a origem não tivesse esses aliases — ex.: origem
  macOS).
- **Destino macOS/Fedora/Arch:** os binários já se chamam `bat`/`fd` — **NÃO**
  adicione esses aliases (e remova-os se vieram da origem).

Após cada instalação, rode imediatamente o `verify` daquele item; se falhar,
pare e investigue antes de seguir.

### Fase 3 — Plugins e tema do Oh My Zsh
- Para cada plugin de `omz_plugins`: se a pasta em
  `${ZSH_CUSTOM:-~/.oh-my-zsh/custom}/plugins/<nome>` já existir, pule; senão
  clone do `source`.
- Tema: se for `dracula-pro` (PAGO, não-público), PERGUNTE ao usuário se ele
  quer (a) copiar o arquivo do acesso comprado, ou (b) usar a alternativa
  gratuita `dracula`. Veja o `note` do tema no manifest.

### Fase 4 — Montar o .zshrc adaptado (BIDIRECIONAL)
Use `dotfiles/.zshrc` como BASE. As 12 linhas específicas de plataforma
(wsl_windows: 10, debian_binary_rename: 2) estão em `manifest.json → platform_specific_lines`, cada uma
com um campo `platform`. **Detecte o SO deste destino e remova as linhas cuja
`platform` NÃO corresponde a ele:**
- `platform: macos` (`/opt/homebrew`, `brew shellenv`, `pbcopy`, `pbpaste`,
  `open -a`, `defaults`, `/Users/`, `ls -G`, `LSCOLORS`) → **remover se o destino
  NÃO for macOS**.
- `platform: wsl_windows` (`/mnt/c`, `/mnt/wslg`, `PULSE_SERVER`, `MESA_D3D12`,
  `WARP_ENABLE_WAYLAND`, `powershell.exe`, `wslpath`) → **remover se o destino
  NÃO for WSL/Windows**.
- `platform: debian_binary_rename` (`alias bat="batcat"`, `alias fd="fdfind"`) →
  **manter/adicionar se o destino for Debian/Ubuntu; remover se for macOS/outros**
  (ver Fase 2).
- **Mantenha** o que é portável: aliases de produtividade (pnpm, git), hooks
  (`load-nvmrc`), prompt custom, e os blocos de version managers presentes aqui.
- O backup já foi feito na Fase 0.5; ainda assim confirme antes de sobrescrever.

### Fase 5 — Configs de apps
Copie os diretórios em `dotfiles/config/` para `~/.config/` (micro, glow, etc.),
sem sobrescrever sem perguntar.

### Fase 6 — VERIFICAÇÃO OBRIGATÓRIA (não pule)
Esta fase é o critério de sucesso. Execute, não presuma.

1. **Smoke-test de cada ferramenta** — rode cada comando abaixo e capture
   sucesso/falha. Para ferramentas de shell (nvm, etc.), rode dentro de
   `zsh -ic '<comando>'` para carregar o ambiente.

   | Ferramenta | Tipo | Comando de verificação |
   |---|---|---|
| `zoxide` | CLI | `zoxide --version` |
| `fzf` | CLI | `fzf --version` |
| `bat` | CLI | `bat --version || batcat --version` |
| `fd` | CLI | `fd --version || fdfind --version` |
| `eza` | CLI | `eza --version` |
| `glow` | CLI | `glow --version` |
| `micro` | CLI | `micro --version` |
| `kubectl` | CLI | `kubectl version --client` |
| `nvm` | version manager | `nvm --version  # rodar em shell interativa, após carregar o nvm` |
| `pyenv` | version manager | `pyenv --version` |
| `bun` | version manager | `bun --version` |
| `pnpm` | version manager | `pnpm --version` |
| `go` | version manager | `go version` |

2. **Carga limpa do shell** — rode `zsh -ic 'echo CARGA_OK'` e confirme que NÃO
   aparece nenhum "command not found", "no such file or directory" nem erro de
   plugin/tema. Se aparecer, rastreie a linha culpada no `.zshrc` e corrija.

3. **Plugins e tema ativos** — confirme que os plugins de `omz_plugins` existem
   em disco e que o tema configurado resolve para um arquivo `.zsh-theme`
   existente.

4. **Relatório final** — apresente ao usuário uma tabela com:
   `instalado agora` / `já estava presente` / `pulado` / **`FALHOU`** para cada
   item, mais o que precisa de ação manual (tema pago, login de ferramentas).
   Se houver qualquer `FALHOU`, o setup NÃO está completo — liste os próximos
   passos para resolver.

## Reverter (se algo der errado)
O backup da Fase 0.5 é o ponto de retorno. Para desfazer as mudanças de config:

```sh
# opção A — pelo repo:
./scripts/restore.sh ~/.shell-config-backups/<timestamp>

# opção B — direto pelo backup (auto-suficiente, não precisa do repo):
~/.shell-config-backups/<timestamp>/restore.sh
```

O `restore.sh` ainda salva o estado atual em `.pre-restore-<timestamp>/` antes
de sobrescrever — ou seja, o próprio revert é reversível. Depois de restaurar,
abra um novo shell (`exec zsh`). Observação: o restore reverte **arquivos de
config**; pacotes instalados (brew/apt) permanecem — desinstale-os à parte se
quiser, listando o que foi "instalado agora" no relatório final.

## Itens que exigem atenção manual
- **dracula-pro**: Tema PRO (PAGO) da Dracula. NÃO está em repo público. Você precisa baixar do seu acesso comprado em draculatheme.com/pro e copiar o arquivo .zsh-theme para ${ZSH_CUSTOM}/themes/. A versão gratuita equivalente é 'dracula' (git clone https://github.com/dracula/zsh). O Claude deve PERGUNTAR qual você quer usar na máquina nova.\n
