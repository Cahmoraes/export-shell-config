# dev-env-migrate

Leva seu ambiente de uma máquina para outra — **incluindo entre Linux/WSL e
macOS** — sem copiar arquivos manualmente e sem quebrar nada no destino. Cobre
duas frentes:

- **Shell** (`export.sh`): zsh + Oh My Zsh + ferramentas CLI + plugins + tema.
- **Claude Code** (`export-claude.sh`): plugins + marketplaces + language servers
  (LSP) + statusline + hooks + `settings.json` sanitizado.

## A ideia

Copiar o `.zshrc` cru não funciona entre SOs: ele contém aliases e paths
específicos de uma máquina (ex.: `alias bat="batcat"` só existe no Ubuntu;
`/mnt/c/...` só existe no WSL). Em vez de copiar texto, este projeto **gera um
inventário estruturado** do seu ambiente — quais ferramentas você usa e *de onde
elas vêm* — e deixa o Claude Code **reconstruir** o ambiente no destino,
adaptando ao SO de lá.

```
  MÁQUINA ORIGEM                   git push          MÁQUINA DESTINO
  "exporte meu ambiente"  ──────►  profile/  ──────►  "importe meu ambiente"
   (skill export-env)              ├ manifest.json     (skill import-env)
                                   ├ SETUP.md                 │
                                   └ dotfiles/                ▼
                                          Claude detecta o SO local, traduz o
                                          gerenciador e adapta as linhas por
                                          plataforma — em qualquer direção
```

O projeto tem **duas pontas**:

- **Export** (máquina de origem): `export.sh` escaneia o ambiente e gera o
  `profile/`. Roda uma vez, é determinístico, não altera nada.
- **Import** (máquina de destino): o Claude Code lê `profile/SETUP.md` e
  reconstrói o ambiente, usando `scripts/backup.sh` e `scripts/restore.sh` como
  rede de segurança.

---

## Início rápido

A forma recomendada é **conversar com o Claude Code**: duas skills versionadas no
repo (`export-env` e `import-env`) fazem todo o trabalho — você não roda scripts
à mão.

### 1. Na máquina de origem — exportar

Abra o Claude Code no repositório e diga:

> **"Exporte meu ambiente"**

A skill `export-env` gera os profiles (shell + Claude Code), confere que nenhum
segredo vazou e — com sua confirmação — faz commit e push.

_Alternativa manual:_
```bash
./export.sh && ./export-claude.sh
git add -A && git commit -m "snapshot do ambiente" && git push
```

### 2. Na máquina nova — importar

```bash
git clone <seu-repo> && cd dev-env-migrate
claude
```

E diga ao Claude:

> **"Importe meu ambiente"**

A skill `import-env` (que viaja no repo) mostra o plano via dry-run, faz backup,
instala e adapta o shell + a config do Claude Code ao SO local, e verifica tudo —
pedindo confirmação nos passos sensíveis. **Funciona em qualquer direção**
(WSL↔macOS↔Linux).

_Alternativa manual:_ rode `./scripts/dry-run.sh` para ver o plano e depois diga
ao Claude *"Leia profile/SETUP.md e prepare meu ambiente"* e *"Leia
profile/claude/CLAUDE_SETUP.md e reconstrua minha config do Claude Code"*.

---

## Referência dos scripts

Esta seção documenta cada componente executável: **o que faz**, **como funciona**
e **os comandos**. Serve tanto para você quanto para o Claude Code.

### Skills `export-env` e `import-env` (a camada Claude-driven)

São skills de projeto em `.claude/skills/`, carregadas pelo Claude Code ao abrir
o repo. Em vez de você rodar scripts, descreve a intenção e o Claude conduz:

- **`export-env`** (origem): roda os dois exports, faz a checagem de segredos,
  prepara o commit e — com sua confirmação — dá push. Dispare com *"exporte meu
  ambiente"*, *"atualize o snapshot e suba"*.
- **`import-env`** (destino): pré-checagem → dry-run → backup → executa o
  `SETUP.md` e o `CLAUDE_SETUP.md` adaptando ao SO local → verifica → oferece
  revert. Dispare com *"importe meu ambiente"*, *"prepare meu ambiente aqui"*.

As skills são uma casca fina sobre os scripts/roteiros abaixo — você pode usar
qualquer das duas camadas.

### `export.sh` — exportar o ambiente (origem)

```bash
./export.sh
```

- **Onde roda:** na máquina de origem (a que tem o ambiente que você quer levar).
- **O que faz:** wrapper fino que verifica `python3` e chama `lib/exporter.py`.
- **Efeito colateral:** nenhum no sistema — só **escreve** em `./profile/`. Não
  instala, não move ferramentas, não altera seu `.zshrc`.
