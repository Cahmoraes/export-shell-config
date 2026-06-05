# Template — Relatório de Importação

Este arquivo é o **molde** do relatório que o skill `import-env` gera no DESTINO.
Copie a estrutura abaixo para `RELATORIO_IMPORT.md` (na raiz do repo clonado) e
preencha conforme a execução. O relatório é **específico desta máquina** — não
viaja no `profile/` e está no `.gitignore`.

Objetivo: quando o destino **não consegue instalar uma biblioteca sozinho** (ex.:
o `rtk`, cujo método muda por SO), o problema fica **registrado de forma sumarizada**
em vez de se perder no log da conversa. O usuário lê o relatório e sabe, num
relance, o que falta e o que mudar na ORIGEM para a próxima vez.

Regras de preenchimento:
- Liste no resumo **só contagens**; o detalhe vai nas tabelas.
- Uma linha por item que **não** instalou direto pelo roteiro (o que instalou
  limpo não precisa aparecer — mantenha sumarizado).
- Sempre que houver falha/intervenção, preencha **"Sugestões para a ORIGEM"**:
  é o que fecha a lacuna no `lib/catalog.json` / roteiro para a próxima importação.
- Estados padronizados (use exatamente estes ícones+rótulos):
  - `✅ instalado` · `➖ já presente` · `⏭️ pulado` (não aplicável a este SO)
  - `✋ resolvido manual` · `⚠️ resolvido com ressalva` · `❌ não resolvido` (bloqueante)

---

```markdown
# Relatório de Importação — <SO do destino> — <AAAA-MM-DD>

> Gerado pelo skill `import-env`. Registra falhas, intervenções manuais e
> pendências da reconstrução do ambiente NESTA máquina. Específico do destino.

## Contexto
- **Destino:** <ex.: macOS 14 arm64 / Ubuntu 24.04 WSL>
- **Origem do profile:** commit `<git rev-parse --short HEAD>`
- **Data/hora:** <ISO 8601>
- **Backup criado:** `<caminho impresso por backup.sh>`
  (revert: `./scripts/restore.sh <caminho>`)

## Resumo
| Estado | Qtde |
|---|---|
| ✅ instalado | 0 |
| ➖ já presente | 0 |
| ⏭️ pulado (não aplicável a este SO) | 0 |
| ✋ resolvido manual | 0 |
| ⚠️ resolvido com ressalva | 0 |
| ❌ não resolvido (bloqueante) | 0 |

## Problemas e intervenções
Uma linha por item que NÃO instalou direto pelo roteiro.
Categorias: `CLI` · `plugin` · `language-server` · `hook-binary` · `dotfile` · `config-app`.

| Item | Categoria | Plataforma | Tentado (comando do roteiro) | Sintoma / erro | Resolução | Estado |
|---|---|---|---|---|---|---|
| `rtk` | hook-binary | macOS | `<método que o roteiro tentou>` | não resolveu sozinho | manual: `brew install rtk` | ✋ resolvido manual |

## Decisões manuais (sensíveis — não são falhas)
Itens que o roteiro manda PERGUNTAR antes de aplicar:
- [ ] tema pago (ex.: `dracula-pro`) — instalado? como?
- [ ] flags de segurança (`bypassPermissions`, `skipDangerousModePermissionPrompt`,
      `skipAutoPermissionPrompt`) — aplicadas? (sim/não)
- [ ] hooks específicos de plataforma (`wsl-screenshot-cli`, `~/bin/claude-notify`)
      — mantidos / removidos / adaptados?

## Sugestões para a ORIGEM (fechar a lacuna)
O que mudar no `profile/`/catálogo para a PRÓXIMA importação não tropeçar aqui.
- Ex.: `rtk` precisa de instalação **por plataforma** — registrar em `lib/catalog.json`:
  - macOS: `brew install rtk`
  - Linux/WSL: `curl -fsSL https://raw.githubusercontent.com/rtk-ai/rtk/refs/heads/master/install.sh | sh && rtk init -g`
  - fallback: `cargo install --git https://github.com/rtk-ai/rtk` ou binário prebuilt das releases

## Pendências em aberto
- [ ] <itens sem resolução que exigem ação do usuário>

## Verificação final
- `claude plugin list` → <ok / divergências>
- smoke-tests (Fase 6 do `SETUP.md`) → <ok / quais falharam>
```
