#!/usr/bin/env python3
"""
claude_exporter.py — exporta a configuração GLOBAL do Claude Code para um profile
portável, para ser reconstruída em outra máquina pelo próprio Claude.

Exporta (sem segredos):
  - plugins instalados + marketplaces de origem (para reinstalar via `claude plugin`)
  - quais language servers cada plugin LSP exige + como instalá-los
  - quais binários os hooks do settings.json exigem + como instalá-los
  - pacotes node globais (pnpm/npm) — onde moram as libs de TS LSP
  - settings.json SANITIZADO (paths do $HOME viram ${HOME}; segredos removidos)
  - statusline, keybindings, hooks, agents, skills (config/identidade)

NUNCA exporta: .credentials.json, .claude.json, history, projects, sessions
(ver 'sensitive_never_export' no catálogo).

Saída: profile/claude/  (manifest + CLAUDE_SETUP.md + config/).
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

HOME = Path.home()
CLAUDE_DIR = HOME / ".claude"
REPO = Path(__file__).resolve().parent.parent
CATALOG_PATH = REPO / "lib" / "claude_catalog.json"
OUT = REPO / "profile" / "claude"
CONFIG_OUT = OUT / "config"

HOME_STR = str(HOME)
SECRET_KEY_RE = re.compile(r"(api[_-]?key|token|secret|password|credential)", re.I)


def load_catalog() -> dict:
    with open(CATALOG_PATH, encoding="utf-8") as f:
        return json.load(f)


def read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def which(name: str):
    return shutil.which(name)


def sanitize_value(v):
    """Substitui o $HOME literal por ${HOME} em qualquer string, recursivamente."""
    if isinstance(v, str):
        return v.replace(HOME_STR, "${HOME}")
    if isinstance(v, list):
        return [sanitize_value(x) for x in v]
    if isinstance(v, dict):
        return {k: sanitize_value(x) for k, x in v.items()}
    return v


def sanitize_settings(settings: dict):
    """Remove segredos e generaliza paths. Retorna (settings_limpo, segredos_removidos)."""
    removed = []

    # Chaves do campo `env` gerenciadas por ferramentas externas em cada máquina:
    # não devem viajar no profile (cada destino reconfigura via headroom init, etc.)
    _env_machine_specific = {"ANTHROPIC_BASE_URL", "OPENAI_BASE_URL", "COPILOT_PROVIDER_BASE_URL", "COPILOT_PROVIDER_TYPE"}

    def clean(obj, trail=""):
        if isinstance(obj, dict):
            out = {}
            for k, val in obj.items():
                if SECRET_KEY_RE.search(k):
                    removed.append(f"{trail}.{k}".lstrip("."))
                    continue
                if trail.lstrip(".") == "env" and k in _env_machine_specific:
                    removed.append(f"env.{k}")
                    continue
                out[k] = clean(val, f"{trail}.{k}")
            return out
        if isinstance(obj, list):
            return [clean(x, trail) for x in obj]
        return obj

    cleaned = clean(settings)
    return sanitize_value(cleaned), removed


def detect_language_servers(catalog: dict, enabled_plugins: dict) -> list:
    """Para cada plugin LSP habilitado, descobre o language server e seu status."""
    enabled = {name for name, val in enabled_plugins.items() if val is not False}
    result = []
    for ls_name, meta in catalog["language_servers"].items():
        relevant = [p for p in meta["for_plugins"] if p in enabled]
        if not relevant:
            continue
        binary = meta["binary"]
        found = which(binary)
        result.append({
            "language_server": ls_name,
            "binary": binary,
            "for_plugins": relevant,
            "describe": meta.get("describe"),
            "installed_on_source": bool(found),
            "source_path": found,
            "install": meta["install"],
        })
    return result


def detect_hook_dependencies(catalog: dict, settings: dict) -> list:
    """Acha binários externos que os HOOKS do settings.json invocam.

    Análogo a detect_language_servers, mas para hooks: inclui só as dependências
    cujo comando aparece de fato nos hooks (data-driven — o catálogo pode listar
    vários binários conhecidos; o export traz só os realmente usados aqui). Os
    hooks em si já viajam via config/settings.json; aqui só registramos qual
    binário o destino precisa instalar no PATH para o hook não falhar.
    """
    deps = catalog.get("hook_dependencies", {})
    hooks_text = json.dumps(settings.get("hooks", {}), ensure_ascii=False)
    result = []
    for name, meta in deps.items():
        if name.startswith("_") or not isinstance(meta, dict):
            continue
        marker = meta.get("detect_in_hooks", name)
        if marker not in hooks_text:
            continue
        binary = meta["binary"]
        found = which(binary)
        result.append({
            "name": name,
            "binary": binary,
            "describe": meta.get("describe"),
            "source": meta.get("source"),
            "verify": meta.get("verify"),
            "installed_on_source": bool(found),
            "source_path": found,
            "install": meta["install"],
            "install_note": meta.get("install_note"),
            "post_install": meta.get("post_install"),
        })
    return result


def detect_global_node_packages() -> dict:
    """Lê pacotes globais de pnpm e npm (onde estão as libs de TS LSP)."""
    out = {"pnpm": [], "npm": []}

    def run(cmd):
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            return r.stdout
        except (OSError, subprocess.SubprocessError):
            return ""

    # pnpm ls -g --json → lista com {dependencies: {name: {version}}}
    raw = run(["pnpm", "ls", "-g", "--depth=0", "--json"])
    try:
        data = json.loads(raw) if raw.strip() else []
        if isinstance(data, list):
            data = data[0] if data else {}
        deps = data.get("dependencies", {}) if isinstance(data, dict) else {}
        out["pnpm"] = sorted(f"{n}@{d.get('version', '?')}" for n, d in deps.items())
    except (ValueError, AttributeError, KeyError, IndexError):
        pass

    raw = run(["npm", "ls", "-g", "--depth=0", "--json"])
    try:
        deps = json.loads(raw).get("dependencies", {}) if raw.strip() else {}
        out["npm"] = sorted(f"{n}@{d.get('version', '?')}" for n, d in deps.items())
    except (ValueError, AttributeError, KeyError):
        pass

    return out


def scan_non_portable(settings: dict, catalog: dict) -> list:
    """Acha trechos de settings/hooks específicos de plataforma (qualquer uma).

    Varre todos os grupos de marcadores (wsl_windows, macos, local_scripts), não
    só WSL — o destino decide o que condicionar conforme o próprio SO.
    """
    text = json.dumps(settings, ensure_ascii=False)
    hits = []
    for group, pats in catalog["non_portable_markers"].items():
        if group.startswith("_") or not isinstance(pats, list):
            continue
        for pat in pats:
            if pat in text and pat not in hits:
                hits.append(pat)
    return hits


def find_security_flags(settings: dict, catalog: dict) -> dict:
    """Coleta os valores das chaves sensíveis de segurança presentes em settings."""
    found = {}
    for dotted in catalog["security_flags"]["keys"]:
        node = settings
        ok = True
        for part in dotted.split("."):
            if isinstance(node, dict) and part in node:
                node = node[part]
            else:
                ok = False
                break
        if ok:
            found[dotted] = node
    return found


def copy_text_sanitized(src: Path, dst: Path):
    """Copia um arquivo de texto trocando o $HOME literal por ${HOME}."""
    try:
        text = src.read_text(encoding="utf-8")
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(text.replace(HOME_STR, "${HOME}"), encoding="utf-8")
        return True
    except (OSError, UnicodeDecodeError):
        # Binário ou ilegível: copia cru.
        shutil.copy2(src, dst)
        return True


def copy_claude_config(catalog: dict, sanitized_settings: dict) -> list:
    """Copia config/identidade para profile/claude/config/, pulando segredos."""
    if OUT.exists():
        shutil.rmtree(OUT)
    CONFIG_OUT.mkdir(parents=True, exist_ok=True)
    copied = []

    # settings.json já sanitizado, escrito direto.
    (CONFIG_OUT / "settings.json").write_text(
        json.dumps(sanitized_settings, indent=2, ensure_ascii=False), encoding="utf-8")
    copied.append("settings.json")

    cfg = catalog["config_to_export"]
    for name in cfg["files"]:
        if name == "settings.json":
            continue
        src = CLAUDE_DIR / name
        if src.exists() and src.is_file():
            copy_text_sanitized(src, CONFIG_OUT / name)
            copied.append(name)

    ignore = shutil.ignore_patterns("node_modules", ".git", "*.log", ".DS_Store")
    for name in cfg["dirs"]:
        src = CLAUDE_DIR / name
        if not src.exists() or not src.is_dir():
            continue
        dst = CONFIG_OUT / name
        shutil.copytree(src, dst, dirs_exist_ok=True, ignore=ignore)
        # Sanitiza paths nos arquivos de texto copiados.
        for f in dst.rglob("*"):
            if f.is_file():
                try:
                    t = f.read_text(encoding="utf-8")
                    if HOME_STR in t:
                        f.write_text(t.replace(HOME_STR, "${HOME}"), encoding="utf-8")
                except (OSError, UnicodeDecodeError):
                    pass
        copied.append(f"{name}/")

    return copied


def inventory_config_dirs(catalog: dict) -> dict:
    """Lista, por NOME, o conteúdo de cada diretório de config exportado.

    Existe só para a RECONCILIAÇÃO DE REMOÇÃO: o claude-manifest passa a registrar
    quais skills/agents/commands/hooks viajaram (não só que o diretório viajou).
    Assim, se uma skill some da origem, o destino detecta o órfão por nome
    (ver lib/reconcile.py + removal_policy.config_inventory.* no catálogo).

    É inventário (dado), não lógica: lê o que copy_claude_config já depositou em
    profile/claude/config/<dir>/ e devolve os nomes dos filhos imediatos.
    """
    inv = {}
    for name in catalog["config_to_export"]["dirs"]:
        d = CONFIG_OUT / name
        if d.is_dir():
            inv[name] = sorted(child.name for child in d.iterdir())
    return inv


def build_manifest(settings, plugins_data, marketplaces, lsp, node_pkgs,
                   non_portable, security, removed_secrets, copied,
                   hook_deps=None, config_inventory=None) -> dict:
    enabled = settings.get("enabledPlugins", {})
    plugins = []
    for full_name, installs in (plugins_data or {}).get("plugins", {}).items():
        inst = installs[0] if isinstance(installs, list) and installs else {}
        plugins.append({
            "name": full_name,
            "enabled": enabled.get(full_name, True),
            "version": inst.get("version"),
            "gitCommitSha": inst.get("gitCommitSha"),
        })

    mkts = []
    for name, meta in (marketplaces or {}).items():
        src = meta.get("source", {})
        mkts.append({"name": name, "source": src.get("source"), "repo": src.get("repo")})

    return {
        "exported_from": {"home": "${HOME}", "claude_dir": "${HOME}/.claude"},
        "marketplaces": mkts,
        "plugins": plugins,
        "language_servers": lsp,
        "hook_dependencies": hook_deps or [],
        "global_node_packages": node_pkgs,
        "security_flags": security,
        "non_portable_markers_found": non_portable,
        "secrets_removed_from_settings": removed_secrets,
        "config_files_copied": copied,
        "config_inventory": config_inventory or {},
        "_note": "Reconstrua com `claude plugin marketplace add` + `claude plugin install`. "
                 "Instale os language_servers (binários) para os plugins LSP funcionarem e "
                 "os hook_dependencies (binários) para os hooks do settings.json não falharem. "
                 "Revise security_flags e non_portable_markers antes de aplicar.",
    }


def render_setup_md(m: dict) -> str:
    n_plugins = len([p for p in m["plugins"] if p["enabled"] is not False])
    lsp_lines = "\n".join(
        f"| `{l['language_server']}` | {', '.join(l['for_plugins'])} | "
        f"`{l['binary']}` | {', '.join(l['install'].keys())} | "
        f"{'sim' if l['installed_on_source'] else 'NÃO'} |"
        for l in m["language_servers"]) or "| — | — | — | — | — |"
    mkt_lines = "\n".join(
        f"- `{mk['name']}` → `{mk['repo']}` (`claude plugin marketplace add {mk['repo']}`)"
        for mk in m["marketplaces"]) or "- (nenhum extra)"
    sec_lines = "\n".join(f"  - `{k}` = `{json.dumps(v)}`" for k, v in m["security_flags"].items()) \
        or "  - (nenhuma)"
    np_lines = ", ".join(f"`{p}`" for p in m["non_portable_markers_found"]) or "(nenhum)"

    hook_deps = m.get("hook_dependencies", [])
    if hook_deps:
        rows = "\n".join(
            f"| `{d['name']}` | `{d['binary']}` | "
            f"{'sim' if d['installed_on_source'] else 'NÃO'} | {d.get('describe', '')} |"
            for d in hook_deps)
        blocks = []
        for d in hook_deps:
            lines = [f"- **`{d['name']}`** — instale o binário "
                     f"(escolha o gerenciador que existe nesta máquina):"]
            for k, cmd in d["install"].items():
                lines.append(f"  - ({k}) `{cmd}`")
            if d.get("install_note"):
                lines.append(f"  - _{d['install_note']}_")
            if d.get("verify"):
                lines.append(f"  - Verifique: `{d['verify']}`")
            if d.get("post_install"):
                lines.append(f"  - {d['post_install']}")
            blocks.append("\n".join(lines))
        hook_deps_section = f"""
