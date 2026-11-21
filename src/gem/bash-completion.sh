# Bash completion for GeminiOS `gem` package manager
_gem_completions() {
    local cur prev commands
    COMPREPLY=()
    cur="${COMP_WORDS[COMP_CWORD]}"
    prev="${COMP_WORDS[COMP_CWORD-1]}"
    commands="update install remove search list repo doctor"

    if [[ ${COMP_CWORD} -eq 1 ]]; then
        COMPREPLY=( $(compgen -W "${commands}" -- "${cur}") )
        return 0
    fi
    if [[ "${prev}" == "repo" ]]; then
        COMPREPLY=( $(compgen -W "list enable disable" -- "${cur}") )
        return 0
    fi
    if [[ "${prev}" == "enable" || "${prev}" == "disable" ]]; then
        COMPREPLY=( $(compgen -W "arch aur" -- "${cur}") )
        return 0
    fi
}
complete -F _gem_completions gem
