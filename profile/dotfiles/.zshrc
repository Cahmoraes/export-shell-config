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

# Env específicos de desktop (ajuste se não fizer sentido no seu setup)
export WARP_ENABLE_WAYLAND=1
export MESA_D3D12_DEFAULT_ADAPTER_NAME=NVIDIA
export BROWSER=google-chrome

# Warp: notifica que o rc foi carregado (somente no Warp)
if [[ "$TERM_PROGRAM" == "WarpTerminal" ]]; then
  printf '\ePsf{"hook":"SourcedRcFileForWarp","value":{"shell":"zsh"}}\x9c'
fi

# Aliases de compatibilidade (Ubuntu renomeia bat e fd para evitar conflitos)
alias bat="batcat"
alias fd="fdfind"
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
alias open-zsh="code ~/.zshrc"
alias docker-restart="sudo service docker restart"
alias copiloty="copilot --yolo"
# Node
alias nw="node --watch"
# Git
alias ammend="git commit --amend --no-edit"
alias claudey="claude --dangerously-skip-permissions"
alias claudya="claude agents --dangerously-skip-permissions"
alias glow="glow -p"


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
export PNPM_HOME="/home/cahmoraes/.local/share/pnpm"
case ":$PATH:" in
  *":$PNPM_HOME:"*) ;;
  *) export PATH="$PNPM_HOME:$PATH" ;;
esac
case ":$PATH:" in
  *":$PNPM_HOME/bin:"*) ;;
  *) export PATH="$PNPM_HOME/bin:$PATH" ;;
esac
# pnpm end

# VS Code CLI (WSL → abre no Windows)
VSCODE_BIN="/mnt/c/Users/ike_m/AppData/Local/Programs/Microsoft VS Code/bin"
[[ -d "$VSCODE_BIN" ]] && path=("$VSCODE_BIN" $path)

# ── VS Code CPU priority (evita travar YouTube/video ao abrir VS Code) ──────
# Aplica nice=10 nos processos VS Code quando chamado
alias nice-vscode='bash ~/nice-vscode.sh'
alias nice-vscode-restore='bash ~/nice-vscode.sh 0'
alias pscreen='pastepng /tmp/screen.png && echo /tmp/screen.png'

# PulseAudio → WSLg (voice mode)
export PULSE_SERVER=unix:/mnt/wslg/runtime-dir/pulse/native

# bun completions
[ -s "/home/cahmoraes/.bun/_bun" ] && source "/home/cahmoraes/.bun/_bun"
export PATH="$HOME/.local/bin:$PATH"
