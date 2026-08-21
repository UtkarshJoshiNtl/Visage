"""Entry point for ``python -m visage``.

Usage:
    python -m visage              # Live dashboard (default)
    python -m visage --benchmark  # Run benchmarks
    python -m visage --remote     # Start remote monitoring server
    python -m visage --export     # Snapshot metrics to JSON
    python -m visage --export-continuous  # Continuous CSV export
    visage                        # Same as above (if installed)
"""

import argparse
import signal
import sys
import time
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="visage",
        description="System performance dashboard",
        epilog="See https://github.com/anomalyco/visage",
    )
    parser.add_argument(
        "--benchmark",
        action="store_true",
        help="Run CPU, memory, and disk benchmarks",
    )
    parser.add_argument(
        "--remote",
        action="store_true",
        help="Start remote monitoring HTTP server (default port 8090)",
    )
    parser.add_argument(
        "--remote-port",
        type=int,
        default=8090,
        help="Remote server port",
    )
    parser.add_argument(
        "--remote-host",
        type=str,
        default="127.0.0.1",
        help="Remote server bind address (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--export",
        action="store_true",
        help="Snapshot metrics once to JSON",
    )
    parser.add_argument(
        "--export-continuous",
        action="store_true",
        help="Continuous CSV export at regular intervals",
    )
    parser.add_argument(
        "--export-interval",
        type=float,
        default=5.0,
        help="Interval in seconds for continuous export (default: 5.0)",
    )
    parser.add_argument(
        "--export-format",
        choices=["json", "jsonl"],
        default="json",
        help="Export format: json (single file) or jsonl (JSON lines, one per line)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=str(Path.home() / "visage_snapshot.json"),
        help="Output path for --export",
    )
    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="Path to config JSON",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"visage {__import__('visage').__version__}",
    )
    args = parser.parse_args()

    if args.benchmark:
        _run_benchmark()
    elif args.remote:
        _run_remote(args.remote_host, args.remote_port)
    elif args.export:
        _run_export(args.output, args.export_format)
    elif args.export_continuous:
        _run_export_continuous(args.output, args.export_interval)
    else:
        _run_dashboard(args.config)


def _run_dashboard(config_path: str | None = None) -> None:
    from visage.app import VisageApp

    app = VisageApp(config_path=config_path)
    sys.exit(app.run())


def _run_benchmark() -> None:
    from rich.console import Console
    from rich.table import Table

    from visage.benchmark.runner import BenchmarkRunner

    console = Console()
    runner = BenchmarkRunner()

    console.print("[bold]Visage Benchmark Suite[/]\n")

    for name, method in [("CPU", runner.cpu), ("Memory", runner.memory), ("Disk", runner.disk)]:
        with console.status(f"Running {name.lower()} benchmark..."):
            result = method()
        table = Table(title=name, box=None)
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="yellow")
        for key, val in result.items():
            if key == "score":
                table.add_row("Score", str(val))
            elif "bandwidth" in key and isinstance(val, (int, float)):
                from visage.util import format_rate
                table.add_row(key.replace("_", " ").title(), format_rate(val))
            elif isinstance(val, float):
                table.add_row(key.replace("_", " ").title(), f"{val:.2f}")
            else:
                table.add_row(key.replace("_", " ").title(), str(val))
        console.print(table)
        console.print()


def _run_remote(host: str = "127.0.0.1", port: int = 8090) -> None:
    from visage.remote.server import serve

    print(f"Starting Visage remote monitoring on {host}:{port}...")
    serve(host=host, port=port)


def _run_export(path: str, fmt: str = "json") -> None:
    from visage.collectors import cpu, disk, gpu, memory, network, process
    from visage.collectors.sensors import collect as collect_sensors
    from visage.collectors.battery import collect as collect_battery
    from visage.export.exporter import export_json, export_json_lines

    snapshot = {
        "cpu": cpu.collect(),
        "memory": memory.collect(),
        "disk": disk.collect(),
        "network": network.collect(),
        "gpu": gpu.collect(),
        "processes": process.collect(top_n=20),
        "sensors": collect_sensors(),
        "battery": collect_battery(),
    }

    if fmt == "jsonl":
        result = export_json_lines(path, snapshot)
    else:
        result = export_json(snapshot, path)
    print(f"Snapshot written to {result}")


def _run_export_continuous(path: str, interval: float) -> None:
    from visage.collectors import cpu, disk, memory, network
    from visage.export.exporter import export_csv

    print(f"Continuous export to {path} every {interval}s (Ctrl+C to stop)...")
    running = True

    def _stop(sig, frame):
        nonlocal running
        running = False

    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)

    while running:
        cpu_data = cpu.collect()
        mem_data = memory.collect()
        disk_data = disk.collect()
        net_data = network.collect()
        snapshot = {
            "timestamp": time.time(),
            "cpu_percent": cpu_data.get("percent", 0),
            "mem_percent": mem_data.get("percent", 0),
            "mem_used": mem_data.get("used", 0),
            "disk_read": disk_data.get("total", {}).get("read_bytes", 0),
            "disk_write": disk_data.get("total", {}).get("write_bytes", 0),
            "net_recv": net_data.get("total", {}).get("bytes_recv", 0),
            "net_sent": net_data.get("total", {}).get("bytes_sent", 0),
        }
        export_csv([snapshot], path)
        time.sleep(interval)

    print(f"\nExport stopped. Data written to {path}")


if __name__ == "__main__":
    main()
