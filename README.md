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
| **CPU** | Total usage bar, per-core breakdown, model name, frequency, uptime, context switches |
| **Memory** | RAM bar with used/total, swap usage |
| **Disk** | Read/write throughput in real time |
| **Network** | Download/upload speeds |
| **GPU** | SM/memory utilization, clocks, power, temperature, roofline analysis (when present) |
| **Sensors** | CPU temperature and RAPL power consumption |
| **Processes** | Top processes with sort, tree view, filtering, detail panel, signal sending |

**Controls:**

| Key | Action |
|-----|--------|
| `q` | Quit |
| `r` | Force refresh |
| `d` | Cycle refresh speed (0.5s → 1s → 2s → 5s) |
| `up`/`down` | Navigate process list |
| `s` | Cycle sort mode (CPU → MEM → PID → NAME) |
| `t` | Toggle tree view |
| `/` | Filter/search processes |
| `Enter` | Toggle detail panel for selected process |
| `x` | Send signal to selected process |
| `Esc` | Close detail/filter/signal panel |

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

### Configuration

Visage reads `visage.json` from the current directory, `~/.config/visage/config.json`, or `~/.visage.json`. Every key is optional; defaults apply for anything omitted.

```jsonc
{
  "refresh": { "interval": 1.0 },
  "widgets": {
    "enabled": ["cpu", "memory", "disk", "network", "gpu", "processes"],
    "order": ["cpu", "memory", "disk", "network", "gpu", "processes"]
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

- `widgets.enabled` toggles dashboard sections; disabling one removes it from the UI (and its collector).
- `thresholds` color-code the utilization bars; GPU keys use the `gpu_*` prefix.
- `alerts` pop a toast when a snapshot value passes the rule; `op` is one of `gt|lt|gte|lte` and `cooldown` (seconds) suppresses repeats.

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
    ├── alert.py                # Rule-based alert engine (threshold checks, cooldowns)
    ├── config.py               # Zero-dependency JSON config loader
    ├── style.tcss              # Tokyo Night inspired theme (CSS for TUI)
    ├── util.py                 # format_bytes, format_rate, DeltaTracker, sparklines
    ├── collectors/
    │   ├── cpu.py              # Raw /proc/stat parser (no psutil)
    │   ├── memory.py           # Raw /proc/meminfo parser (no psutil)
    │   ├── disk.py             # Cumulative disk I/O via psutil
    │   ├── network.py          # Cumulative net I/O via psutil
    │   ├── process.py          # psutil.process_iter, sorted by CPU%
    │   ├── gpu.py              # NVIDIA (NVML) / AMD (AMDSMI) metrics, roofline data
    │   ├── perf.py             # Hardware PMU counters via perf_event_open + ctypes
    │   ├── sensors.py          # Temperatures + RAPL power
    │   └── cache.py            # /proc/cpuinfo cache topology
    ├── widgets/
    │   ├── cpu.py              # ProgressBar + per-core sparkline
    │   ├── memory.py           # ProgressBar + used/total + swap
    │   ├── disk.py             # Read/write rates
    │   ├── network.py          # ↓↑ throughput
    │   ├── gpu.py              # Utilization, clocks, power, roofline + bound-by
    │   └── processes.py        # Rich Table of top-N processes
    ├── benchmark/
    │   └── runner.py           # CPU pi, memory bandwidth, disk sequential
    ├── runners/
    │   ├── __init__.py         # Public API: run_isolated, run_benchmark
    │   └── isolated.py         # CpuCage, CpufreqLock, BenchmarkResult, BenchmarkSummary
    ├── tracing/
    │   ├── __init__.py         # create_tracer factory
    │   └── tracer.py           # BCC eBPF tracer + /proc polling fallback
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
- **Raw /proc parsers** replace psutil for CPU and memory — single FD opened once, seek(0) each tick.
- **No third-party deps for PMU counters** — `perf_event_open` called via raw `ctypes`.
- **Graceful degradation** — all kernel-level features (eBPF, PMU, cpuset, frequency lock) fall back to unprivileged alternatives when root/permissions are unavailable.

### Hardware Sandbox (Checkpoint 5)

```
run_benchmark("binary", core_id=3, target_freq_khz=3000000, iterations=10)
  │
  ├─ CpuCage(cpuset cgroup v2 → sched_setaffinity)
  │    └─ CpufreqLock(save governor+min+max → performance@3GHz)
  │
  ├─ [10 iterations]
  │    ├─ perf_event_open(cpu=3, disabled=True)
  │    ├─── reset + enable
  │    ├─── spawn via taskset -c 3
  │    ├─── wait / measure
  │    └─── disable + read
  │
  └─ BenchmarkSummary
       ├─ μ, σ for IPC, cache misses, wall time
       └─ noisy if any CV > max_sigma_pct
```

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
```

### Roadmap

- [x] Core dashboard (CPU, memory, disk, network, processes)
- [x] Benchmark mode
- [x] Process tracing (BCC eBPF + /proc fallback)
- [x] Temperature & power sensors
- [x] Cache statistics
- [x] JSON/CSV export
- [x] Remote monitoring via FastAPI
- [x] **Hardware sandbox** — core isolation + frequency lock + PMU counters + noise filtering
- [x] GPU metrics (NVIDIA / AMD) with roofline analysis
- [x] Historical graphs (sparklines)
- [x] Config file (which metrics to show, thresholds) + alert rules
- [ ] Docker support

## License

MIT
