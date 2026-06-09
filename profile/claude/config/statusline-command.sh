#!/usr/bin/env bash
input=$(cat)

IFS=$'\t' read -r model effort dir ctx_pct five_resets_at five_used_pct < <(
  printf '%s' "$input" | jq -r '[
    (.model.display_name // ""),
    (.effort.level // ""),
    (.workspace.current_dir // .cwd // ""),
    (.context_window.used_percentage // ""),
    (.rate_limits.five_hour.resets_at // ""),
    (.rate_limits.five_hour.used_percentage // "")
  ] | @tsv'
)

[ -z "$dir" ] && dir=$(pwd)

pct_color() {
  local pct=$1
  if   [ "$pct" -lt 50 ]; then printf '\033[32m'
  elif [ "$pct" -lt 80 ]; then printf '\033[33m'
  else                          printf '\033[31m'
  fi
}

make_bar() {
  local pct=$1
  local filled=$(( pct * 10 / 100 ))
  [ "$filled" -gt 10 ] && filled=10
  local empty=$(( 10 - filled ))
  local bar=""
  for (( i=0; i<filled; i++ )); do bar="${bar}█"; done
  for (( i=0; i<empty;  i++ )); do bar="${bar}░"; done
  printf '%s' "$bar"
}

branch=$(git -C "$dir" --no-optional-locks symbolic-ref --short HEAD 2>/dev/null)

[ -n "$branch" ] && printf ' \033[01;33m(%s)\033[00m' "$branch"
[ -n "$model"  ] && printf ' \033[00;36m[%s]\033[00m' "$model"
[ -n "$effort" ] && printf ' \033[00;32m⚡%s\033[00m' "$effort"

if [ -n "$ctx_pct" ]; then
  pct=$(printf '%.0f' "$ctx_pct")
  color=$(pct_color "$pct")
  bar=$(make_bar "$pct")
  printf " ${color}[%s] %d%%\033[0m" "$bar" "$pct"
fi

if [ -n "$five_resets_at" ]; then
  # macOS usa `date -r <epoch>`; GNU/Linux usa `date -d "@<epoch>"`. Tenta BSD, cai pra GNU.
  reset_time=$(date -r "${five_resets_at}" "+%H:%M" 2>/dev/null || date -d "@${five_resets_at}" "+%H:%M" 2>/dev/null)
  if [ -n "$reset_time" ]; then
    session_pct=""
    [ -n "$five_used_pct" ] && session_pct="$(printf '%.0f' "$five_used_pct")% "
    printf ' \033[02;37m│\033[00m \033[00;35m%s%s\033[00m' "$session_pct" "$reset_time"
  fi
fi
