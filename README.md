# Visage — System Performance Dashboard

> A live terminal UI that puts your system's vital metrics at your fingertips.
> Built for developers who want to understand what their machine is doing, in real time.

```
┌──────────────────────────────────────────────────────┐
│  Visage                         Theme: Nord  Ctrl+Q  │
│                                                       │
│  CPU — AMD Ryzen 9 5950X                              │
│  ████████████████████████░░░░░░░  83%                 │
│  4.8 GHz   Uptime: 14d 3h   Ctx: 1.2M/s             │
│                                                       │
│  Memory                                               │
│  ██████████████████░░░░░░░░░░░  6.3 / 15.5 GB        │
│  Swap: 0.5 / 2.0 GB                                   │
│                                                       │
│  Network                                              │
│  ↓ 18.2 Mb/s  ↑ 2.1 Mb/s   ↓ 120 GB  ↑ 45 GB       │
│  eth0  192.168.1.42  ↓18.2Mb/s  ↑2.1Mb/s            │
│                                                       │
│  Sensors — Core: 65°C  NVMe: 42°C  CPU Fan: 1200 RPM │
│                                                       │
│  Processes                                            │
│  Name                  PID    CPU%   Mem%    RSS      │
│  ▶ firefox             1234   12.3    8.1   1.2 GB   │
│    python3             5678    8.7    4.2   680 MB   │
│    clang              12345    5.1    2.8   450 MB   │
│                                                       │
│  q:Quit r:Refresh d:Speed t:Theme s:Sort a:Agg v:Vim │
│  l:Long n:Nice /:Filter x:Signal enter:Detail         │
└──────────────────────────────────────────────────────┘
```

---

## Quick Start

```bash
# Install from PyPI
pip install visage

# Or install from source
git clone https://github.com/anomalyco/visage
cd visage
pip install -e .

# Run the dashboard
visage
```

## Usage

### Dashboard Mode (default)

Shows live metrics in a terminal UI:

| Section | Shows |
|---------|-------|
| **CPU** | Total usage bar, per-core mini-graphs, model name, frequency, uptime, context switches |
| **Memory** | RAM bar with used/total, swap usage, buffers/cached/reclaimable breakdown |
| **Disk** | Per-partition read/write rates, usage bars with mount points and space info |
| **Network** | Per-interface download/upload rates with IP addresses, cumulative totals |
| **GPU** | SM/memory utilization, clocks, power, temperature, roofline analysis, sparkline graphs |
| **Sensors** | CPU temperature, NVMe temps, fan speeds (hwmon), RAPL power consumption |
| **Battery** | Charge level with bar and status (when present) |
| **Docker** | Container CPU/Memory/Net/Block I/O stats (when Docker available) |
| **Processes** | Top processes with sort, tree view, aggregate mode, filtering, detail panel, signal sending, vim navigation |

### Controls

**Global:**

| Key | Action |
|-----|--------|
| `q` | Quit |
| `r` | Force refresh all metrics |
| `d` | Cycle refresh speed (0.5s → 1s → 2s → 5s) |
| `t` | Cycle color themes (Tokyo Night → Dracula → Gruvbox → Nord → Monokai → Solarized) |

**Process widget** (when focused):

| Key | Action |
|-----|--------|
| `up`/`down` | Navigate process list |
| `PageUp`/`PageDown` | Page through process list (10 rows) |
| `s` | Cycle sort mode. First press toggles direction, subsequent presses cycle CPU → MEM → PID → NAME |
| `a` | Toggle aggregate mode (group processes by name, show totals) |
| `t` | Toggle tree view (parent/child hierarchy) |
| `v` | Toggle vim keybinding mode |
| `l` | Toggle long command line display |
| `n` | Renice selected process (set priority) |
| `/` | Filter/search processes by name |
| `Enter` | Toggle detail panel for selected process |
| `x` | Send signal to selected process |
| `Esc` | Close detail/filter/signal panel |

### Vim Mode

Press `v` to enter vim mode, then use:

| Key | Action |
|-----|--------|
| `j`/`k` | Move down/up one row |
| `h`/`l` | Move up/down 5 rows |
| `gg` | Jump to first process |
| `G` | Jump to last process |
| `Esc` | Exit vim mode |

### Aggregate Mode

Press `a` to collapse processes by name. Shows total CPU/MEM/RSS across all instances with a count `(N)`. Great for seeing total resource usage of multi-process apps like Chrome or Firefox.

### Benchmark Mode

```bash
visage --benchmark
```

Runs three performance tests inline and prints scored results:

