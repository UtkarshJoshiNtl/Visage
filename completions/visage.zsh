# Zsh completion for visage
_compdef visage() {
    _arguments \
        '--benchmark[Run benchmarks]' \
        '--remote[Start remote monitoring server]' \
        '--remote-host[Remote server bind address]:host:' \
        '--remote-port[Remote server port]:port:' \
        '--export[Snapshot metrics to JSON]' \
        '--export-continuous[Continuous CSV export]' \
        '--export-interval[Export interval in seconds]:seconds:' \
        '--export-format[Export format]:format:(json jsonl)' \
        '--output[Output path for export]:path:_files' \
        '--config[Path to config JSON]:path:_files' \
        '--ci-test[Run isolated CI performance benchmark gate]:executable:_files' \
        '*--test-args[Arguments passed to --ci-test executable]:args:' \
        '--core[Target CPU core index]:core:' \
        '--iterations[Number of iterations]:iterations:' \
        '--max-cv[Max allowable noise CV percentage]:pct:' \
        '--min-ipc[Minimum required IPC assertion]:ipc:' \
        '--max-time[Maximum allowed mean wall time in seconds]:seconds:' \
        '--max-ipc-drop[Max allowed IPC drop percentage under baseline]:pct:' \
        '--max-time-increase[Max allowed wall time increase percentage over baseline]:pct:' \
        '--max-miss-increase[Max allowed cache miss increase percentage over baseline]:pct:' \
        '--baseline[Path to baseline benchmark JSON]:path:_files' \
        '--save-baseline[Path to save current run as baseline JSON]:path:_files' \
        '--output-md[Path to write GitHub Actions markdown summary]:path:_files' \
        '--output-json[Path to write JSON benchmark summary report]:path:_files' \
        '--version[Show version]' \
        '--help[Show help message]'
}
