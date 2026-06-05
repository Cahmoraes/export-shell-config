---
description: Reconstrói nesta máquina o ambiente exportado (shell + Claude Code), com backup e verificação
---

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

## 5. Verificação e relatório
- Rode os smoke-tests da Fase 6 do `SETUP.md` e o `claude plugin list`.
- Entregue um relatório: `instalado` / `já presente` / `pulado` / **`FALHOU`** por
  item, mais o que exigiu decisão manual (tema pago, hooks, flags de segurança).
- Lembre o usuário de como reverter, se necessário: `./scripts/restore.sh <backup>`.