## Fase 3.5 — Dependências de binário dos hooks
Alguns hooks do `settings.json` chamam binários externos que precisam existir no
PATH (senão o hook falha silenciosamente a cada chamada). Os hooks em si já vêm
no `config/settings.json` (Fase 4) — aqui você só instala os binários.
**Idempotência:** rode `command -v <binário>` antes; pule o que já existe
(registre "já presente (vX)").

| Dependência | Binário | Estava na origem? | O que é |
|---|---|---|---|
{rows}

{chr(10).join(blocks)}
"""
    else:
        hook_deps_section = ""

    return f"""# CLAUDE_SETUP — Reconstruir a config do Claude Code

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
{mkt_lines}

## Fase 2 — Plugins ({n_plugins} habilitados)
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
{lsp_lines}

A coluna "Gerenciadores" lista as chaves disponíveis em
`manifest.language_servers[].install` — escolha a que existe nesta máquina.
As libs de TS na origem vinham de pacotes node globais
(`manifest.global_node_packages`: `typescript-language-server`, `typescript`,
`@vtsls/language-server`). Replique os relevantes com **pnpm OU npm**, conforme
o disponível. Exemplos equivalentes:
- pnpm: `pnpm add -g typescript-language-server typescript`
- npm:  `npm install -g typescript-language-server typescript`
{hook_deps_section}
## Fase 4 — settings.json (com cuidado)
Mescle `config/settings.json` no `~/.claude/settings.json`. Os paths usam
`${{HOME}}` — confirme que expandem nesta máquina.

