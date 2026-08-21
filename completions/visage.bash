# Bash completion for visage
_visage_completion() {
    local cur prev
    COMPREPLY=()
    cur="${COMP_WORDS[COMP_CWORD]}"
    prev="${COMP_WORDS[COMP_CWORD-1]}"

    case "${prev}" in
        --remote-port|--remote-host|--export-interval|--output|--config|--core|--iterations|--max-cv|--min-ipc|--max-time|--max-ipc-drop|--max-time-increase|--max-miss-increase|--baseline|--save-baseline|--output-md|--output-json)
            COMPREPLY=()
            return 0
            ;;
        --export-format)
            COMPREPLY=( $(compgen -W "json jsonl" -- "${cur}") )
            return 0
            ;;
        --ci-test)
            COMPREPLY=( $(compgen -f -- "${cur}") )
            return 0
            ;;
        --test-args)
            COMPREPLY=()
            return 0
            ;;
    esac

    if [[ "${cur}" == -* ]]; then
        COMPREPLY=( $(compgen -W "--benchmark --remote --remote-host --remote-port --export --export-continuous --export-interval --export-format --output --config --ci-test --test-args --core --iterations --max-cv --min-ipc --max-time --max-ipc-drop --max-time-increase --max-miss-increase --baseline --save-baseline --output-md --output-json --version --help" -- "${cur}") )
        return 0
    fi
}

complete -F _visage_completion visage