- **CPU** — Leibniz pi approximation (iterations/second)
- **Memory** — Sequential read/write bandwidth (MB/s)
- **Disk** — Sequential write/read on a temp file (MB/s)

### Hardware-Isolated Benchmark Runner

Programmatic entry points for deterministic, noise-filtered benchmarking:

```python
from visage.runners import run_isolated, run_benchmark

# Single run on core 3 with PMU counters
r = run_isolated("/usr/bin/myapp", core_id=3)

# Repeated runs with statistical noise filtering
s = run_benchmark("/usr/bin/myapp", core_id=3,
                  iterations=10, max_sigma_pct=1.0)
print(f"IPC: μ={s.ipc_mean:.3f} σ={s.ipc_std:.3f} noisy={s.noisy}")
```

Features:
- **Core isolation** — cpuset cgroup v2 (root) → `sched_setaffinity` fallback
- **Frequency lock** — saves governor + min/max freq, sets `performance` governor at a constant kHz
- **Hardware PMU counters** — `perf_event_open` via raw ctypes (cycles, instructions, cache misses, IPC)
- **Noise filtering** — runs N iterations, computes μ and σ, flags if any CV exceeds threshold

All features degrade gracefully when unprivileged (WSL2, no root).

### Themes

Press `t` to cycle through 6 built-in themes:

| Theme | Style |
|-------|-------|
| **Tokyo Night** | Default — dark blue with cyan accents |
| **Dracula** | Purple accents on dark gray |
| **Gruvbox** | Retro warm colors with yellow accents |
| **Nord** | Arctic blue palette |
| **Monokai** | Vibrant colors on dark background |
| **Solarized** | Precision colors for machines and people |

Custom themes can be loaded from TOML files:

```json
{
  "theme": "dracula"
}
```

Or create your own theme file:

```toml
[meta]
display_name = "My Theme"
graph_style = "braille"

[colors]
bg = "#1a1b26"
card = "#24283b"
border = "#3b4261"
accent = "#7aa2f7"
text = "#a9b1d6"
graph = "#7dcfff"
dim = "#565f89"
```

### Configuration

Visage reads config from (in order of priority):

1. `visage.json` in the current directory
2. `~/.config/visage/config.json`
3. `~/.visage.json`

Every key is optional; defaults apply for anything omitted.

```jsonc
{
  "refresh": { "interval": 1.0 },
  "theme": "default",
  "graph_style": "braille",
  "widgets": {
    "enabled": ["cpu", "memory", "disk", "network", "gpu", "psi", "sensors", "battery", "docker", "processes"],
    "order": ["cpu", "memory", "disk", "network", "gpu", "psi", "sensors", "battery", "docker", "processes"]
  },
  "thresholds": {
    "cpu":     { "red": 80, "yellow": 50 },
    "memory":  { "red": 90, "yellow": 75 },
    "gpu_sm_util":   { "red": 80, "yellow": 50 },
    "gpu_mem_util":  { "red": 80, "yellow": 50 },
    "gpu_temp_c":    { "red": 85, "yellow": 70 },
    "gpu_power_w":   { "red": 90, "yellow": 75 }
  },
  "gpu": { "arch_override": null },
  "alerts": [
    { "name": "cpu-hot", "metric": "cpu_percent", "op": "gt",
      "value": 80, "cooldown": 60, "message": "CPU at {value}%" }
  ]
}
```

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `refresh.interval` | float | `1.0` | Dashboard refresh interval in seconds |
| `theme` | string | `"default"` | Built-in theme name or path to custom TOML theme |
| `graph_style` | string | `"braille"` | Graph rendering: `"braille"`, `"block"`, `"ascii"`, or `"auto"` |
| `widgets.enabled` | list | all | Which sections to show |
| `widgets.order` | list | default | Display order of sections |
| `thresholds` | dict | see above | Color thresholds for utilization bars |
| `gpu.arch_override` | string | `null` | Force GPU architecture detection |
| `alerts` | list | `[]` | Alert rules (see below) |

Alert rules: `op` is one of `gt|lt|gte|lte`, `cooldown` (seconds) suppresses repeats.

### Remote Monitoring

```bash
visage --remote
visage --remote --remote-port 9090  # custom port
```

Exposes all metrics as JSON over HTTP, with per-metric endpoints and WebSocket streaming:

```bash
curl http://localhost:8090/metrics
curl http://localhost:8090/cpu
curl http://localhost:8090/memory
curl http://localhost:8090/gpu
```

Prometheus-compatible metrics:

