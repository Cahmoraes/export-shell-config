#!/usr/bin/env python3
"""
exporter.py — escaneia o ambiente shell atual e gera um "profile" portável.

Fluxo:
  1. Carrega a base de conhecimento (catalog.json).
  2. Detecta o SO e o que está REALMENTE instalado nesta máquina.
  3. Parseia o ~/.zshrc para descobrir tema e plugins ativos.
  4. Copia os dotfiles relevantes para profile/dotfiles/.
  5. Cruza "detectado" x "catálogo" e escreve profile/manifest.json.
  6. Gera profile/SETUP.md — as instruções que o Claude Code lê na máquina nova.

O export NÃO instala nada e NÃO move ferramentas: só inventaria a procedência.
"""

from __future__ import annotations

import json
import os
import platform
import re
import shutil
import sys
from pathlib import Path

HOME = Path.home()
REPO = Path(__file__).resolve().parent.parent
CATALOG_PATH = REPO / "lib" / "catalog.json"
PROFILE = REPO / "profile"
DOTFILES_OUT = PROFILE / "dotfiles"

# Arquivos de config candidatos a viajar. (origem no HOME, destino relativo em dotfiles/)
DOTFILE_CANDIDATES = [
    ".zshrc",
    ".zshenv",
    ".p10k.zsh",
    ".fzf.zsh",
]
# Diretórios/arquivos de config sob ~/.config que valem a pena levar.
CONFIG_DIR_CANDIDATES = [
    "micro",
    "glow",
    "starship.toml",
    "caveman",       # defaultMode do caveman (ex.: "off" — não auto-ativa nas sessões)
    "token-crunch",  # denylist da compressão de saídas (config + var TOKEN_CRUNCH_CONFIG no .zshrc)
]


def load_catalog() -> dict:
    with open(CATALOG_PATH, encoding="utf-8") as f:
        return json.load(f)


def detect_os() -> str:
    """Retorna 'macos', 'debian', 'linux' ou 'unknown' para a máquina ATUAL (origem)."""
    sysname = platform.system()
    if sysname == "Darwin":
        return "macos"
    if sysname == "Linux":
        # WSL aparece como Linux; tratamos como debian-like se houver apt.
        if shutil.which("apt") or shutil.which("apt-get"):
            return "debian"
        return "linux"
    return "unknown"


def is_wsl() -> bool:
    rel = platform.release().lower()
    return "microsoft" in rel or "wsl" in rel


def which(name: str) -> str | None:
    return shutil.which(name)


def parse_zshrc(zshrc: Path) -> dict:
    """Extrai ZSH_THEME e a lista de plugins=() do .zshrc."""
    info = {"theme": None, "plugins": [], "framework": None}
    if not zshrc.exists():
        return info
    text = zshrc.read_text(encoding="utf-8", errors="replace")

    if "oh-my-zsh" in text:
        info["framework"] = "oh-my-zsh"

    # ZSH_THEME="xxx" (ignora linhas comentadas)
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("#"):
            continue
        m = re.match(r'ZSH_THEME=["\']?([^"\'\s]+)', s)
        if m:
            info["theme"] = m.group(1)

    # plugins=(a b c ...) possivelmente multilinha
    m = re.search(r"plugins=\(([^)]*)\)", text, re.DOTALL)
    if m:
        info["plugins"] = [p for p in re.split(r"\s+", m.group(1).strip()) if p]

    return info


