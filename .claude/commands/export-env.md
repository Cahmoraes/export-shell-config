---
description: Exporta o ambiente desta máquina (shell + Claude Code) e sobe para o GitHub
---

Você vai exportar o ambiente **desta máquina (origem)** e publicá-lo no GitHub,
para que ele possa ser reconstruído em outra máquina. Execute os passos abaixo;
não peça ao usuário para rodar nada manualmente.

1. **Gere os profiles** rodando os dois exports:
   - `./export.sh` — ambiente shell (zsh, ferramentas, plugins, tema).
   - `./export-claude.sh` — config do Claude Code (plugins, LSP, statusline, settings).

2. **Resuma o que foi capturado** ao usuário: SO de origem detectado, nº de
   ferramentas/plugins, language servers, e quantas linhas específicas de
   plataforma foram marcadas (mostre a quebra por plataforma do manifest).

3. **Checagem de segurança (obrigatória):** confirme que nenhum segredo entrou em
   `profile/`. O export já sanitiza, mas verifique:
   - `git -C . status --short profile/` não deve incluir `.credentials.json`,
     `.claude.json`, `history.jsonl`.
   - faça um grep rápido por credenciais em `profile/` (`sk-`, `ghp_`, `gho_`,
     `bearer`, `oauth`) e ignore matches que sejam `gitCommitSha` (hashes públicos).
   - se achar algo suspeito, PARE e avise o usuário antes de continuar.

4. **Prepare o commit:** `rm -rf tests/__pycache__ lib/__pycache__ scripts/__pycache__`,
   depois `git add -A` e mostre `git status --short`.

5. **Peça confirmação antes do push** — é uma publicação em repositório remoto.
   Mostre o resumo das mudanças e pergunte se pode subir.

6. Após o aceite: faça `git commit` com mensagem descritiva (em português) e
   `git push`. Confirme ao usuário o hash do commit e que está sincronizado.

Se não estiver num repositório git com remoto configurado, avise e ofereça
inicializar / criar o repo com `gh` antes de prosseguir.