**Pergunte ao usuário antes de aplicar estas flags de segurança:**
{sec_lines}

  Elas desativam confirmações de permissão. Numa máquina nova/compartilhada o
  usuário pode NÃO querer isso.

## Fase 5 — Hooks, statusline, keybindings, agents, skills
Copie de `config/` para `~/.claude/`. **Atenção a trechos específicos de
plataforma** encontrados: {np_lines}

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
curl -fsS http://127.0.0.1:8787/health >/dev/null && echo "proxy healthy" || \
  launchctl bootstrap "gui/$(id -u)" ~/Library/LaunchAgents/com.headroom.*.plist 2>/dev/null
sleep 2
curl -fsS http://127.0.0.1:8787/health >/dev/null && echo "proxy healthy" \
  || echo "proxy NÃO subiu — inspecione os logs do headroom"
```

### 6b-bis — Habilitar o interceptor de tool_results (ast-grep outliner)
A flag `--intercept-tool-results` faz o proxy substituir Reads grandes de código
(`.ts/.py/.rs` > 500 chars) por um outline ast-grep (só assinaturas de nível
superior); o corpo só vai ao modelo quando se pede um range específico. Reduz
tokens de reads em ~60-80%.

A flag existe em `headroom proxy`, mas **NÃO** em `headroom install apply` — então
ela não é setada pelo passo 6b. Ela persiste apenas no `proxy_args` do manifest
do deploy. Adicione-a ali e reinicie o serviço:
```bash
MANIFEST="$HOME/.headroom/deploy/init-user/manifest.json"   # ajuste o profile se != init-user
python3 - "$MANIFEST" <<'PY'
import json, sys
p = sys.argv[1]
m = json.load(open(p))
args = m.setdefault("proxy_args", [])
if "--intercept-tool-results" not in args:
    args.append("--intercept-tool-results")
    json.dump(m, open(p, "w"), indent=2)
    print("flag adicionada")