- **Saída:** `profile/manifest.json`, `profile/SETUP.md` e `profile/dotfiles/`,
  além de um resumo no terminal (o que foi detectado e copiado).
- **Quando rodar de novo:** sempre que mudar suas ferramentas/configs e quiser
  atualizar o snapshot. É seguro rodar quantas vezes quiser (regenera o profile).

### `lib/exporter.py` — o motor do export

Chamado pelo `export.sh` (você normalmente não o roda direto). Em ordem:

1. Carrega a base de conhecimento `lib/catalog.json`.
2. Detecta o SO de origem e se é WSL.
3. Lê o `~/.zshrc` e extrai o **tema** (`ZSH_THEME`) e os **plugins** (`plugins=()`).
4. Detecta quais ferramentas/version managers estão **realmente instalados**
   (via `which` e checagem de paths como `~/.nvm`).
5. Marca as linhas do `.zshrc` que são **específicas de WSL/Windows** (`/mnt/c`,
   `PULSE_SERVER`, aliases `batcat`/`fdfind`, etc.) — elas viajam, mas vêm
   sinalizadas para o destino removê-las.
6. Copia os dotfiles para `profile/dotfiles/`.
7. Cruza "detectado" × "catálogo" e escreve `profile/manifest.json` e
   `profile/SETUP.md`.

### `export-claude.sh` — exportar a config do Claude Code (origem)

```bash
./export-claude.sh
```

- **Onde roda:** na máquina de origem, **depois** do `export.sh` (são
  independentes). Wrapper sobre `lib/claude_exporter.py`.
- **O que faz:** lê `~/.claude/` e gera `profile/claude/` com tudo o que define
  a *identidade* do seu Claude Code, **sem segredos**:
  - **plugins + marketplaces** de origem (para reinstalar via `claude plugin`);
  - **language servers** que cada plugin LSP exige e como instalar cada binário
    (TS via pnpm, pyright via pip/pnpm, gopls via go, rust-analyzer via cargo);
  - **pacotes node globais** (onde moram `typescript-language-server`,
    `typescript`, `@vtsls/language-server`);
  - `settings.json` **sanitizado** (paths do `$HOME` viram `${HOME}`, chaves de
    segredo removidas), `keybindings.json`, `statusline-command.sh`, o
    **`CLAUDE.md` global** (suas instruções para todos os projetos), e os
    diretórios `hooks/`, `agents/`, `skills/`, `commands/`.
- **O que NUNCA exporta:** `.credentials.json`, `.claude.json`, `history.jsonl`,
  `projects/`, `sessions/` (tokens, histórico e estado de sessão) e o
  **`CLAUDE.local.md`** (instruções pessoais/gitignored — não vão para um repo que
  pode ser público). Ver `sensitive_never_export` em `lib/claude_catalog.json`.
- **Sinaliza riscos:** flags de segurança (`bypassPermissions`) e hooks
  não-portáveis (`wsl-screenshot-cli`, `~/bin/claude-notify`) vão marcados no
  manifesto para o Claude tratar no destino.
- **Saída:** `profile/claude/claude-manifest.json`, `profile/claude/CLAUDE_SETUP.md`
  e `profile/claude/config/`.

No destino, diga ao Claude: *"Leia `profile/claude/CLAUDE_SETUP.md` e reconstrua
minha config do Claude Code."* Ele adiciona os marketplaces, instala os plugins,
garante os language servers no PATH, mescla o `settings.json` (perguntando antes
de aplicar as flags de segurança) e verifica tudo no final.

### `scripts/dry-run.sh` — simular o setup sem instalar nada (destino)

```bash
./scripts/dry-run.sh
```

- **Onde roda:** na máquina de destino, **antes** do setup real (opcional, mas
  recomendado).
- **O que faz:** lê o `profile/manifest.json`, detecta o SO atual e mostra o
  **plano de execução** em modo read-only — sem instalar nem alterar nada:
  - presença de `zsh`, `git` e Oh My Zsh;
  - para cada ferramenta: `● já presente` (será pulada) ou `○ faltando` (com o
    comando de instalação que *seria* usado neste SO);
  - quais plugins já estão em disco e o status do tema (inclusive se exige ação
    manual, como o `dracula-pro` pago);
  - o **plano de adaptação** `origem → este destino`: quais linhas do `.zshrc`
    MANTER × REMOVER (por plataforma) e se há aliases `bat`/`fd` a ADICIONAR;
  - um resumo: quantas ferramentas já existem × faltam.
- **Por que existe:** confere se a detecção e o plano batem com a realidade do
  alvo antes de mexer no sistema. Usa a mesma lógica de detecção do exporter
  (binário, alias do Debian como `batcat`/`fdfind`, ou path como `~/.nvm`).
- **Requer:** `python3` (só para o diagnóstico; o setup real é feito pelo Claude).

