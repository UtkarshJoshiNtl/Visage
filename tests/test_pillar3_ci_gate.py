"""Tests for Pillar 3: CI/CD Performance Regression & Assertion Tooling."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from visage.runners.ci import (
    CiGateConfig,
    generate_markdown_report,
    run_ci_gate,
)
from visage.runners.isolated import BenchmarkSummary


class TestCiGate:
    def test_ci_gate_pass(self, tmp_path):
        mock_summary = BenchmarkSummary(
            iterations=5,
            returncodes=[0, 0, 0, 0, 0],
            wall_times=[0.100, 0.101, 0.099, 0.100, 0.100],
            cycles=[1000000, 1000000, 1000000, 1000000, 1000000],
            instructions=[2000000, 2000000, 2000000, 2000000, 2000000],
            cache_misses=[50, 50, 50, 50, 50],
            ipc_values=[2.0, 2.0, 2.0, 2.0, 2.0],
            ipc_mean=2.0,
            ipc_std=0.0,
            miss_mean=50.0,
            miss_std=0.0,
            time_mean=0.100,
            time_std=0.0005,
            available=True,
            isolated=False,
            freq_locked=False,
            core_id=0,
            max_sigma_pct=2.0,
        )

        out_json = str(tmp_path / "ci_out.json")
        out_md = str(tmp_path / "ci_out.md")
        save_base = str(tmp_path / "baseline.json")

        cfg = CiGateConfig(
            executable="/bin/true",
            args=[],
            core_id=0,
            iterations=5,
            max_cv_pct=2.0,
            min_ipc=1.5,
            max_time_s=1.0,
            save_baseline_path=save_base,
            output_json_path=out_json,
            output_md_path=out_md,
        )

        with patch("visage.runners.ci.run_benchmark", return_value=mock_summary):
            res = run_ci_gate(cfg)
            assert res.passed is True
            assert len(res.violations) == 0
            assert "PASSED" in res.markdown_report
            assert Path(out_json).exists()
            assert Path(out_md).exists()
            assert Path(save_base).exists()

    def test_ci_gate_exit_code_failure(self):
        mock_summary = BenchmarkSummary(
            iterations=3,
            returncodes=[0, 1, 0],
            wall_times=[0.1, 0.1, 0.1],
            time_mean=0.1,
            time_std=0.0,
            available=False,
            core_id=0,
        )

        cfg = CiGateConfig(executable="/bin/false", iterations=3)

        with patch("visage.runners.ci.run_benchmark", return_value=mock_summary):
            res = run_ci_gate(cfg)
            assert res.passed is False
            assert any("failed with returncode 1" in v for v in res.violations)
            assert "FAILED" in res.markdown_report

    def test_ci_gate_baseline_regression_detection(self, tmp_path):
        base_file = tmp_path / "baseline.json"
        base_data = {
            "time_mean": 0.100,
            "ipc_mean": 2.50,
            "miss_mean": 100.0,
        }
        base_file.write_text(json.dumps(base_data))

        # Current run: time increased by 50% (0.150 vs 0.100), IPC dropped by 40% (1.5 vs 2.5)
        mock_summary = BenchmarkSummary(
            iterations=5,
            returncodes=[0, 0, 0, 0, 0],
            wall_times=[0.150, 0.150, 0.150, 0.150, 0.150],
            cycles=[1000000, 1000000, 1000000, 1000000, 1000000],
            instructions=[1500000, 1500000, 1500000, 1500000, 1500000],
            cache_misses=[200, 200, 200, 200, 200],
            ipc_values=[1.5, 1.5, 1.5, 1.5, 1.5],
            ipc_mean=1.5,
            ipc_std=0.0,
            miss_mean=200.0,
            miss_std=0.0,
            time_mean=0.150,
            time_std=0.0,
            available=True,
            core_id=0,
        )

        cfg = CiGateConfig(
            executable="/bin/my_app",
            iterations=5,
            baseline_path=str(base_file),
            max_ipc_drop_pct=10.0,
            max_time_increase_pct=10.0,
            max_miss_increase_pct=20.0,
        )

        with patch("visage.runners.ci.run_benchmark", return_value=mock_summary):
            res = run_ci_gate(cfg)
            assert res.passed is False
            assert len(res.violations) == 3
            assert any("Wall time increased" in v for v in res.violations)
            assert any("IPC dropped" in v for v in res.violations)
            assert any("cache misses increased" in v for v in res.violations)

    def test_markdown_report_formatting(self):
        summary = BenchmarkSummary(
            iterations=10,
            returncodes=[0] * 10,
            wall_times=[0.05] * 10,
            time_mean=0.05,
            time_std=0.0001,
            ipc_mean=2.2,
            ipc_std=0.01,
            miss_mean=120.0,
            miss_std=2.0,
            available=True,
            core_id=2,
            isolated=True,
            freq_locked=True,
        )
        cfg = CiGateConfig(executable="./my_app", core_id=2, iterations=10)
        report = generate_markdown_report(cfg, summary, violations=[])
        assert "Visage Performance Gate" in report
        assert "PASSED" in report
        assert "Wall Time" in report
        assert "Instructions per Cycle (IPC)" in report
        assert "LLC Cache Misses" in report
        assert "cpuset v2" in report
