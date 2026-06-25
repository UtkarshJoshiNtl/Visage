# Visage — System Performance Dashboard

> A live terminal UI that puts your system's vital metrics at your fingertips.
> Built for developers who want to understand what their machine is doing, in real time.

```
┌──────────────────────────────────────────────────┐
│  Visage                                Ctrl+Q ╳  │
│                                                    │
│  CPU                                               │
│  ███████████████████████░░░░░░░  83%               │
│  C0:85%  C1:72%  C2:91%  C3:64%                  │
│                                                    │
│  Memory                                            │
│  ██████████████████░░░░░░░░░░░  6.3 / 15.5 GB     │
│  Swap: 0.5 / 2.0 GB                                │
│                                                    │
│  Disk                                              │
│  Read:  320 MB/s   Write: 150 MB/s                │
│                                                    │
│  Network                                           │
│  ↓  18 MB/s    ↑  2 MB/s                           │
│                                                    │
│  Processes                                         │
│  python     42.1                                    │
│  clang      18.3                                    │
│  Xorg        5.2                                    │
│  ...                                                │
├──────────────────────────────────────────────────┤
│  q:Quit  r:Refresh  d:Speed                       │
└──────────────────────────────────────────────────┘
```

---

## Quick Start

```bash
# Install
pip install -e .

# Run the dashboard
visage
# or
python -m visage
```

## Usage

### Dashboard Mode (default)

Shows live metrics in a terminal UI:

| Section | Shows |
|---------|-------|
| **CPU** | Total usage bar, per-core breakdown with color-coded indicators |
| **Memory** | RAM bar with used/total, swap usage |
| **Disk** | Read/write throughput in real time |
| **Network** | Download/upload speeds |
| **Processes** | Top processes sorted by CPU usage |

**Controls:**

| Key | Action |
|-----|--------|
| `q` | Quit |
| `r` | Force refresh |
| `d` | Cycle refresh speed (0.5s → 1s → 2s → 5s) |

### Benchmark Mode

```bash
visage --benchmark
```

Runs three performance tests inline and prints scored results:

- **CPU** — Leibniz pi approximation (iterations/second)
- **Memory** — Sequential read/write bandwidth (MB/s)
- **Disk** — Sequential write/read on a temp file (MB/s)

### Remote Monitoring

```bash
visage --remote
# → serving on http://0.0.0.0:8090
```

Exposes all metrics at `/metrics` as JSON over HTTP:

```bash
curl http://localhost:8090/metrics
```

Endpoints:

| Route | Description |
|-------|-------------|
| `GET /` | Service info |
| `GET /metrics` | Full system snapshot |
| `GET /health` | Health check |

### Export

```bash
visage --export
# → visage_snapshot.json

visage --export --output /tmp/metrics.json
```

Writes a one-shot snapshot of all metrics to a JSON file (ISO timestamped).

## Architecture

```
visage/
├── pyproject.toml              # Package metadata, dependencies, entry point
├── README.md
└── visage/
    ├── __init__.py
    ├── __main__.py             # CLI dispatcher (dashboard / benchmark / remote / export)
    ├── app.py                  # Textual Application, timer, data wiring
    ├── style.tcss              # Tokyo Night inspired theme (CSS for TUI)
    ├── util.py                 # format_bytes, format_rate, DeltaTracker
    ├── collectors/
    │   ├── cpu.py              # psutil.cpu_percent, cpu_freq, cpu_stats
    │   ├── memory.py           # psutil.virtual_memory, swap_memory
    │   ├── disk.py             # psutil.disk_io_counters (cumulative)
    │   ├── network.py          # psutil.net_io_counters (cumulative)
    │   ├── process.py          # psutil.process_iter, sorted by CPU%
    │   ├── sensors.py          # Temperatures + RAPL power
    │   └── cache.py            # /proc/cpuinfo cache topology
    ├── widgets/
    │   ├── cpu.py              # ProgressBar + per-core sparkline
    │   ├── memory.py           # ProgressBar + used/total + swap
    │   ├── disk.py             # Read/write rates
    │   ├── network.py          # ↓↑ throughput
    │   └── processes.py        # Rich Table of top-N processes
    ├── benchmark/
    │   └── runner.py           # CPU pi, memory bandwidth, disk sequential
    ├── tracing/
    │   └── tracer.py           # /proc-based process birth/death monitor
    ├── export/
    │   └── exporter.py         # JSON / CSV / log append
    └── remote/
        └── server.py           # FastAPI app exposing /metrics
```

### Design Decisions

- **Collectors are stateless** — they return plain dicts. Stateful rate computation (disk, network deltas) lives in `DeltaTracker` in `util.py`, owned by the app layer. This makes the collectors reusable for the remote API without modification.
- **Widgets use Textual reactives** — each widget exposes `reactive` attributes. Setting them triggers targeted re-renders, avoiding full-screen redraws.
- **Refresh rate is adjustable** — `d` cycles between 0.5s, 1s (default), 2s, and 5s.
- **Remote mode shares the same code** — `visage --remote` starts a FastAPI server that calls the identical `collectors.*` functions.

## Requirements

- Python ≥ 3.11
- Linux (for full sensor and cache support; macOS works with reduced features)

Dependencies (installed automatically):

| Package | Purpose |
|---------|---------|
| `psutil` | System metrics (CPU, memory, disk, network, processes) |
| `textual` | Terminal UI framework |
| `rich` | Pretty terminal output (tables, formatting) |
| `fastapi` + `uvicorn` | Remote monitoring web server (optional) |

## Development

```bash
git clone https://github.com/anomalyco/visage
cd visage
pip install -e ".[dev]"
```

### Roadmap

- [x] Core dashboard (CPU, memory, disk, network, processes)
- [x] Benchmark mode
- [x] Process tracing
- [x] Temperature & power sensors
- [x] Cache statistics
- [x] JSON/CSV export
- [x] Remote monitoring via FastAPI
- [ ] GPU metrics (NVIDIA / AMD)
- [ ] Historical graphs (sparklines)
- [ ] Config file (which metrics to show, thresholds)
- [ ] Docker support

## License

MIT
