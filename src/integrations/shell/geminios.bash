# GeminiOS Bash Integration (/etc/profile.d/geminios.bash)

alias ask='gemini'
alias agent='gemini --agent'

command_not_found_handle() {
    local cmd="$1"
    echo "bash: ${cmd}: command not found" >&2
    if command -v gemini >/dev/null 2>&1; then
        echo "[GeminiOS] Checking suggestion for '${cmd}'..." >&2
        gemini "Command '${cmd}' was not found on GeminiOS (package manager: gem, optional arch/aur bridge). Give a 1-2 line fix or install command." 2>/dev/null
    fi
    return 127
}

wtf() {
    local last_cmd
    last_cmd="$(history 2 | head -n 1 | sed 's/^[ ]*[0-9]*[ ]*//')"
    echo "[GeminiOS] Analyzing last command: ${last_cmd}"
    gemini "The user ran this command in bash on GeminiOS and hit an error: \`${last_cmd}\`. Explain the likely cause and exact fix concisely."
}
