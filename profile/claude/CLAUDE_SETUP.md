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
- Toolchain das dependências de binário dos hooks (Fase 3.5), se houver — ex.:
  `go` para o `token-crunch`.

## Fase 1 — Marketplaces
Rode `claude plugin marketplace list` primeiro; adicione só os que faltam:
- `claude-plugins-official` → `anthropics/claude-plugins-official` (`claude plugin marketplace add anthropics/claude-plugins-official`)
- `caveman` → `JuliusBrussee/caveman` (`claude plugin marketplace add JuliusBrussee/caveman`)
- `context-mode` → `mksglu/context-mode` (`claude plugin marketplace add mksglu/context-mode`)
- `claude-code-warp` → `warpdotdev/claude-code-warp` (`claude plugin marketplace add warpdotdev/claude-code-warp`)
- `headroom-marketplace` → `chopratejas/headroom` (`claude plugin marketplace add chopratejas/headroom`)
- `chrome-devtools-plugins` → `ChromeDevTools/chrome-devtools-mcp` (`claude plugin marketplace add ChromeDevTools/chrome-devtools-mcp`)

## Fase 2 — Plugins (12 habilitados)
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

Hooks que chamam binários externos só funcionam se o binário existir no PATH —
garanta que as dependências da Fase 3.5 foram instaladas antes de confiar nesses
hooks.

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

## Fase 6 — Headroom (proxy de compressão de tokens)

O `settings.json` já inclui `ENABLE_TOOL_SEARCH=true`. Essa flag é necessária para
que o MCP Tool Search funcione mesmo com o proxy headroom ativo — sem ela, todos os
MCP tools carregam eager e o baseline da sessão cresce ~16k tokens por sessão.

### 6a — Instalar/atualizar headroom
```bash
pip install "headroom-ai[all]"   # ou: pip install --upgrade "headroom-ai[all]"
```

### 6b — Subir o proxy como serviço persistente
```bash
# Configura apenas claude e codex (sem copilot — requer BYOK não disponível)
headroom install apply --providers manual --target claude --target codex
headroom install start
# Verifique pelo HEALTH, não por `headroom install status`: no macOS ≥0.24 o
# status usa `launchctl kickstart` e reporta "stopped" mesmo com o proxy saudável.
# Fallback macOS — se `start` falhar (exit 113, GUI domain inacessível numa sessão
# não-interativa), faça o bootstrap explícito do launchd e cheque de novo:
curl -fsS http://127.0.0.1:8787/health >/dev/null && echo "proxy healthy" ||   launchctl bootstrap "gui/$(id -u)" ~/Library/LaunchAgents/com.headroom.*.plist 2>/dev/null
sleep 2
curl -fsS http://127.0.0.1:8787/health >/dev/null && echo "proxy healthy"   || echo "proxy NÃO subiu — inspecione os logs do headroom"
```

### 6b-bis — Afinar o manifest do deploy (intercept + memória + telemetria)
Três ajustes vivem só no manifest do deploy e **NÃO** são gerados por
`headroom install apply` (o planner não os escreve) — por isso precisam ser
aplicados à mão aqui e persistidos no manifest do profile `default`:

1. **`--intercept-tool-results`** (em `proxy_args`): faz o proxy substituir Reads
   grandes de código (`.ts/.py/.rs` > 500 chars) por um outline ast-grep (só
   assinaturas de nível superior); o corpo só vai ao modelo quando se pede um
   range específico. É a maior fonte de economia para um agente de código
   (reduz tokens de reads em ~60-80%). A antiga flag `--compress-superseded-reads`
   **não existe mais** nesta versão — não a use.
2. **`memory_enabled: true`** — memória cross-agent com embedder **local** (default
   quando habilitada; sem custo de API). O `memory.db` é criado no primeiro uso
   em `memory_db_path` e é estado de runtime: **não viaja** no profile (como o
   `learn`). Aqui só liga-se a *config*.
3. **`telemetry_enabled: false`** — desliga telemetria (alinhado ao RTK).

