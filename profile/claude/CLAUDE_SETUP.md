# CLAUDE_SETUP — Reconstruir a config do Claude Code

> **Para o Claude Code:** este é um roteiro executável. Leia junto com
> `claude-manifest.json` (mesmo diretório). O objetivo é reproduzir a config
> GLOBAL do Claude desta origem nesta máquina, **adaptando ao SO** e **sem**
> aplicar segredos (eles não foram exportados — você fará login normalmente).

## Princípios
1. **Backup antes de tudo.** Faça cópia de `~/.claude/settings.json`,
   `keybindings.json`, `statusline-command.sh` e dos diretórios `hooks/`,
   `agents/`, `skills/` para `~/.claude/<arquivo>.bak-<data>` antes de sobrescrever.
2. **Idempotência (tudo repetível sem quebrar).** Cheque antes de criar:
   `claude plugin list` antes de instalar plugin; `claude plugin marketplace list`
   antes de adicionar marketplace; `command -v <binário>` antes de instalar
   language server. Pule o que já existe (registre "já presente"). Para
   settings/hooks/skills: faça MERGE com backup, nunca sobrescreva cego. Rodar
   este setup duas vezes deve ser seguro.
3. **Verificação.** Ao final, confirme plugins ativos e cada language server
   respondendo `--version`.
4. **Segurança em primeiro lugar.** NÃO aplique as `security_flags` (abaixo) sem
   PERGUNTAR ao usuário.

## Fase 0 — Pré-requisitos
- `claude` (Claude Code) instalado e logado (o login é manual — segredos não vêm
  no profile).
- Gerenciadores conforme os language servers necessários: `pnpm`/`npm` (TS),
  `pip`/`pnpm` (pyright), `go` (gopls), `rustup`/`cargo` (rust-analyzer).

## Fase 1 — Marketplaces
Rode `claude plugin marketplace list` primeiro; adicione só os que faltam:
- `claude-plugins-official` → `anthropics/claude-plugins-official` (`claude plugin marketplace add anthropics/claude-plugins-official`)
- `caveman` → `JuliusBrussee/caveman` (`claude plugin marketplace add JuliusBrussee/caveman`)
- `context-mode` → `mksglu/context-mode` (`claude plugin marketplace add mksglu/context-mode`)
- `claude-code-warp` → `warpdotdev/claude-code-warp` (`claude plugin marketplace add warpdotdev/claude-code-warp`)

## Fase 2 — Plugins (11 habilitados)
Para cada plugin em `manifest.plugins`, rode `claude plugin install <name>` (o
`<name>` já vem como `plugin@marketplace`). Respeite o campo `enabled`:
- `enabled: false` → instale e depois `claude plugin disable <name>` (ou não instale).
- `enabled: ["X"]` → habilitado com escopo/arg específico; replique o valor em
  `enabledPlugins` do settings.

## Fase 3 — Language servers (o que faz os plugins LSP funcionarem)
Cada plugin LSP é só a integração; o BINÁRIO do language server precisa existir
no PATH. Regras:

- **Idempotência:** antes de instalar, rode `command -v <binário>`. Se já existe,
  PULE (registre "já presente (vX)"). Só instale o que falta.
- **Gerenciador de node (TypeScript e pyright):** NÃO assuma pnpm. Detecte o que
  a máquina tem e use-o — **prefira `pnpm` se `command -v pnpm` existir; senão
  use `npm`**. O manifesto traz os dois comandos em `install.pnpm` e
  `install.npm`. Se faltarem ambos, habilite um com `corepack enable` (traz o
  pnpm) ou instale o Node (traz o npm) antes.
- **Não-node:** `gopls` via `go install`; `rust-analyzer` via `rustup`/`cargo`.

| Language server | Plugins | Binário | Gerenciadores | Estava na origem? |
|---|---|---|---|---|
| `typescript-language-server` | typescript-lsp@claude-plugins-official | `typescript-language-server` | pnpm, npm | sim |
| `vtsls` | typescript-lsp@claude-plugins-official | `vtsls` | pnpm, npm | sim |
| `pyright` | pyright-lsp@claude-plugins-official | `pyright-langserver` | pnpm, npm, pip | sim |
| `gopls` | gopls-lsp@claude-plugins-official | `gopls` | go | sim |
| `rust-analyzer` | rust-analyzer-lsp@claude-plugins-official | `rust-analyzer` | rustup, cargo | sim |

A coluna "Gerenciadores" lista as chaves disponíveis em
`manifest.language_servers[].install` — escolha a que existe nesta máquina.
As libs de TS na origem vinham de pacotes node globais
(`manifest.global_node_packages`: `typescript-language-server`, `typescript`,
`@vtsls/language-server`). Replique os relevantes com **pnpm OU npm**, conforme
o disponível. Exemplos equivalentes:
- pnpm: `pnpm add -g typescript-language-server typescript`
- npm:  `npm install -g typescript-language-server typescript`

## Fase 4 — settings.json (com cuidado)
Mescle `config/settings.json` no `~/.claude/settings.json`. Os paths usam
`${HOME}` — confirme que expandem nesta máquina.

**Pergunte ao usuário antes de aplicar estas flags de segurança:**
  - `permissions.defaultMode` = `"bypassPermissions"`
  - `skipDangerousModePermissionPrompt` = `true`
  - `skipAutoPermissionPrompt` = `true`

  Elas desativam confirmações de permissão. Numa máquina nova/compartilhada o
  usuário pode NÃO querer isso.

## Fase 5 — Hooks, statusline, keybindings, agents, skills
Copie de `config/` para `~/.claude/`. **Atenção a trechos específicos de
plataforma** encontrados: `wsl-screenshot-cli`, `~/bin/claude-notify`

Detecte o SO deste destino e trate cada marcador conforme a plataforma a que
pertence (regra simétrica — vale nos dois sentidos):
- **WSL/Windows-only** (`wsl-screenshot-cli`, `.ps1`, `/mnt/c`, `/mnt/wslg`,
  `powershell.exe`, `wslpath`) → se o destino NÃO for WSL/Windows, **remova ou
  condicione** o hook.
- **macOS-only** (`pbcopy`, `pbpaste`, `osascript`, `/opt/homebrew`, `open -a`,
  `defaults write`, `/Users/`) → se o destino NÃO for macOS, **remova ou
  condicione** o hook.
- **Scripts locais** (`~/bin/claude-notify`) → se não existir nesta máquina,
  recrie-o ou remova o hook que o chama.

## Fase 6 — Verificação
1. `claude plugin list` mostra os plugins esperados (habilitados/desabilitados).
2. Cada language server da Fase 3 responde: `typescript-language-server --version`,
   `pyright-langserver --version`, `gopls version`, `rust-analyzer --version`.
3. A statusline aparece ao abrir o Claude Code (sem erro de path).
4. Relatório final: plugins `instalado`/`já presente`/`pulado`, language servers
   `ok`/`FALHOU`, e o que exigiu decisão manual (security flags, hooks WSL).
