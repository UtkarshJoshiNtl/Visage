# Fish completion for visage
complete -c visage -l benchmark -d 'Run benchmarks'
complete -c visage -l remote -d 'Start remote monitoring server'
complete -c visage -l remote-host -d 'Remote server bind address' -r
complete -c visage -l remote-port -d 'Remote server port' -r
complete -c visage -l export -d 'Snapshot metrics to JSON'
complete -c visage -l export-continuous -d 'Continuous CSV export'
complete -c visage -l export-interval -d 'Export interval in seconds' -r
complete -c visage -l export-format -d 'Export format' -r -a 'json jsonl'
complete -c visage -l output -d 'Output path for export' -r -F
complete -c visage -l config -d 'Path to config JSON' -r -F
complete -c visage -l ci-test -d 'Run isolated CI performance benchmark gate' -r -F
complete -c visage -l test-args -d 'Arguments passed to --ci-test executable'
complete -c visage -l core -d 'Target CPU core index for isolated benchmarking' -r
complete -c visage -l iterations -d 'Number of iterations for benchmarking' -r
complete -c visage -l max-cv -d 'Max allowable noise CV percentage' -r
complete -c visage -l min-ipc -d 'Minimum required IPC assertion' -r
complete -c visage -l max-time -d 'Maximum allowed mean wall time in seconds' -r
complete -c visage -l max-ipc-drop -d 'Max allowed IPC drop percentage under baseline' -r
complete -c visage -l max-time-increase -d 'Max allowed wall time increase percentage over baseline' -r
complete -c visage -l max-miss-increase -d 'Max allowed cache miss increase percentage over baseline' -r
complete -c visage -l baseline -d 'Path to baseline benchmark JSON file' -r -F
complete -c visage -l save-baseline -d 'Path to save current run as baseline JSON' -r -F
complete -c visage -l output-md -d 'Path to write GitHub Actions markdown summary report' -r -F
complete -c visage -l output-json -d 'Path to write JSON benchmark summary report' -r -F
complete -c visage -l version -d 'Show version'
complete -c visage -l help -d 'Show help message'