### `scripts/backup.sh` — snapshot antes de alterar (destino)

```bash
./scripts/backup.sh
```

- **Onde roda:** na máquina de destino, **antes** de qualquer alteração. O
  `SETUP.md` obriga isso na Fase 0.5.
- **O que faz:** copia todas as configs existentes do alvo para
  `~/.shell-config-backups/<timestamp>/`, preservando a estrutura relativa ao
  `$HOME`. Configs cobertas: `.zshrc`, `.zshenv`, `.p10k.zsh`, `.fzf.zsh`,
  `~/.config/micro`, `~/.config/glow`, `~/.config/starship.toml`.
- **O que gera dentro da pasta de backup:**
  - cópia de cada arquivo/diretório salvo;
  - `MANIFEST.txt` — a lista do que foi salvo (usada pelo restore);
  - `restore.sh` — uma **cópia do antídoto**, para reverter mesmo sem o repo.
- **Saída:** a **última linha** impressa é o caminho absoluto do backup. Guarde-o.
- **Portável:** funciona em macOS, Linux e WSL (bash + utilitários POSIX).

### `scripts/restore.sh` — reverter para um snapshot (destino)

```bash
# opção A — a partir do repo, apontando o backup:
./scripts/restore.sh ~/.shell-config-backups/<timestamp>

# opção B — auto-suficiente, de dentro do próprio backup (não precisa do repo):
~/.shell-config-backups/<timestamp>/restore.sh
```

- **Onde roda:** na máquina de destino, quando você quer desfazer as mudanças.
- **O que faz:** lê o `MANIFEST.txt` do backup e restaura cada arquivo para sua
  posição original no `$HOME`.
- **Segurança extra:** antes de sobrescrever, salva o estado atual em
  `<backup>/.pre-restore-<timestamp>/`. Ou seja, **o próprio revert é
  reversível** — se você restaurar o backup errado, ainda pode voltar.
- **Sem argumento:** se chamado sem caminho, usa a pasta onde o próprio script
  está (por isso a cópia dentro do backup funciona sozinha).
- **Escopo (importante):** reverte **arquivos de config**, não pacotes
  instalados. Ferramentas instaladas via `brew`/`apt` permanecem; desinstale-as
  à parte se quiser (o relatório final do Claude lista o que foi "instalado agora").
- **Depois de restaurar:** abra um novo shell (`exec zsh`) para aplicar.

### `profile/SETUP.md` — o roteiro que o Claude executa (destino)

Não é um script, mas **é executável pelo Claude**: um roteiro em fases que ele
segue na máquina nova. Resumo das fases:

| Fase | O que acontece |
|---|---|
| 0 | Detecta o SO; instala `zsh` se faltar (pergunta antes); inventaria o que já existe no destino. |
| 0.5 | **Backup obrigatório** (`scripts/backup.sh`) antes de qualquer alteração. |
| 1 | Instala o Oh My Zsh se faltar. |
| 2 | Instala só as ferramentas CLI faltantes, com o gerenciador do SO. |
| 3 | Clona plugins; resolve o tema (pergunta no caso do `dracula-pro` pago). |
| 4 | Monta o `.zshrc` adaptado: remove as linhas cuja plataforma ≠ destino e ajusta `bat`/`fd` (bidirecional). |
| 5 | Copia as configs de apps (`~/.config/...`). |
| 6 | **Verificação obrigatória**: smoke-test de cada ferramenta + relatório `instalado`/`já presente`/`pulado`/`FALHOU`. |

Os três princípios que o Claude segue em todas as fases: **idempotência** (não
quebrar o que já existe), **verificação** (testar, não presumir) e **backup**
(todo revert tem que ser possível).

---

## Garantias do processo

- **Cross-platform bidirecional:** funciona nos dois sentidos (WSL→macOS **e**
  macOS→WSL). Cada linha específica de plataforma é rotulada
  (`macos`/`wsl_windows`/`debian_binary_rename`); no destino, o Claude remove as
  que não pertencem ao SO de lá, ajusta os aliases `bat`/`fd` conforme o destino
  (adiciona no Debian, remove no macOS) e usa `brew`/`apt`/`dnf`/`pacman`.
- **Não precisa ter zsh no destino:** se faltar, o Claude pergunta e instala (e
  oferece torná-lo o shell padrão).
- **Idempotente:** o que já existe é detectado e pulado — nada é reinstalado ou
  quebrado. Rodar o setup duas vezes é seguro.
- **Verificado:** cada ferramenta passa por um smoke-test (`zoxide --version`,
  `glow --version`, etc.) e o Claude entrega um relatório de status real.
- **Reversível:** backup automático antes de alterar, com revert auto-suficiente.

---

## Estrutura do repositório

