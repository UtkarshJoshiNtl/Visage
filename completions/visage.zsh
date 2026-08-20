# Zsh completion for visage
_compdef visage() {
    _arguments \
        '--benchmark[Run benchmarks]' \
        '--remote[Start remote monitoring server]' \
        '--remote-port[Remote server port]:port:' \
        '--export[Snapshot metrics to JSON]' \
        '--export-continuous[Continuous CSV export]' \
        '--export-interval[Export interval in seconds]:seconds:' \
        '--export-format[Export format]:format:(json jsonl)' \
        '--output[Output path for export]:path:_files' \
        '--config[Path to config JSON]:path:_files' \
        '--version[Show version]' \
        '--help[Show help message]'
}
