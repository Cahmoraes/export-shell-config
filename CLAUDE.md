# CLAUDE.md

Ferramenta para exportar o ambiente de uma máquina (shell zsh + Claude Code) e
reconstruí-lo em outra, **bidirecional** entre WSL, macOS e Linux. O export é
determinístico (scripts); o import é híbrido (o Claude lê um roteiro e adapta).

## Comandos

```bash
# Testes (só stdlib — NÃO há pytest nem deps externas). Inclui integração (2 fluxos).
python3 -m unittest discover -s tests -p "test_*.py"

# Exports (rodam na ORIGEM; geram/atualizam profile/)
./export.sh            # ambiente shell  → profile/ (manifest.json, SETUP.md, dotfiles/)
./export-claude.sh     # config do Claude → profile/claude/ (claude-manifest.json, CLAUDE_SETUP.md, config/)

# Preview no DESTINO (read-only, não instala nada)
./scripts/dry-run.sh

# Rede de segurança no DESTINO
./scripts/backup.sh                       # snapshot antes de alterar
./scripts/restore.sh ~/.shell-config-backups/<ts>   # revert
```

Após mudar qualquer `lib/*.py` ou `lib/*.json`, **regenere o profile**
(`./export.sh && ./export-claude.sh`) — `profile/` é gerado mas é commitado (é o
que viaja para a outra máquina).

**Fluxo via Claude (sem rodar scripts à mão)** — skills em `.claude/skills/`:
- `export-env` — na ORIGEM: gera os profiles, checa segredos, commita e dá push.
- `import-env` — no DESTINO: dry-run → backup → executa `SETUP.md` e
  `CLAUDE_SETUP.md` adaptando ao SO → verifica. Viaja com o repo (após `git clone`).

## Arquitetura

Duas pontas, conectadas por `profile/` (transportado via git):

```
ORIGEM (export.sh)              profile/            DESTINO (Claude lê o roteiro)
classifica cada item     →   manifest + dotfiles  →  detecta o SO daqui e adapta
```

- **Dados vs código:** o conhecimento mora em JSON (`catalog.json`,
  `claude_catalog.json`); a lógica em Python (`exporter.py`, `claude_exporter.py`).
  **Adicionar uma ferramenta/language server = editar o JSON, não o código.**
- **Bidirecionalidade = classificar origem + filtrar destino.** O export rotula
  cada linha não-portável por plataforma (`macos`/`wsl_windows`/
  `debian_binary_rename`); o destino remove as que não são do SO de lá. NÃO
  existe "código do fluxo direto" vs "reverso" — é uma engine só (O(N), não O(N²)).

## Arquivos-chave

| Arquivo | Papel |
|---|---|
| `lib/catalog.json` | Conhecimento de ferramentas shell + `platform_specific_patterns` (por SO). |
| `lib/exporter.py` | Motor do export shell. `scan_platform_lines` rotula por plataforma; `render_setup_md` gera o roteiro. |
| `lib/claude_catalog.json` | Language servers por plugin LSP + `sensitive_never_export` + `non_portable_markers`. |
| `lib/claude_exporter.py` | Motor do export do Claude. **Sanitiza segredos** antes de copiar. |
| `scripts/dryrun.py` | `compute_adaptation_plan()` — regra pura de manter×remover por destino. |

## Gotchas (não-óbvios — leia antes de mexer)

- **Segredos nunca viajam.** `claude_exporter.py` remove chaves que casam
  `api_key|token|secret|password` e nunca copia `.credentials.json`,
  `.claude.json`, `history.jsonl`, `projects/`, `sessions/`. Ao alterar esse
  exporter, preserve a sanitização e os `${HOME}` (paths absolutos do home viram
  `${HOME}`). Há testes dedicados a isso em `test_claude_exporter.py`.
- **Ordem de varredura importa:** em `scan_platform_lines`, `wsl_windows` vem
  ANTES de `macos`. Um path do Windows montado (`/mnt/c/Users/...`) contém
  `/Users/` (marcador macOS) — o marcador WSL é mais específico e deve vencer.
  Inverter a ordem reintroduz um falso positivo (há teste de regressão).
- **`profile/` é gerado mas versionado.** Não edite à mão; rode os exports.
  Antes de `git add`, limpe caches: `rm -rf tests/__pycache__ lib/__pycache__ scripts/__pycache__`.
- **Estado volátil não viaja:** `copy_dotfiles` ignora `buffers`/`backups` do
  micro (crash-recovery, podem ter conteúdo de arquivos). Só config viaja.
- **`python3` é dependência dos exports e do dry-run.** Em testes que forçam PATH
  mínimo, use o binário real (`sys.executable`), não `command -v python3` — o
  shim do pyenv é um script bash e quebra sem `bash` no PATH.
- **`bat`/`fd` são bidirecionais:** no Debian/Ubuntu os binários são
  `batcat`/`fdfind` (precisam de alias); no macOS são nativos (sem alias). O
  roteiro adiciona no Debian e remove no macOS — não trate como caso único.

## Convenções

- Idioma do projeto: **português pt-br** (comentários, docs, roteiros, mensagens
  de commit). Identificadores de código em inglês.
- Testes: `unittest` puro, sem dependências. Manter assim — uma ferramenta que
  prepara máquinas limpas tem que rodar em máquina limpa.
- Funções de I/O isolam efeitos atrás de globais (`HOME`, `OUT`) e de `which()`,
  para serem testáveis com mocks/tmpdirs.