⚠️ Se você rodar `headroom install apply` no futuro, ele **sobrescreve** o manifest
e remove estes três ajustes — basta reaplicar este bloco.
```bash
MANIFEST="$HOME/.headroom/deploy/default/manifest.json"   # ajuste o profile se != default
python3 - "$MANIFEST" <<'PY'
import json, sys
p = sys.argv[1]
m = json.load(open(p))
changed = []
args = m.setdefault("proxy_args", [])
if "--intercept-tool-results" not in args:
    args.append("--intercept-tool-results")
    changed.append("intercept-tool-results")
if m.get("memory_enabled") is not True:
    m["memory_enabled"] = True
    changed.append("memory_enabled=true")
if m.get("telemetry_enabled") is not False:
    m["telemetry_enabled"] = False
    changed.append("telemetry_enabled=false")
if changed:
    json.dump(m, open(p, "w"), indent=2)
    print("aplicado:", ", ".join(changed))
else:
    print("nada a mudar (já afinado)")
PY

# ⚠️ NÃO reinicie o headroom diretamente nesta sessão: se este Claude Code já
# estiver roteando pelo proxy (ANTHROPIC_BASE_URL → 127.0.0.1:8787), um
# `headroom install stop` síncrono mata o backend da PRÓPRIA sessão e ela
# congela antes de o `start` rodar (precisaria de outra ferramenta para subir).
# Por isso o reinício roda DESACOPLADO, em background imune a SIGHUP — o `start`
# acontece mesmo que o socket do cliente caia no intervalo:
nohup sh -c 'headroom install stop; sleep 2; headroom install start' >/tmp/headroom-restart.log 2>&1 &
sleep 4   # dá tempo de o proxy voltar antes de checar (veja /tmp/headroom-restart.log se falhar)
# Verifique pelo /health (não por `headroom install status` — quirk do macOS ≥0.24):
curl -fsS http://127.0.0.1:8787/health >/dev/null && echo "proxy healthy"   || echo "proxy não respondeu — veja /tmp/headroom-restart.log"
```
Verifique o efeito no manifest do profile `default`: `proxy_args` deve conter
`--intercept-tool-results`, `memory_enabled` deve ser `true` e `telemetry_enabled`
`false`. A flag também deve aparecer em `headroom proxy --help | grep intercept`.

### 6c — Integrar com o Claude Code
```bash
headroom init claude   # escreve ANTHROPIC_BASE_URL em ~/.claude/settings.local.json + hooks
```

### 6d — Registrar MCPs (headroom + serena)
O `headroom mcp` e a `serena` ficam em `~/.claude.json` (não viajam no profile).
Forma canônica (≥0.25): `headroom mcp install` registra o CCR no Claude Code **e**
no Codex de uma vez, ativando as ferramentas `mcp__headroom__headroom_compress`,
`headroom_retrieve` e `headroom_stats` (fluxo Compress-Cache-Retrieve):
```bash
headroom mcp install   # idempotente: já registrado → "already registered"
# serena não é gerida pelo headroom — registre à parte:
claude mcp add serena -- uvx --from git+https://github.com/oraios/serena \
  serena start-mcp-server --project-from-cwd --context claude-code
```

> **Nota:** `ANTHROPIC_BASE_URL=http://127.0.0.1:8787` é gerenciado pelo
> `headroom init claude` e **não viaja no profile** — cada destino configura via
> sua própria instalação do headroom. Não o adicione manualmente.

## Fase 7 — Verificação final
1. `claude plugin list` mostra os plugins esperados (habilitados/desabilitados).
2. Cada language server da Fase 3 responde: `typescript-language-server --version`,
   `pyright-langserver --version`, `gopls version`, `rust-analyzer --version`.
3. A statusline aparece ao abrir o Claude Code (sem erro de path).
4. `/context` em nova sessão: MCP tools como **on-demand (0 tokens)**, baseline < 30k.
5. Relatório final: plugins `instalado`/`já presente`/`pulado`, language servers
   `ok`/`FALHOU`, e o que exigiu decisão manual (security flags, hooks WSL).
