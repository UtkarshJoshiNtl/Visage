"""Entry point for ``python -m visage``.

Usage:
    python -m visage              # Live dashboard (default)
    python -m visage --benchmark  # Run benchmarks
    python -m visage --remote     # Start remote monitoring server
    python -m visage --export     # Snapshot metrics to JSON
    visage                        # Same as above (if installed)
"""

import argparse
import sys
import time


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
        "--export",
        action="store_true",
        help="Snapshot metrics once to JSON",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="visage_snapshot.json",
        help="Output path for --export",
    )
    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="Path to config JSON",
    )
    args = parser.parse_args()

    if args.benchmark:
        _run_benchmark()
    elif args.remote:
        _run_remote(args.remote_port)
    elif args.export:
        _run_export(args.output)
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


def _run_remote(port: int) -> None:
    from visage.remote.server import serve

    print(f"Starting Visage remote monitoring on port {port}...")
    serve(port=port)


def _run_export(path: str) -> None:
    from visage.collectors import cpu, disk, gpu, memory, network, process
    from visage.collectors.sensors import collect as collect_sensors
    from visage.export.exporter import export_json

    snapshot = {
        "cpu": cpu.collect(),
        "memory": memory.collect(),
        "disk": disk.collect(),
        "network": network.collect(),
        "gpu": gpu.collect(),
        "processes": process.collect(),
        "sensors": collect_sensors(),
    }
    result = export_json(snapshot, path)
    print(f"Snapshot written to {result}")


if __name__ == "__main__":
    main()