```bash
curl http://localhost:8090/metrics/prometheus
# → visage_cpu_percent 42.5
# → visage_memory_percent 63.2
# → visage_memory_used 10240000000
```

WebSocket for real-time streaming:
```bash
wscat -c ws://localhost:8090/ws/metrics
```

Endpoints:

| Route | Description |
|-------|-------------|
| `GET /` | Service info and version |
| `GET /metrics` | Full system snapshot (all metrics) |
| `GET /metrics/prometheus` | Prometheus exposition format |
| `GET /cpu` | CPU metrics only |
| `GET /memory` | Memory metrics only |
| `GET /disk` | Disk metrics only |
| `GET /network` | Network metrics only |
| `GET /gpu` | GPU metrics only |
| `GET /processes` | Process list |
| `GET /sensors` | Temperature, fans, and power |
| `GET /battery` | Battery status |
| `GET /health` | Health check |
| `WS /ws/metrics` | Real-time streaming (CPU, memory, disk, network, processes) |

### Export

```bash
# JSON snapshot (default)
visage --export
visage --export --output /tmp/metrics.json

# JSON Lines format (append-friendly, one JSON object per line)
visage --export --export-format jsonl --output metrics.jsonl
```

Writes a one-shot snapshot of all metrics to a file (ISO timestamped).

### Continuous Export

```bash
visage --export-continuous --export-interval 5 --output metrics.csv
```

Writes metrics to CSV at regular intervals. Ctrl+C to stop.

### Shell Completions

Shell completions are available in `completions/`:

```bash
# Bash — add to ~/.bashrc
source /path/to/visage/completions/visage.bash

# Zsh — add to ~/.zshrc
source /path/to/visage/completions/visage.zsh

# Fish — copy to completions directory
cp completions/visage.fish ~/.config/fish/completions/
```

### Man Page

```bash
man ./visage.1
```

## CLI Reference

```
visage [OPTIONS]

Options:
  --benchmark              Run CPU, memory, and disk benchmarks
  --remote                 Start remote monitoring HTTP server
  --remote-port PORT       Remote server port (default: 8090)
  --export                 Snapshot metrics once to JSON
  --export-continuous      Continuous CSV export at regular intervals
  --export-interval SECS   Interval for continuous export (default: 5.0)
  --export-format FORMAT   Export format: json or jsonl (default: json)
  --output PATH            Output path for --export (default: visage_snapshot.json)
  --config PATH            Path to config JSON
  --version                Show version and exit
  -h, --help               Show help message
```

## Architecture

```
visage/
├── pyproject.toml              # Package metadata, dependencies, entry point
├── visage.1                    # Man page
├── completions/                # Shell completions (bash/zsh/fish)
│   ├── visage.bash
│   ├── visage.zsh
│   └── visage.fish
├── README.md
└── visage/
    ├── __init__.py
    ├── __main__.py             # CLI dispatcher (dashboard / benchmark / remote / export)
    ├── app.py                  # Textual Application, timer, data wiring, theme cycling
    ├── alert.py                # Rule-based alert engine (threshold checks, cooldowns)
    ├── config.py               # Zero-dependency JSON config loader
    ├── theme.py                # TOML theme engine, TCSS generation
    ├── style.tcss              # Tokyo Night inspired theme (CSS for TUI)
    ├── util.py                 # format_bytes, format_rate, DeltaTracker, sparklines, ASCII fallback
    ├── collectors/
    │   ├── cpu.py              # Raw /proc/stat parser (no psutil)
    │   ├── memory.py           # Raw /proc/meminfo parser (no psutil)
    │   ├── disk.py             # Cumulative disk I/O via psutil
    │   ├── network.py          # Cumulative net I/O + per-process network approximation
    │   ├── process.py          # psutil.process_iter, sort/tree/aggregate/filter
    │   ├── gpu.py              # NVIDIA (NVML) / AMD (AMDSMI) metrics, roofline data
    │   ├── perf.py             # Hardware PMU counters via perf_event_open + ctypes
    │   ├── sensors.py          # Temperatures, fan speeds (hwmon), RAPL power
    │   ├── psi.py              # Pressure Stall Information (CPU/memory/IO)
    │   ├── battery.py          # Battery status from sysfs
    │   ├── docker.py           # Container stats via docker CLI
    │   └── cache.py            # /proc/cpuinfo cache topology
    ├── widgets/
    │   ├── cpu.py              # ProgressBar + per-core sparkline
    │   ├── memory.py           # ProgressBar + used/total + swap
    │   ├── disk.py             # Read/write rates
    │   ├── network.py          # ↓↑ throughput + cumulative totals
    │   ├── gpu.py              # Utilization, clocks, power, roofline + bound-by
    │   ├── psi.py              # Pressure stall sparklines
    │   ├── sensors.py          # Temps, fans, power
    │   ├── battery.py          # Battery level bar
    │   ├── docker.py           # Container stats table
    │   └── processes.py        # Rich Table with sort/tree/aggregate/vim/filter/signals
    ├── themes/                  # Built-in TOML theme files
    │   ├── default.toml        # Tokyo Night
    │   ├── dracula.toml
    │   ├── gruvbox.toml
    │   ├── nord.toml
    │   ├── monokai.toml
    │   └── solarized.toml
    ├── benchmark/
    │   └── runner.py           # CPU pi, memory bandwidth, disk sequential
    ├── runners/
    │   ├── __init__.py         # Public API: run_isolated, run_benchmark
    │   └── isolated.py         # CpuCage, CpufreqLock, BenchmarkResult, BenchmarkSummary
    ├── tracing/
    │   ├── __init__.py         # create_tracer factory
    │   └── tracer.py           # BCC eBPF tracer + /proc polling fallback
    ├── export/
    │   └── exporter.py         # JSON / JSON Lines / CSV / log append / Prometheus format
    └── remote/
        └── server.py           # FastAPI app exposing /metrics + Prometheus endpoint
```

