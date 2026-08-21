"""CI/CD Performance Regression & Assertion Gatekeeper.

Enables automated performance regression testing in CI/CD pipelines (e.g. GitHub Actions)
using hardware-isolated PMU profiling, statistical noise filtering, and baseline comparison.
"""

from __future__ import annotations

import dataclasses
import json
import logging
from pathlib import Path
from typing import Any, Sequence

from visage.runners.isolated import BenchmarkSummary, run_benchmark

log = logging.getLogger(__name__)


@dataclasses.dataclass(frozen=True)
class CiGateConfig:
    """Configuration for CI performance gate execution."""

    executable: str
    args: Sequence[str] = ()
    core_id: int = 0
    iterations: int = 10
    target_freq_khz: int | None = None
    max_cv_pct: float = 2.0
    timeout: float | None = None
    min_ipc: float | None = None
    max_time_s: float | None = None
    max_ipc_drop_pct: float | None = None
    max_time_increase_pct: float | None = None
    max_miss_increase_pct: float | None = None
    baseline_path: str | None = None
    save_baseline_path: str | None = None
    output_json_path: str | None = None
    output_md_path: str | None = None


@dataclasses.dataclass(frozen=True)
class CiGateResult:
    """Result of a CI performance gate check."""

    passed: bool
    violations: list[str]
    summary: BenchmarkSummary
    baseline: dict[str, Any] | None
    markdown_report: str
    data: dict[str, Any]


def generate_markdown_report(
    cfg: CiGateConfig,
    summary: BenchmarkSummary,
    violations: list[str],
    baseline: dict[str, Any] | None = None,
) -> str:
    """Generate a GitHub Action summary compatible markdown report."""
    status_emoji = "\u2705 **PASSED**" if not violations else "\u274c **FAILED (REGRESSION DETECTED)**"
    status_alert = "> [!NOTE]\n> All performance assertions passed." if not violations else (
        "> [!CAUTION]\n> **Performance Regression Violations:**\n> - " + "\n> - ".join(violations)
    )

    lines = [
        f"## Visage Performance Gate: {status_emoji}",
        "",
        status_alert,
        "",
        "### Benchmark Environment & Settings",
        "",
        f"- **Executable**: `{cfg.executable}`",
        f"- **Arguments**: `{' '.join(map(str, cfg.args)) or '(none)'}`",
        f"- **Isolated Core**: CPU {summary.core_id} ({'cpuset v2' if summary.isolated else 'pinned'})",
        f"- **Frequency Lock**: {'Active' if summary.freq_locked else 'Inactive'}",
        f"- **PMU Counters**: {'Accessible' if summary.available else 'Unavailable (wall-clock only)'}",
        f"- **Iterations**: {summary.iterations}",
        f"- **Max Allowed CV (Noise)**: {cfg.max_cv_pct:.1f}%",
        "",
        "### Profiling Results Summary",
        "",
        "| Metric | Current Mean (\u03bc) | Current Std (\u03c3) | CV (%) | Baseline | Delta | Status |",
        "| :--- | :--- | :--- | :--- | :--- | :--- | :--- |",
    ]

    def _format_row(name: str, cur_mean: float, cur_std: float, base_val: float | None, unit: str = "", higher_is_better: bool = False) -> str:
        cv = (cur_std / cur_mean * 100.0) if cur_mean > 0 else 0.0
        cv_str = f"{cv:.2f}%"
        cur_str = f"{cur_mean:.4f} {unit}".strip()
        std_str = f"\u00b1 {cur_std:.4f}"

        if base_val is not None and base_val > 0:
            base_str = f"{base_val:.4f} {unit}".strip()
            delta_pct = ((cur_mean - base_val) / base_val) * 100.0
            delta_str = f"{delta_pct:+.2f}%"
            if higher_is_better:
                delta_status = "\u2705" if delta_pct >= 0 else ("\u26a0\ufe0f" if delta_pct > -cfg.max_cv_pct else "\u274c")
            else:
                delta_status = "\u2705" if delta_pct <= 0 else ("\u26a0\ufe0f" if delta_pct < cfg.max_cv_pct else "\u274c")
        else:
            base_str = "N/A"
            delta_str = "N/A"
            delta_status = "\u2705" if cv <= cfg.max_cv_pct else "\u26a0\ufe0f (noisy)"

        return f"| **{name}** | {cur_str} | {std_str} | {cv_str} | {base_str} | {delta_str} | {delta_status} |"

    base_time = baseline.get("time_mean") if baseline else None
    base_ipc = baseline.get("ipc_mean") if baseline else None
    base_miss = baseline.get("miss_mean") if baseline else None

    lines.append(_format_row("Wall Time", summary.time_mean, summary.time_std, base_time, "s", higher_is_better=False))
    lines.append(_format_row("Instructions per Cycle (IPC)", summary.ipc_mean, summary.ipc_std, base_ipc, "", higher_is_better=True))
    lines.append(_format_row("LLC Cache Misses", summary.miss_mean, summary.miss_std, base_miss, "misses", higher_is_better=False))

    lines.append("")
    return "\n".join(lines)


