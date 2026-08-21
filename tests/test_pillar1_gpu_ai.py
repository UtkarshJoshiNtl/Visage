"""Tests for Pillar 1: Multi-GPU Telemetry and AI Framework Workload Detection."""

from unittest.mock import MagicMock, patch

from visage.collectors.gpu import (
    EMPTY_RESULT,
    _collect_amd,
    _collect_nvidia,
    _compute_roofline,
    _ensure_gpu,
    _find_spec,
    close,
    collect as collect_gpu,
)
from visage.collectors.process import (
    _aggregate_by_name,
    collect as collect_proc,
    detect_ai_framework,
)
from visage.widgets.gpu import GpuWidget


class TestMultiGpuCollector:
    def test_empty_result_structure(self):
        with patch("visage.collectors.gpu._ensure_gpu", return_value=False), \
             patch("visage.collectors.gpu._devices", []):
            res = collect_gpu()
            assert res["available"] is False
            assert res["gpu_count"] == 0
            assert res["gpus"] == []
            assert res["pcie_tx_bytes_sec"] == 0.0

    def test_multi_gpu_nvidia_collection(self):
        mock_dev0 = {
            "index": 0,
            "handle": MagicMock(),
            "name": "NVIDIA H100 80GB HBM3",
            "sm_count": 132,
            "spec": _find_spec("NVIDIA H100 80GB HBM3"),
            "core_clock_max_mhz": 1800,
            "mem_clock_max_mhz": 2600,
        }
        mock_dev1 = {
            "index": 1,
            "handle": MagicMock(),
            "name": "NVIDIA RTX 4090",
            "sm_count": 128,
            "spec": _find_spec("NVIDIA RTX 4090"),
            "core_clock_max_mhz": 2520,
            "mem_clock_max_mhz": 1313,
        }

        with patch("visage.collectors.gpu._vendor", "nvidia"), \
             patch("visage.collectors.gpu._devices", [mock_dev0, mock_dev1]), \
             patch("visage.collectors.gpu._ensure_gpu", return_value=True), \
             patch("visage.collectors.gpu._collect_nvidia") as mock_collect_nv:

            mock_collect_nv.side_effect = [
                {
                    "index": 0,
                    "name": "NVIDIA H100 80GB HBM3",
                    "sm_util": 90.0,
                    "mem_util": 75.0,
                    "power_w": 450.0,
                    "power_max_w": 700.0,
                    "clock_core_mhz": 1750,
                    "clock_mem_mhz": 2600,
                    "temp_c": 58.0,
                    "mem_used_bytes": 60 * 1024**3,
                    "mem_total_bytes": 80 * 1024**3,
                    "sm_count": 132,
                    "pcie_tx_bytes_sec": 5000000.0,
                    "pcie_rx_bytes_sec": 7000000.0,
                },
                {
                    "index": 1,
                    "name": "NVIDIA RTX 4090",
                    "sm_util": 50.0,
                    "mem_util": 30.0,
                    "power_w": 250.0,
                    "power_max_w": 450.0,
                    "clock_core_mhz": 2400,
                    "clock_mem_mhz": 1313,
                    "temp_c": 52.0,
                    "mem_used_bytes": 10 * 1024**3,
                    "mem_total_bytes": 24 * 1024**3,
                    "sm_count": 128,
                    "pcie_tx_bytes_sec": 1000000.0,
                    "pcie_rx_bytes_sec": 2000000.0,
                },
            ]

            res = collect_gpu()
            assert res["available"] is True
            assert res["vendor"] == "nvidia"
            assert res["gpu_count"] == 2
            assert len(res["gpus"]) == 2

            gpu0 = res["gpus"][0]
            assert gpu0["name"] == "NVIDIA H100 80GB HBM3"
            assert gpu0["sm_util"] == 90.0
            assert gpu0["gflops_achieved"] > 0
            assert gpu0["pcie_tx_bytes_sec"] == 5000000.0

            gpu1 = res["gpus"][1]
            assert gpu1["name"] == "NVIDIA RTX 4090"
            assert gpu1["sm_util"] == 50.0

            # Backward-compatibility top-level keys match primary GPU
            assert res["name"] == "NVIDIA H100 80GB HBM3"
            assert res["sm_util"] == 90.0

    def test_multi_gpu_widget_cycling(self):
        w = GpuWidget()
        data = {
            "available": True,
            "vendor": "nvidia",
            "gpu_count": 2,
            "gpus": [
                {
                    "index": 0,
                    "vendor": "nvidia",
                    "name": "GPU 0 - RTX 4090",
                    "sm_util": 75.0,
                    "mem_util": 60.0,
                    "power_w": 300.0,
                    "power_max_w": 450.0,
                    "clock_core_mhz": 2500,
                    "clock_mem_mhz": 1300,
                    "temp_c": 65.0,
                    "mem_used_bytes": 12000000000,
                    "mem_total_bytes": 24000000000,
                    "pcie_tx_bytes_sec": 1024000,
                    "pcie_rx_bytes_sec": 2048000,
                    "gflops_achieved": 50000.0,
                    "gflops_peak_fp32": 80000.0,
                    "gflops_peak_fp16": 160000.0,
                    "gbw_achieved": 600.0,
                    "gbw_theoretical": 1000.0,
                    "arith_intensity": 83.3,
                    "ridge_point": 80.0,
                    "bound_by": "Compute",
                },
                {
                    "index": 1,
                    "vendor": "nvidia",
                    "name": "GPU 1 - RTX 3090",
                    "sm_util": 40.0,
                    "mem_util": 20.0,
                    "power_w": 180.0,
                    "power_max_w": 350.0,
                    "clock_core_mhz": 1700,
                    "clock_mem_mhz": 1200,
                    "temp_c": 55.0,
                    "mem_used_bytes": 6000000000,
                    "mem_total_bytes": 24000000000,
                    "pcie_tx_bytes_sec": 512000,
                    "pcie_rx_bytes_sec": 1024000,
                    "gflops_achieved": 15000.0,
                    "gflops_peak_fp32": 35000.0,
                    "gflops_peak_fp16": 70000.0,
                    "gbw_achieved": 200.0,
                    "gbw_theoretical": 900.0,
                    "arith_intensity": 75.0,
                    "ridge_point": 38.8,
                    "bound_by": "Compute",
                },
            ],
        }

        w.update_data(data)
        assert w.available is True
        assert w.gpu_count == 2
        assert w.active_gpu_idx == 0
        assert w.name == "GPU 0 - RTX 4090"
        assert w.sm_util == 75.0

        # Cycle to GPU 1
        w.cycle_gpu()
        assert w.active_gpu_idx == 1
        assert w.name == "GPU 1 - RTX 3090"
        assert w.sm_util == 40.0

        # Cycle back to GPU 0
        w.cycle_gpu()
        assert w.active_gpu_idx == 0
        assert w.name == "GPU 0 - RTX 4090"


