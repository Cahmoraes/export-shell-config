---
name: import-env
description: Reconstrói nesta máquina (DESTINO) o ambiente exportado — shell zsh + Claude Code — adaptando ao SO, com backup e verificação. Use num clone deste repositório quando o usuário quer instalar o ambiente salvo (ex "prepare meu ambiente", "importe minhas configs", "reconstrua o ambiente aqui").
---

# import-env

Você está numa **máquina destino**, dentro de um clone deste repositório. Vai
reconstruir o ambiente descrito em `profile/`, **adaptando ao SO desta máquina**.
Execute os passos; não peça ao usuário para rodar scripts manualmente. PEÇA
CONFIRMAÇÃO antes de passos sensíveis (sudo, sobrescrever config, tema pago,
flags de segurança).

## 0. Pré-checagem
- Confirme que `profile/manifest.json` e `profile/claude/claude-manifest.json`
  existem. Se faltarem, o profile não foi gerado/commitado na origem — avise e pare.
- Detecte o SO desta máquina (`uname -s`; em Linux veja se é WSL via `/proc/version`).

## 1. Plano (dry-run)
Rode `./scripts/dry-run.sh` e mostre ao usuário o **plano de adaptação**
(origem → este destino): o que já existe e será pulado, o que falta instalar, e
as linhas do `.zshrc` a manter/remover/adicionar. **Peça confirmação para seguir.**

O dry-run também imprime o **Plano de remoção** (deleção propagada origem→destino):
itens que ESTE destino aplicou num import anterior e que **sumiram da origem**
(via recibo em `~/.dev-env-migrate/`). Há duas categorias — destaque ambas:
- **REMOVER** (tool-owned: skill, plugin, marketplace, security flag, hook-script,
  plugin OMZ) → você vai removê-los na Fase 4.5, **com confirmação**.
- **AVISO** (binário de sistema: CLI, language server, hook-binary) → **não
  desinstale** (pode quebrar a máquina); só registre no relatório.
No **primeiro import** desta máquina não há recibo → nada a remover (normal).

## 2. Backup (rede de segurança — obrigatório)
Rode `./scripts/backup.sh` e **guarde o caminho impresso na última linha**. Cite-o
ao usuário: é o ponto de revert (`./scripts/restore.sh <caminho>`).

## 3. Ambiente shell
Leia `profile/SETUP.md` e execute-o fase a fase para ESTE SO:
- instale `zsh` se faltar (pergunte antes); instale só as ferramentas faltantes
  com o gerenciador certo (`brew`/`apt`/`dnf`/`pacman`);
- monte o `.zshrc` adaptado seguindo o plano de adaptação (remova as linhas cuja
  plataforma ≠ este destino; ajuste os aliases `bat`/`fd` conforme o destino);
- copie as configs de apps (`~/.config/...`).

## 4. Claude Code
Leia `profile/claude/CLAUDE_SETUP.md` e execute-o:
- adicione os marketplaces e instale os plugins (idempotente: `claude plugin list`
  antes);
- garanta os language servers no PATH (detecte `pnpm`/`npm`/`go`/`rustup`; prefira
  `pnpm`, caia para `npm`);
- mescle o `settings.json` (os paths usam `${HOME}`); **pergunte antes** de aplicar
  as flags de segurança (`bypassPermissions`); condicione/remova hooks que não são
  desta plataforma.

## 4.5 Remoções (órfãos que sumiram da origem)
Execute o **Plano de remoção** do dry-run. O backup da Fase 2 já cobre o revert.
Trate cada categoria conforme a ação:
- **REMOVER (tool-owned)** — para cada órfão, **PERGUNTE ao usuário** e, com o
  aceite, remova pelo método certo:
  - `plugin Claude` → `claude plugin uninstall <nome>` · `marketplace` →
    `claude plugin marketplace remove <nome>`.
  - `skill`/`agent`/`command`/`hook-script` → apague o item em
    `~/.claude/<skills|agents|commands|hooks>/<nome>` (já há backup na Fase 2 do
    `CLAUDE_SETUP.md`).
  - `security flag` → remova a chave do `~/.claude/settings.json` no merge da Fase 4.
  - `plugin OMZ` → remova de `plugins=(...)` no `.zshrc` e apague a pasta clonada
    em `${ZSH_CUSTOM:-~/.oh-my-zsh/custom}/plugins/<nome>`.
- **AVISO (binário de sistema)** — **não** desinstale. Apenas registre no
  relatório que saiu da origem (o usuário desinstala manualmente se quiser).
- Se o usuário recusar uma remoção, registre como pendência e siga — o recibo da
  Fase 5 só grava o estado novo, então o item voltará a aparecer no próximo
  dry-run até ser resolvido.

## 5. Verificação e relatório
- Rode os smoke-tests da Fase 6 do `SETUP.md` e o `claude plugin list`.
- **Durante as fases 3 e 4, anote cada tropeço** (item que não instalou pelo
  método do roteiro, erro do gerenciador, decisão sensível) — não confie só na
  memória da conversa.
- **Gere o `RELATORIO_IMPORT.md`** na raiz do repo, seguindo o molde em
  `references/import-report.md`. É um report **sumarizado** e
  específico desta máquina (está no `.gitignore`, não viaja no profile). Ele
  existe para o caso em que **o destino não consegue instalar uma biblioteca
  sozinho** — o método de instalação costuma variar por SO (ex.: `rtk` →
  `brew install rtk` no macOS, `install.sh` no Linux/WSL). Registre por item:
  o que foi tentado, o sintoma, como resolveu (ou não) e o **estado** padronizado
  (`✅ instalado` / `➖ já presente` / `⏭️ pulado` / `✋ resolvido manual` /
  `⚠️ resolvido com ressalva` / `❌ não resolvido`).
- Sempre que houver falha ou intervenção manual, preencha a seção **"Sugestões
  para a ORIGEM"** do relatório — é o que fecha a lacuna no `lib/catalog.json` na
  próxima importação.
- **Grave o recibo** (baseline da próxima reconciliação de remoção): rode
  `python3 ./scripts/receipt.py save`. Ele copia os manifests aplicados para
  `~/.dev-env-migrate/receipt/`. Sem isto, o próximo import não detecta o que foi
  removido da origem. Faça isto **ao final**, só se o import chegou ao fim sem
  erro bloqueante (senão o baseline registraria um estado que não foi de fato
  aplicado).
- Mostre o resumo ao usuário e cite o caminho do `RELATORIO_IMPORT.md`.
- Lembre o usuário de como reverter, se necessário: `./scripts/restore.sh <backup>`.
