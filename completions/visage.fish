# Fish completion for visage
complete -c visage -l benchmark -d 'Run benchmarks'
complete -c visage -l remote -d 'Start remote monitoring server'
complete -c visage -l remote-port -d 'Remote server port' -r
complete -c visage -l export -d 'Snapshot metrics to JSON'
complete -c visage -l export-continuous -d 'Continuous CSV export'
complete -c visage -l export-interval -d 'Export interval in seconds' -r
complete -c visage -l output -d 'Output path for export' -r -F
complete -c visage -l config -d 'Path to config JSON' -r -F
complete -c visage -l help -d 'Show help message'