### Design Decisions

- **Collectors are stateless** — they return plain dicts. Stateful rate computation (disk, network deltas) lives in `DeltaTracker` in `util.py`, owned by the app layer.
- **Widgets use Textual reactives** — each widget exposes `reactive` attributes. Setting them triggers targeted re-renders.
- **Theme system is TOML-based** — themes define color variables that generate TCSS dynamically. No external deps.
- **Per-process network is approximated** — uses `/proc/[pid]/net/dev` deltas attributed proportionally by CPU usage (no netlink required).
- **ASCII fallback is automatic** — SSH sessions and non-UTF terminals get block/ASCII graphs instead of braille.
- **Remote mode shares the same code** — `visage --remote` starts a FastAPI server that calls the identical `collectors.*` functions.
- **Raw /proc parsers** replace psutil for CPU and memory — single FD opened once, seek(0) each tick.
- **No third-party deps for PMU counters** — `perf_event_open` called via raw `ctypes`.
- **Graceful degradation** — all kernel-level features (eBPF, PMU, cpuset, frequency lock) fall back to unprivileged alternatives when root/permissions are unavailable.

## Requirements

- Python ≥ 3.11
- Linux (for full sensor, PMU, and cache support; macOS works with reduced features)

Dependencies (installed automatically):

| Package | Purpose |
|---------|---------|
| `psutil` | System metrics (disk, network, processes; CPU & memory use raw /proc) |
| `textual` | Terminal UI framework |
| `rich` | Pretty terminal output (tables, formatting) |
| `fastapi` + `uvicorn` | Remote monitoring web server (optional) |
| `python3-bpfcc` | eBPF process tracer via BCC (optional, requires root) |

## Development

```bash
git clone https://github.com/anomalyco/visage
cd visage
pip install -e ".[dev]"
python -m pytest tests/ -v
```

### Roadmap

- [x] Core dashboard (CPU, memory, disk, network, processes)
- [x] Benchmark mode
- [x] Process tracing (BCC eBPF + /proc fallback)
- [x] Temperature & power sensors
- [x] Cache statistics
- [x] JSON/CSV export
- [x] Remote monitoring via FastAPI
- [x] Hardware sandbox (core isolation + frequency lock + PMU counters + noise filtering)
- [x] GPU metrics (NVIDIA / AMD) with roofline analysis
- [x] Historical graphs (sparklines)
- [x] Config file (which metrics to show, thresholds) + alert rules
- [x] Docker support
- [x] Interactive process management (sort, tree, filter, detail, signals)
- [x] Per-disk and per-network interface breakdown
- [x] Battery monitor
- [x] Block graph rendering and per-core CPU mini-graphs
- [x] WebSocket streaming for remote monitoring
- [x] Continuous CSV export mode
- [x] Aggregate multi-process view, nice column, renice, vim mode, PgUp/PgDown
- [x] Fan speeds (hwmon), per-process network, cumulative network totals
- [x] Theme engine (TOML), 6 built-in themes, SSH/ASCII fallback
- [x] JSON Lines export, Prometheus endpoint, man page, tab completions, PyPI packaging

## License

MIT
