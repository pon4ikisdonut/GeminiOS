# GeminiOS Default Zsh Configuration (/etc/skel/.zshrc and /etc/zsh/zshrc)

# 1. Shell History
HISTFILE=~/.zsh_history
HISTSIZE=10000
SAVEHIST=10000
setopt APPEND_HISTORY SHARE_HISTORY HIST_IGNORE_DUPS HIST_IGNORE_SPACE AUTO_CD

# 2. Keybindings & Terminal Navigation (Emacs mode + Arrow Keys Fix)
bindkey -e

# Load terminfo for hardware terminal capability lookups
zmodload zsh/terminfo 2>/dev/null

# Make sure terminal enters application cursor mode when ZLE is active
if (( ${+terminfo[smkx]} )) && (( ${+terminfo[rmkx]} )); then
    function zle-line-init() {
        echoti smkx
    }
    function zle-line-finish() {
        echoti rmkx
    }
    zle -N zle-line-init
    zle -N zle-line-finish
fi

# History search with Up/Down arrows based on already typed prefix
autoload -Uz up-line-or-beginning-search down-line-or-beginning-search
zle -N up-line-or-beginning-search
zle -N down-line-or-beginning-search

# Standard and Application Mode Arrow Keys (Konsole / xterm / Wayland)
bindkey '^[[A' up-line-or-beginning-search      # Up Arrow (normal)
bindkey '^[OA' up-line-or-beginning-search      # Up Arrow (application)
bindkey '^[[B' down-line-or-beginning-search    # Down Arrow (normal)
bindkey '^[OB' down-line-or-beginning-search    # Down Arrow (application)

bindkey '^[[C' forward-char                     # Right Arrow (normal)
bindkey '^[OC' forward-char                     # Right Arrow (application)
bindkey '^[[D' backward-char                    # Left Arrow (normal)
bindkey '^[OD' backward-char                    # Left Arrow (application)

# Terminfo-mapped Arrow Keys
[[ -n "${terminfo[kcuu1]}" ]] && bindkey "${terminfo[kcuu1]}" up-line-or-beginning-search
[[ -n "${terminfo[kcud1]}" ]] && bindkey "${terminfo[kcud1]}" down-line-or-beginning-search
[[ -n "${terminfo[kcuf1]}" ]] && bindkey "${terminfo[kcuf1]}" forward-char
[[ -n "${terminfo[kcub1]}" ]] && bindkey "${terminfo[kcub1]}" backward-char

# Home / End Keys
bindkey '^[[H' beginning-of-line
bindkey '^[OH' beginning-of-line
bindkey '^[[1~' beginning-of-line
bindkey '^[[7~' beginning-of-line
[[ -n "${terminfo[khome]}" ]] && bindkey "${terminfo[khome]}" beginning-of-line

bindkey '^[[F' end-of-line
bindkey '^[OF' end-of-line
bindkey '^[[4~' end-of-line
bindkey '^[[8~' end-of-line
[[ -n "${terminfo[kend]}" ]] && bindkey "${terminfo[kend]}" end-of-line

# Delete and Backspace Keys
bindkey '^[[3~' delete-char
[[ -n "${terminfo[kdch1]}" ]] && bindkey "${terminfo[kdch1]}" delete-char
bindkey '^?' backward-delete-char
bindkey '^H' backward-delete-char

# Word navigation: Ctrl+Left / Ctrl+Right and Alt+Left / Alt+Right
bindkey '^[[1;5D' backward-word
bindkey '^[[1;5C' forward-word
bindkey '^[[5D' backward-word
bindkey '^[[5C' forward-word
bindkey '^[b' backward-word
bindkey '^[f' forward-word

# 3. Tab Completion System
autoload -Uz compinit && compinit -d ~/.zcompdump

# 4. Material 3 Google Blue GeminiOS Prompt
PROMPT='%F{#A8C7FA}✦%f %B%F{#E2E2E9}geminios%f%b %F{#8E9099}%~%f %F{#A8C7FA}❯%f '

# 5. Load GeminiOS AI shell hooks (command_not_found, wtf, ask, agent)
[[ -f /etc/profile.d/geminios.zsh ]] && source /etc/profile.d/geminios.zsh