def run_ci_gate(cfg: CiGateConfig) -> CiGateResult:
    """Execute the benchmark and evaluate all CI performance regression assertions."""
    summary = run_benchmark(
        executable=cfg.executable,
        args=cfg.args,
        core_id=cfg.core_id,
        target_freq_khz=cfg.target_freq_khz,
        iterations=cfg.iterations,
        max_sigma_pct=cfg.max_cv_pct,
        timeout=cfg.timeout,
    )

    violations: list[str] = []

    # 1. Non-zero exit code check
    for i, rc in enumerate(summary.returncodes):
        if rc != 0:
            violations.append(f"Iteration {i + 1} failed with returncode {rc}")

    # 2. Noise / statistical jitter check
    time_cv = (summary.time_std / summary.time_mean * 100.0) if summary.time_mean > 0 else 0.0
    if time_cv > cfg.max_cv_pct:
        violations.append(f"Wall time noise (CV={time_cv:.2f}%) exceeds threshold {cfg.max_cv_pct:.1f}%")

    if summary.available and summary.ipc_mean > 0:
        ipc_cv = (summary.ipc_std / summary.ipc_mean * 100.0)
        if ipc_cv > cfg.max_cv_pct:
            violations.append(f"IPC noise (CV={ipc_cv:.2f}%) exceeds threshold {cfg.max_cv_pct:.1f}%")

    # 3. Static thresholds
    if cfg.max_time_s is not None and summary.time_mean > cfg.max_time_s:
        violations.append(
            f"Mean wall time {summary.time_mean:.4f}s exceeds limit {cfg.max_time_s:.4f}s"
        )

    if cfg.min_ipc is not None and summary.available and summary.ipc_mean < cfg.min_ipc:
        violations.append(
            f"Mean IPC {summary.ipc_mean:.4f} is below minimum required {cfg.min_ipc:.4f}"
        )

    # 4. Baseline regression check
    baseline_data: dict[str, Any] | None = None
    if cfg.baseline_path:
        base_p = Path(cfg.baseline_path)
        if base_p.exists():
            try:
                with open(base_p) as f:
                    baseline_data = json.load(f)
            except Exception as e:
                violations.append(f"Failed to read baseline file {cfg.baseline_path}: {e}")

    if baseline_data:
        base_time = baseline_data.get("time_mean", 0.0)
        if base_time > 0 and cfg.max_time_increase_pct is not None:
            time_inc = ((summary.time_mean - base_time) / base_time) * 100.0
            if time_inc > cfg.max_time_increase_pct:
                violations.append(
                    f"Wall time increased by {time_inc:+.2f}% over baseline (max allowed: +{cfg.max_time_increase_pct:.1f}%)"
                )

        base_ipc = baseline_data.get("ipc_mean", 0.0)
        if base_ipc > 0 and summary.available and cfg.max_ipc_drop_pct is not None:
            ipc_drop = ((base_ipc - summary.ipc_mean) / base_ipc) * 100.0
            if ipc_drop > cfg.max_ipc_drop_pct:
                violations.append(
                    f"IPC dropped by {ipc_drop:.2f}% under baseline (max allowed drop: {cfg.max_ipc_drop_pct:.1f}%)"
                )

        base_miss = baseline_data.get("miss_mean", 0.0)
        if base_miss > 0 and summary.available and cfg.max_miss_increase_pct is not None:
            miss_inc = ((summary.miss_mean - base_miss) / base_miss) * 100.0
            if miss_inc > cfg.max_miss_increase_pct:
                violations.append(
                    f"LLC cache misses increased by {miss_inc:+.2f}% over baseline (max allowed: +{cfg.max_miss_increase_pct:.1f}%)"
                )

    passed = len(violations) == 0

    json_payload = {
        "passed": passed,
        "violations": violations,
        "executable": cfg.executable,
        "core_id": summary.core_id,
        "iterations": summary.iterations,
        "isolated": summary.isolated,
        "freq_locked": summary.freq_locked,
        "time_mean": summary.time_mean,
        "time_std": summary.time_std,
        "time_cv_pct": time_cv,
        "ipc_mean": summary.ipc_mean,
        "ipc_std": summary.ipc_std,
        "miss_mean": summary.miss_mean,
        "miss_std": summary.miss_std,
        "wall_times": summary.wall_times,
        "cycles": summary.cycles,
        "instructions": summary.instructions,
        "cache_misses": summary.cache_misses,
    }

    # Save baseline if requested
    if cfg.save_baseline_path:
        try:
            out_base = Path(cfg.save_baseline_path)
            out_base.parent.mkdir(parents=True, exist_ok=True)
            with open(out_base, "w") as f:
                json.dump(json_payload, f, indent=2)
        except Exception as e:
            log.error("Failed to save baseline to %s: %s", cfg.save_baseline_path, e)

    # Save JSON report if requested
    if cfg.output_json_path:
        try:
            out_json = Path(cfg.output_json_path)
            out_json.parent.mkdir(parents=True, exist_ok=True)
            with open(out_json, "w") as f:
                json.dump(json_payload, f, indent=2)
        except Exception as e:
            log.error("Failed to write json report to %s: %s", cfg.output_json_path, e)

    md_report = generate_markdown_report(cfg, summary, violations, baseline_data)

    # Save Markdown report if requested
    if cfg.output_md_path:
        try:
            out_md = Path(cfg.output_md_path)
            out_md.parent.mkdir(parents=True, exist_ok=True)
            with open(out_md, "w") as f:
                f.write(md_report)
        except Exception as e:
            log.error("Failed to write markdown report to %s: %s", cfg.output_md_path, e)

    return CiGateResult(
        passed=passed,
        violations=violations,
        summary=summary,
        baseline=baseline_data,
        markdown_report=md_report,
        data=json_payload,
    )