| Caminho | Papel |
|---|---|
| `CLAUDE.md` | Contexto do projeto para o Claude Code (comandos, arquitetura, gotchas). |
| `.claude/skills/export-env/` | Skill: exporta o ambiente e publica (origem). |
| `.claude/skills/import-env/` | Skill: reconstrói o ambiente no destino, com backup e verificação. |
| `export.sh` | Entry point do **export de shell** (origem). Wrapper sobre o exporter. |
| `lib/catalog.json` | Base de conhecimento de ferramentas + `platform_specific_patterns` (por SO). **Edite aqui para adicionar ferramentas.** |
| `lib/exporter.py` | Motor do export de shell: detecção, classificação por plataforma, geração do profile. |
| `export-claude.sh` | Entry point do **export do Claude Code** (origem). |
| `lib/claude_catalog.json` | Conhecimento: language servers por plugin LSP + regras de sanitização/segurança. |
| `lib/claude_exporter.py` | Motor do export do Claude: plugins, LSP, sanitização de segredos, geração de `profile/claude/`. |
| `scripts/dry-run.sh` · `scripts/dryrun.py` | **Import:** simula o setup (read-only) e mostra o plano de adaptação. |
| `scripts/backup.sh` | **Import:** snapshot das configs do alvo antes de alterar. |
| `scripts/restore.sh` | **Import:** reverte para um snapshot (auto-suficiente). |
| `tests/test_exporter.py` | Testes do export de shell + classificação por plataforma. |
| `tests/test_claude_exporter.py` | Testes do export do Claude (foco em sanitização de segredos). |
| `tests/test_dryrun.py` | Testes do plano de adaptação (regra bidirecional manter×remover). |
| `tests/test_integration.py` | Teste de integração: os dois fluxos completos (WSL↔macOS) ponta a ponta. |
| `profile/` | Saída do export de shell (commitada — é o que viaja). |
| `profile/claude/` | Saída do export do Claude Code (manifest + CLAUDE_SETUP.md + config/). |

---

## Adicionar uma ferramenta nova

Tudo é dado, não código. Edite `lib/catalog.json` e adicione uma entrada em
`cli_tools`:

```json
"ripgrep": {
  "describe": "grep recursivo ultrarrápido",
  "detect": "rg",
  "source": "https://github.com/BurntSushi/ripgrep",
  "verify": "rg --version",
  "install": {
    "macos": "brew install ripgrep",
    "debian": "sudo apt install -y ripgrep"
  }
}
```

Campos: `detect` (nome do binário procurado), `verify` (smoke-test) e `install`
(comando por SO: `macos`/`debian`/`fallback`). Rode `./export.sh` de novo — a
ferramenta entra no manifest e na tabela de verificação automaticamente.

---

## Desenvolvimento

Os testes de regressão do exporter rodam só com a stdlib do Python (sem
`pip install`):

```bash
python3 -m unittest discover -s tests -p "test_*.py"
```

Cobrem, em camadas:
- **unitários** — export de shell (parsing do `.zshrc`, detecção, classificação
  por plataforma), export do Claude (**sanitização de segredos**, language
  servers) e o **plano de adaptação** bidirecional (`test_dryrun`);
- **integração** (`test_integration`) — os **dois fluxos completos** ponta a
  ponta: WSL→macOS e macOS→WSL (export → manifest → import → `.zshrc` adaptado),
  mais o round-trip de sanitização e de backup/restore.

Rode-os após qualquer mudança em `lib/`, `scripts/dryrun.py` ou nos catálogos.

## Segurança

- O `.zsh_history` **nunca** é exportado (está no `.gitignore`).
- Revise `profile/dotfiles/.zshrc` antes do `git push` se você guarda segredos no
  `.zshrc` — o ideal é movê-los para um `~/.zshrc.local` fora do versionamento.
- O export **não executa** nada do seu ambiente: só lê e copia.

**Export do Claude Code** (`export-claude.sh`):
- **Nunca** copia `.credentials.json`, `.claude.json`, `history.jsonl`,
  `projects/` nem `sessions/` (tokens OAuth, histórico e estado de sessão). No
  destino você faz login normalmente.
- O **`CLAUDE.md` global** (instruções compartilháveis) é exportado; o
  **`CLAUDE.local.md`** (pessoal/gitignored) **nunca** é — o repo pode ser público.
- O `settings.json` é **sanitizado**: chaves que casam `api_key|token|secret|
  password|credential` são removidas e os paths do seu `$HOME` viram `${HOME}`.
- Os hashes `gitCommitSha` no manifesto são SHAs de commit **públicos** do
  GitHub (fixam a versão exata de cada plugin) — não são segredos.
- Ainda assim, revise `profile/claude/config/settings.json` antes do push se você
  tiver adicionado configs incomuns.
