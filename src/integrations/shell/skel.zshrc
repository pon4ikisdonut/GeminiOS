# GeminiOS Default Zsh Configuration (/etc/skel/.zshrc)
HISTFILE=~/.zsh_history
HISTSIZE=10000
SAVEHIST=10000
setopt APPEND_HISTORY SHARE_HISTORY HIST_IGNORE_DUPS AUTO_CD

autoload -Uz compinit && compinit

# Material 3 Google Blue GeminiOS Prompt
PROMPT='%F{#A8C7FA}✦%f %B%F{#E2E2E9}geminios%f%b %F{#8E9099}%~%f %F{#A8C7FA}❯%f '

# Load GeminiOS AI shell hooks (command_not_found, wtf, ask, agent)
[[ -f /etc/profile.d/geminios.zsh ]] && source /etc/profile.d/geminios.zsh