def scan_platform_lines(zshrc: Path, catalog: dict) -> list[dict]:
    """Acha linhas específicas de plataforma e ROTULA cada uma com sua plataforma.

    Varre todos os grupos (macos, wsl_windows, debian_binary_rename), não só WSL —
    é o que torna o fluxo bidirecional: o destino remove as linhas cuja plataforma
    não corresponde ao SO de lá.
    """
    if not zshrc.exists():
        return []
    psp = catalog["platform_specific_patterns"]
    # Ordem importa: wsl_windows ANTES de macos. Um path do Windows montado
    # ("/mnt/c/Users/...") contém "/Users/", que também é marcador macOS — o
    # marcador WSL é mais específico e deve vencer o desempate.
    groups = {
        "wsl_windows": psp.get("wsl_windows", []),
        "macos": psp.get("macos", []),
        "debian_binary_rename": psp.get("debian_binary_rename", {}).get("patterns", []),
    }
    hits = []
    for i, line in enumerate(zshrc.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
        for platform_name, pats in groups.items():
            matched = next((p for p in pats if p in line), None)
            if matched:
                hits.append({"line": i, "pattern": matched,
                             "platform": platform_name, "text": line.strip()})
                break
    return hits


def detect_tools(catalog: dict) -> dict:
    """Para cada categoria do catálogo, marca o que existe nesta máquina."""
    detected = {
        "cli_tools": {},
        "version_managers": {},
        "frameworks": {},
    }

    for name, meta in catalog["cli_tools"].items():
        bin_main = meta.get("detect")
        bin_alt = meta.get("detect_alt")
        found = which(bin_main) or (which(bin_alt) if bin_alt else None)
        if found:
            detected["cli_tools"][name] = {"path": found}

    for name, meta in catalog["version_managers"].items():
        hit = None
        if meta.get("detect") and which(meta["detect"]):
            hit = which(meta["detect"])
        if not hit and meta.get("detect_path"):
            p = Path(os.path.expanduser(meta["detect_path"]))
            if p.exists():
                hit = str(p)
        if hit:
            detected["version_managers"][name] = {"path": hit}

    for name, meta in catalog["frameworks"].items():
        if meta.get("detect_path"):
            p = Path(os.path.expanduser(meta["detect_path"]))
            if p.exists():
                detected["frameworks"][name] = {"path": str(p)}

    return detected


def _copy_rc_home_normalized(src: Path, dst: Path, home_str: str) -> None:
    """Copia um rc do shell trocando o home absoluto por `$HOME`.

    Portável porque o zsh expande `$HOME` em runtime — assim `PNPM_HOME` e os
    `source` do bun deixam de apontar para `/home/<user_da_origem>` (que não existe
    no destino e falha silenciosamente). NÃO aplicar isto aos `.config/` (starship,
    micro): esses apps NÃO expandem `$HOME` e quebrariam com o literal — por isso a
    normalização vive só aqui, no loop dos rc sourçados. Binário/ilegível: cópia crua.

    Ressalva: replace literal. Home dentro de aspas SIMPLES no rc não expandiria
    (`'$HOME'`); hoje os paths de home estão em aspas duplas/sem aspas (ok).
    """
    try:
        text = src.read_text(encoding="utf-8")
        dst.write_text(text.replace(home_str, "$HOME"), encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        shutil.copy2(src, dst)


def copy_dotfiles() -> list[str]:
    """Copia os dotfiles existentes para profile/dotfiles/. Retorna o que foi copiado."""
    if DOTFILES_OUT.exists():
        shutil.rmtree(DOTFILES_OUT)
    DOTFILES_OUT.mkdir(parents=True, exist_ok=True)
    copied = []

    home_str = str(HOME)  # via global p/ testes mockarem HOME
    for name in DOTFILE_CANDIDATES:
        src = HOME / name
        if src.exists() and src.is_file():
            _copy_rc_home_normalized(src, DOTFILES_OUT / name, home_str)
            copied.append(name)

    config_out = DOTFILES_OUT / "config"
    for name in CONFIG_DIR_CANDIDATES:
        src = HOME / ".config" / name
        if not src.exists():
            continue
        config_out.mkdir(parents=True, exist_ok=True)
        dst = config_out / name
        if src.is_dir():
            # Ignora APENAS estado volátil (não-config). 'buffers' e 'backups' são
            # os diretórios de histórico/crash-recovery do micro — contêm conteúdo
            # de arquivos editados e não devem viajar. Mantemos 'history'/'cache'
            # soltos FORA do filtro: poderiam ser config legítima de outros apps.
            shutil.copytree(src, dst, dirs_exist_ok=True,
                            ignore=shutil.ignore_patterns(
                                "buffers", "backups", "*.log", ".DS_Store"))
        else:
            shutil.copy2(src, dst)
        copied.append(f".config/{name}")

    return copied


def build_manifest(catalog, zsh_info, detected, platform_lines, copied, src_os) -> dict:
    """Monta o inventário estruturado cruzando detecção com o catálogo."""
    def entry(category, name):
        meta = catalog[category].get(name, {})
        return {
            "name": name,
            "source": meta.get("source"),
            "install": meta.get("install"),
            "verify": meta.get("verify"),
            "detect": meta.get("detect"),
            "detect_alt": meta.get("detect_alt"),
            "detect_path": meta.get("detect_path"),
            "shell_init": meta.get("shell_init"),
            "config_dirs": meta.get("config_dirs"),
            "note": meta.get("note"),
        }

    # Ferramentas CLI presentes
    cli = [entry("cli_tools", n) for n in detected["cli_tools"]]

    # Plugins do OMZ que estão ativos no .zshrc
    plugins = []
    for p in zsh_info["plugins"]:
        meta = catalog["omz_plugins"].get(p, {})
        plugins.append({
            "name": p,
            "source": meta.get("source", "desconhecido — verificar manualmente"),
            "install": meta.get("install"),
            "known": p in catalog["omz_plugins"],
        })

    # Tema ativo
    theme = None
    if zsh_info["theme"]:
        meta = catalog["omz_themes"].get(zsh_info["theme"], {})
        theme = {
            "name": zsh_info["theme"],
            "source": meta.get("source", "desconhecido — verificar manualmente"),
            "install": meta.get("install"),
            "manual": meta.get("manual", False),
            "note": meta.get("note"),
            "known": zsh_info["theme"] in catalog["omz_themes"],
        }

    version_managers = [entry("version_managers", n) for n in detected["version_managers"]]
    frameworks = [entry("frameworks", n) for n in detected["frameworks"]]

    return {
        "generated_from": {
            "os": src_os,
            "is_wsl": is_wsl(),
            "hostname": platform.node(),
        },
        "framework": zsh_info["framework"],
        "theme": theme,
        "omz_plugins": plugins,
        "cli_tools": cli,
        "version_managers": version_managers,
        "frameworks": frameworks,
        "dotfiles_copied": copied,
        "platform_specific_lines": platform_lines,
        "_note": "Gerado por export.sh. Cada item de 'platform_specific_lines' tem um campo 'platform' (macos/wsl_windows/debian_binary_rename). No destino, REMOVA as linhas cuja plataforma não corresponde ao SO de lá. Bidirecional.",
    }


def render_setup_md(manifest: dict) -> str:
    """Gera o SETUP.md — o prompt que o Claude Code lê na máquina destino."""
    plat_count = len(manifest["platform_specific_lines"])
    theme = manifest["theme"]
    theme_line = theme["name"] if theme else "(nenhum)"
    src_os = manifest["generated_from"]["os"]

    # Quebra das linhas específicas por plataforma (para o roteiro bidirecional).
    by_plat: dict = {}
    for ln in manifest["platform_specific_lines"]:
        by_plat.setdefault(ln.get("platform", "outro"), []).append(ln)
    plat_breakdown = ", ".join(f"{p}: {len(v)}" for p, v in by_plat.items()) or "(nenhuma)"

    # Tabela de verificação: cada ferramenta com seu smoke-test (campo `verify`).
    verify_rows = []
    for cat_label, items in [
        ("CLI", manifest["cli_tools"]),
        ("version manager", manifest["version_managers"]),
    ]:
        for it in items:
            if it.get("verify"):
                verify_rows.append(f"| `{it['name']}` | {cat_label} | `{it['verify']}` |")
    verify_table = "\n".join(verify_rows) if verify_rows else "| — | — | — |"

    manual_items = "".join(
        f"- **{p['name']}**: {p['note']}\n"
        for p in [manifest["theme"]]
        if p and p.get("manual")
    )

    return f"""# SETUP — Preparar este ambiente shell

> **Para o Claude Code:** este arquivo é um roteiro executável. Leia-o por
> inteiro junto com `manifest.json` (no mesmo diretório) antes de agir.
> NÃO copie o `.zshrc` de origem cru — ele foi gerado em **{src_os}** e contém
> linhas específicas dessa plataforma que quebram em outros SOs. O fluxo é
> **bidirecional** (WSL↔macOS↔Linux): na Fase 4 você remove as linhas cuja
> plataforma não corresponde a ESTE destino.

## Contexto da origem
- SO de origem: **{src_os}** (WSL: {manifest['generated_from']['is_wsl']})
- Framework: **{manifest['framework']}**
- Tema ativo: **{theme_line}**
- Linhas específicas de plataforma encontradas: {plat_breakdown}

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
Se o **{manifest['framework']}** faltar, instale (veja `frameworks` no manifest).
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
  `${{ZSH_CUSTOM:-~/.oh-my-zsh/custom}}/plugins/<nome>` já existir, pule; senão
  clone do `source`.
- Tema: se for `dracula-pro` (PAGO, não-público), PERGUNTE ao usuário se ele
  quer (a) copiar o arquivo do acesso comprado, ou (b) usar a alternativa
  gratuita `dracula`. Veja o `note` do tema no manifest.

### Fase 4 — Montar o .zshrc adaptado (BIDIRECIONAL)
Use `dotfiles/.zshrc` como BASE. As {plat_count} linhas específicas de plataforma
({plat_breakdown}) estão em `manifest.json → platform_specific_lines`, cada uma
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
{verify_table}

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
{manual_items}
"""


def main() -> int:
    if not CATALOG_PATH.exists():
        print(f"ERRO: catálogo não encontrado em {CATALOG_PATH}", file=sys.stderr)
        return 1

    catalog = load_catalog()
    src_os = detect_os()
    zshrc = HOME / ".zshrc"

    print("→ Detectando SO de origem:", src_os, "(WSL)" if is_wsl() else "")
    zsh_info = parse_zshrc(zshrc)
    print(f"→ Framework: {zsh_info['framework']} | tema: {zsh_info['theme']} | "
          f"{len(zsh_info['plugins'])} plugins")

    detected = detect_tools(catalog)
    print(f"→ Ferramentas CLI detectadas: {', '.join(detected['cli_tools']) or '(nenhuma)'}")
    print(f"→ Version managers: {', '.join(detected['version_managers']) or '(nenhum)'}")

    platform_lines = scan_platform_lines(zshrc, catalog)
    print(f"→ Linhas específicas de WSL/Windows marcadas: {len(platform_lines)}")

    PROFILE.mkdir(parents=True, exist_ok=True)
    copied = copy_dotfiles()
    print(f"→ Dotfiles copiados: {', '.join(copied) or '(nenhum)'}")

    manifest = build_manifest(catalog, zsh_info, detected, platform_lines, copied, src_os)
    (PROFILE / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (PROFILE / "SETUP.md").write_text(render_setup_md(manifest), encoding="utf-8")

    print("\n✓ Profile gerado em ./profile/")
    print("  - profile/manifest.json")
    print("  - profile/SETUP.md")
    print("  - profile/dotfiles/")
    print("\nPróximo: git add -A && git commit && git push")
    print("Na máquina nova: git clone <repo>, abra o Claude Code e diga:")
    print('  "Leia profile/SETUP.md e prepare meu ambiente."')
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