class TestAiFrameworkDetection:
    def test_vllm_detection(self):
        assert detect_ai_framework("python", "python3 -m vllm.entrypoints.openai.api_server --model llama") == "vLLM"
        assert detect_ai_framework("vllm", "vllm serve mistralai/Mistral-7B") == "vLLM"

    def test_ollama_detection(self):
        assert detect_ai_framework("ollama", "ollama serve") == "Ollama"
        assert detect_ai_framework("ollama_runner", "/usr/bin/ollama runner") == "Ollama"

    def test_pytorch_detection(self):
        assert detect_ai_framework("torchrun", "torchrun --nproc_per_node=4 train.py") == "PyTorch"
        assert detect_ai_framework("python3", "python3 train_pytorch.py --batch-size 32") == "PyTorch"

    def test_tensorrt_detection(self):
        assert detect_ai_framework("trtexec", "trtexec --onnx=model.onnx") == "TensorRT"
        assert detect_ai_framework("python", "python run_tensorrt.py") == "TensorRT"

    def test_triton_detection(self):
        assert detect_ai_framework("tritonserver", "tritonserver --model-repository=/models") == "Triton"

    def test_llama_cpp_detection(self):
        assert detect_ai_framework("llama-server", "llama-server -m model.gguf -c 4096") == "Llama.cpp"
        assert detect_ai_framework("llama-cli", "llama-cli -p 'Hello'") == "Llama.cpp"

    def test_transformers_detection(self):
        assert detect_ai_framework("text-generation-launcher", "text-generation-launcher --model-id gpt2") == "Transformers"
        assert detect_ai_framework("python", "python run_transformers.py") == "Transformers"

    def test_non_ai_process(self):
        assert detect_ai_framework("bash", "/bin/bash") is None
        assert detect_ai_framework("nginx", "nginx: master process") is None
        assert detect_ai_framework("sshd", "sshd: root@pts/0") is None

    def test_ai_filtering_and_aggregation(self):
        procs = [
            {
                "pid": 101,
                "name": "python",
                "cmdline": "python -m vllm.entrypoints.api",
                "username": "user",
                "cpu": 80.0,
                "memory": 20.0,
                "mem_rss": 1024,
                "status": "R",
                "nice": 0,
                "threads": 8,
                "start_time": 0.0,
                "ai_framework": "vLLM",
                "is_ai": True,
            },
            {
                "pid": 102,
                "name": "nginx",
                "cmdline": "nginx -g daemon off;",
                "username": "www-data",
                "cpu": 5.0,
                "memory": 1.0,
                "mem_rss": 256,
                "status": "S",
                "nice": 0,
                "threads": 2,
                "start_time": 0.0,
                "ai_framework": None,
                "is_ai": False,
            }
        ]

        agg = _aggregate_by_name(procs, top_n=10, sort_by="cpu", sort_reverse=True)
        assert len(agg) == 2
        vllm_group = [g for g in agg if g["name"] == "python"][0]
        assert vllm_group["ai_framework"] == "vLLM"
        assert vllm_group["is_ai"] is True
