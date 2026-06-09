# Oh My Zsh
export ZSH="$HOME/.oh-my-zsh"
# ZSH_THEME="spaceship"
ZSH_THEME="dracula-pro"
plugins=(git zsh-completions zsh-autosuggestions zsh-syntax-highlighting)
source "$ZSH/oh-my-zsh.sh"

FIRST_PROMPT=true

precmd() {
  if [[ "$FIRST_PROMPT" = true ]]; then
    FIRST_PROMPT=false
    # Não imprime linha na primeira vez
  else
    print ""
    # Imprime linha nas próximas interações
  fi
}

PROMPT="${PROMPT}"$'\n'

typeset -U path PATH
path=("$HOME/.local/bin" $path)

# pyenv
export PYENV_ROOT="$HOME/.pyenv"
path=("$PYENV_ROOT/shims" "$PYENV_ROOT/bin" $path)
command -v pyenv >/dev/null 2>&1 && eval "$(pyenv init - zsh)"

# nvm
export NVM_DIR="$HOME/.nvm"
[[ -s "$NVM_DIR/nvm.sh" ]] && . "$NVM_DIR/nvm.sh"
[[ -s "$NVM_DIR/bash_completion" ]] && . "$NVM_DIR/bash_completion"

# bun
export BUN_INSTALL="$HOME/.bun"
path=("$BUN_INSTALL/bin" $path)

# Console Ninja
path=("$HOME/.console-ninja/.bin" $path)

# Go (só se existir)
path=("/usr/local/go/bin" $path)
if command -v go >/dev/null 2>&1; then
  GOPATH="$(go env GOPATH 2>/dev/null)"
  [[ -n "$GOPATH" ]] && path=("$GOPATH/bin" $path)
fi

# Ferramentas e utilidades
[[ -f "$HOME/.fzf.zsh" ]] && source "$HOME/.fzf.zsh"
command -v zoxide >/dev/null 2>&1 && eval "$(zoxide init zsh)"

# Aliases de listagem (eza — binário nativo no macOS, sem renome bat/fd)
alias ls="eza"
alias ll="eza -la"
alias tree="eza --tree"

# Aliases
alias apt-up="sudo apt update && sudo apt upgrade -y"
alias kube="kubectl"
alias py="python"
alias pyrun='watchfiles "python"'
alias pp="pnpm"
alias ppa="pnpm add"
alias ppt="pnpm test"
alias ppd="pnpm add -D"
alias ppr="pnpm remove"
alias ppl="pnpm list"
alias dlx="pnpm dlx"
alias ppag="pnpm add -g"
alias ppci="pnpm install --frozen-lockfile"
alias ppu="dlx npm-check -u"
alias show-alias="cat ~/.zshrc | grep alias"
alias mkdir="mkdir -p"
# docker-restart: origem usa `sudo service docker restart` (Linux); no macOS reinicia o Docker Desktop
alias docker-restart="osascript -e 'quit app \"Docker\"' && open -a Docker"
# headroom roteia o claude pelo proxy persistente (ANTHROPIC_BASE_URL no bloco headroom abaixo) — sem 'wrap', sem delay
alias claudey="claude --dangerously-skip-permissions"
alias claudya="claude agents --dangerously-skip-permissions"
alias copiloty="copilot --yolo"
alias open-zsh="code ~/.zshrc"
alias ammend="git commit --amend --no-edit"
alias glow="glow -p"
# Node
alias nw="node --watch"

# Coloque isso após a inicialização do nvm no seu ~/.zshrc
autoload -U add-zsh-hook

load-nvmrc() {
  local node_version="$(nvm version)"
  local nvmrc_path="$(nvm_find_nvmrc)"

  if [ -n "$nvmrc_path" ]; then
    local nvmrc_node_version=$(nvm version "$(cat "${nvmrc_path}")")

    if [ "$nvmrc_node_version" = "N/A" ]; then
      nvm install
    elif [ "$nvmrc_node_version" != "$node_version" ]; then
      nvm use
    fi
  # elif [ "$node_version" != "$(nvm version default)" ]; then
  #   echo "Voltando para versão padrão do nvm"
  #   nvm use default
  fi
}

add-zsh-hook chpwd load-nvmrc
load-nvmrc

# pnpm
export PNPM_HOME="$HOME/.local/share/pnpm"
case ":$PATH:" in
  *":$PNPM_HOME:"*) ;;
  *) export PATH="$PNPM_HOME:$PATH" ;;
esac
case ":$PATH:" in
  *":$PNPM_HOME/bin:"*) ;;
  *) export PATH="$PNPM_HOME/bin:$PATH" ;;
esac
# pnpm end
# Anthropic / Claude Code
# export ANTHROPIC_DEFAULT_HAIKU_MODEL="claude-haiku-4-5"
# export ANTHROPIC_DEFAULT_OPUS_MODEL="claude-opus-4-6"
# export ANTHROPIC_DEFAULT_SONNET_MODEL="claude-sonnet-4-6"
# export ANTHROPIC_FOUNDRY_BASE_URL="https://pre-mg-api.telefonicabigdata.com/anthropic"
# export CLAUDE_CODE_USE_FOUNDRY="1"
# export ANTHROPIC_FOUNDRY_API_KEY="b7537c6df0d847a9b0c75e19a7534b30"

# bun completions
[ -s "$HOME/.bun/_bun" ] && source "$HOME/.bun/_bun"
export PATH="$HOME/.local/bin:$PATH"

# >>> headroom persistent env >>>
export HEADROOM_PORT="8787"
export HEADROOM_HOST="127.0.0.1"
export HEADROOM_MODE="token"
export HEADROOM_BACKEND="anthropic"
export ANTHROPIC_BASE_URL="http://127.0.0.1:8787"
export COPILOT_PROVIDER_TYPE="anthropic"
export COPILOT_PROVIDER_BASE_URL="http://127.0.0.1:8787"
# <<< headroom persistent env <<<

# headroom: mantém o tool-search deferido do Claude Code ativo com ANTHROPIC_BASE_URL custom (issue #746).
# Fora do bloco gerenciado acima para não ser sobrescrito em futuros 'headroom install apply'.
export ENABLE_TOOL_SEARCH=true
