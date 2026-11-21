# GeminiOS Zsh Integration (/etc/profile.d/geminios.zsh)
# 1. Intercepts missing commands and asks Gemini for package/fix hints
# 2. Provides `wtf` to explain the last failed command
# 3. Provides `ask` and `agent` shortcuts
# 4. Prevents Zsh globbing errors on question marks (e.g. "gemini как дела?")

# Disable globbing for natural language CLI tools so `?` does not trigger "no matches found"
alias gemini='noglob gemini'
alias ask='noglob gemini'
alias agent='noglob gemini --agent'
alias wtf='noglob wtf'

# Leave unmatched glob patterns as literal strings rather than throwing "no matches found"
unsetopt NOMATCH 2>/dev/null

command_not_found_handler() {
    local cmd="$1"
    echo "zsh: command not found: ${cmd}" >&2
    if command -v gemini >/dev/null 2>&1; then
        echo "[GeminiOS] Checking suggestion for '${cmd}'..." >&2
        gemini "Command '${cmd}' was not found on GeminiOS (package manager: gem, optional arch/aur bridge). Give a 1-2 line fix or install command." 2>/dev/null
    fi
    return 127
}

wtf() {
    local last_cmd
    last_cmd="$(fc -ln -1)"
    echo "[GeminiOS] Analyzing last command: ${last_cmd}"
    gemini "The user ran this command in zsh on GeminiOS and hit an error: \`${last_cmd}\`. Explain the likely cause and exact fix concisely."
}
