# Bash completion for visage
_visage_completion() {
    local cur prev
    COMPREPLY=()
    cur="${COMP_WORDS[COMP_CWORD]}"
    prev="${COMP_WORDS[COMP_CWORD-1]}"

    case "${prev}" in
        --remote-port|--export-interval|--output|--config)
            COMPREPLY=()
            return 0
            ;;
        --export-format)
            COMPREPLY=( $(compgen -W "json jsonl" -- "${cur}") )
            return 0
            ;;
    esac

    if [[ "${cur}" == -* ]]; then
        COMPREPLY=( $(compgen -W "--benchmark --remote --remote-port --export --export-continuous --export-interval --export-format --output --config --version --help" -- "${cur}") )
        return 0
    fi
}

complete -F _visage_completion visage