else:
    print("flag já presente")
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
curl -fsS http://127.0.0.1:8787/health >/dev/null && echo "proxy healthy" \
  || echo "proxy não respondeu — veja /tmp/headroom-restart.log"
```
Verifique o efeito: `headroom proxy --help | grep intercept` deve listar a flag, e
o `proxy_args` no manifest deve conter `--intercept-tool-results`.

### 6c — Integrar com o Claude Code
```bash
headroom init claude   # escreve ANTHROPIC_BASE_URL em ~/.claude/settings.local.json + hooks
```

### 6d — Registrar MCPs (headroom + serena)
O `headroom mcp` e a `serena` ficam em `~/.claude.json` (não viajam no profile).
O headroom registra os dois ao rodar `headroom wrap claude` pela primeira vez,
ou registre manualmente:
```bash
claude mcp add headroom -- headroom mcp serve
claude mcp add serena -- uvx --from git+https://github.com/oraios/serena \\
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
"""


def main() -> int:
    if not CLAUDE_DIR.exists():
        print(f"ERRO: {CLAUDE_DIR} não encontrado. Este é o export da config do "
              f"Claude Code — rode na máquina que já tem o Claude configurado.",
              file=sys.stderr)
        return 1

    catalog = load_catalog()
    settings = read_json(CLAUDE_DIR / "settings.json") or {}
    plugins_data = read_json(CLAUDE_DIR / "plugins" / "installed_plugins.json") or {}
    marketplaces = read_json(CLAUDE_DIR / "plugins" / "known_marketplaces.json") or {}

    print("→ Lendo config do Claude em", CLAUDE_DIR)
    sanitized, removed = sanitize_settings(settings)
    if removed:
        print(f"→ Segredos removidos do settings: {', '.join(removed)}")

    enabled = settings.get("enabledPlugins", {})
    lsp = detect_language_servers(catalog, enabled)
    print(f"→ Plugins: {len(plugins_data.get('plugins', {}))} | "
          f"marketplaces: {len(marketplaces)} | language servers LSP: {len(lsp)}")

    hook_deps = detect_hook_dependencies(catalog, settings)
    if hook_deps:
        print("→ Dependências de binário dos hooks: " + ", ".join(
            f"{d['name']} ({'na origem' if d['installed_on_source'] else 'AUSENTE aqui'})"
            for d in hook_deps))

    node_pkgs = detect_global_node_packages()
    print(f"→ Pacotes node globais: pnpm={len(node_pkgs['pnpm'])} npm={len(node_pkgs['npm'])}")

    non_portable = scan_non_portable(settings, catalog)
    security = find_security_flags(settings, catalog)
    if non_portable:
        print(f"→ Marcadores não-portáveis: {', '.join(non_portable)}")
    if security:
        print(f"→ Flags de segurança detectadas: {', '.join(security)}")

    copied = copy_claude_config(catalog, sanitized)  # type: ignore[arg-type]
    print(f"→ Config copiada: {', '.join(copied)}")

    config_inventory = inventory_config_dirs(catalog)
    inv_summary = ", ".join(f"{k}={len(v)}" for k, v in config_inventory.items())
    print(f"→ Inventário de config (p/ reconciliação): {inv_summary or '(vazio)'}")

    manifest = build_manifest(settings, plugins_data, marketplaces, lsp,
                              node_pkgs, non_portable, security, removed, copied,
                              hook_deps, config_inventory)
    (OUT / "claude-manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    (OUT / "CLAUDE_SETUP.md").write_text(render_setup_md(manifest), encoding="utf-8")

    print("\n✓ Profile do Claude gerado em ./profile/claude/")
    print("  - profile/claude/claude-manifest.json")
    print("  - profile/claude/CLAUDE_SETUP.md")
    print("  - profile/claude/config/")
    print("\nNa máquina nova: \"Leia profile/claude/CLAUDE_SETUP.md e reconstrua "
          "minha config do Claude Code.\"")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
