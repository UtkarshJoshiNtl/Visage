"""GPU metrics collector — NVIDIA (pynvml) and AMD (amdsmi).

Provides SM utilisation, memory bandwidth utilisation, power, clocks,
temperature, and roofline analysis (achieved FLOP/s vs. bandwidth).

.. note::
   Roofline FLOP/s and bandwidth are estimates computed from
   SM/memory utilisation × theoretical peak. They are not hardware
   instruction counters. Suitable for at-a-glance bottleneck
   identification, not precise profiling.

Gracefully falls back to ``{"available": False}`` when neither library
is installed or no supported GPU is found — zero-crash guarantee.
"""

import re
import time
from typing import Any

GPU_SPECS: list[tuple[str, dict[str, Any]]] = [
    # ── NVIDIA ──────────────────────────────────────────────────
    (r"(?i)\bAda\b|RTX 40\d+|L40|L4",
     {"flops_fp32": 256, "flops_fp16": 512, "bus_width": 384}),
    (r"(?i)\bHopper\b|H100|H200|B100|B200",
     {"flops_fp32": 256, "flops_fp16": 512, "bus_width": 5120}),
    (r"(?i)\bAmpere\b|A100|A30|A40|A10|A16|RTX 30\d+|A2",
     {"flops_fp32": 128, "flops_fp16": 256, "bus_width": 5120}),
    (r"(?i)\bTuring\b|T4|RTX 20\d+|Quadro RTX|TU\d{3}",
     {"flops_fp32": 128, "flops_fp16": 256, "bus_width": 256}),
    (r"(?i)\bVolta\b|V100|GV100",
     {"flops_fp32": 128, "flops_fp16": 256, "bus_width": 4096}),
    (r"(?i)\bPascal\b|P100|P40|GTX 10\d+|GP\d{3}",
     {"flops_fp32": 128, "flops_fp16": 256, "bus_width": 4096}),
    # ── AMD ────────────────────────────────────────────────────
    (r"(?i)\bMI300|MI350",
     {"flops_fp32": 256, "flops_fp16": 1024, "bus_width": 8192}),
    (r"(?i)\bMI250",
     {"flops_fp32": 128, "flops_fp16": 512, "bus_width": 4096}),
    (r"(?i)\bMI100|MI50|MI60",
     {"flops_fp32": 128, "flops_fp16": 256, "bus_width": 4096}),
    (r"(?i)\bRadeon.*RX 79|7900|7800|7700",
     {"flops_fp32": 256, "flops_fp16": 512, "bus_width": 384}),
    (r"(?i)\bRadeon.*RX 69|6900|6800|6700",
     {"flops_fp32": 128, "flops_fp16": 256, "bus_width": 256}),
]

DEFAULT_SPEC: dict[str, Any] = {"flops_fp32": 128, "flops_fp16": 256, "bus_width": 256}

_vendor: str | None = None
_devices: list[dict[str, Any]] = []


def _find_spec(name: str) -> dict[str, Any]:
    for pattern, spec in GPU_SPECS:
        if re.search(pattern, name):
            return dict(spec)
    return dict(DEFAULT_SPEC)


def _ensure_gpu() -> bool:
    global _vendor, _devices

    if _vendor is not None and _devices:
        return True

    _devices = []

    # ---- NVIDIA ----
    try:
        import pynvml

        pynvml.nvmlInit()
        count = pynvml.nvmlDeviceGetCount()
        if count > 0:
            for i in range(count):
                try:
                    h = pynvml.nvmlDeviceGetHandleByIndex(i)
                    name = pynvml.nvmlDeviceGetName(h)
                    if isinstance(name, bytes):
                        name = name.decode("utf-8", errors="replace")

                    sm_count = 0
                    try:
                        attrs = pynvml.nvmlDeviceGetAttributes(h)
                        sm_count = attrs.multiProcessorCount
                    except Exception:
                        pass

                    try:
                        cmax = pynvml.nvmlDeviceGetMaxClockInfo(h, pynvml.NVML_CLOCK_GRAPHICS)
                    except Exception:
                        cmax = 0
                    try:
                        mmax = pynvml.nvmlDeviceGetMaxClockInfo(h, pynvml.NVML_CLOCK_MEM)
                    except Exception:
                        mmax = 0

                    _devices.append({
                        "index": i,
                        "handle": h,
                        "name": str(name),
                        "sm_count": sm_count,
                        "spec": _find_spec(str(name)),
                        "core_clock_max_mhz": cmax,
                        "mem_clock_max_mhz": mmax,
                    })
                except Exception:
                    continue

            if _devices:
                _vendor = "nvidia"
                return True
    except Exception:
        pass

    # ---- AMD ----
    try:
        import amdsmi

        amdsmi.amdsmi_init()
        handles = amdsmi.amdsmi_get_processor_handles()
        if handles:
            for i, h in enumerate(handles):
                try:
                    name = amdsmi.amdsmi_get_gpu_device_name(h)
                    if isinstance(name, bytes):
                        name = name.decode("utf-8", errors="replace")
                    _devices.append({
                        "index": i,
                        "handle": h,
                        "name": str(name),
                        "sm_count": 0,
                        "spec": _find_spec(str(name)),
                        "core_clock_max_mhz": 0.0,
                        "mem_clock_max_mhz": 0.0,
                    })
                except Exception:
                    continue

            if _devices:
                _vendor = "amd"
                return True
            else:
                amdsmi.amdsmi_shutdown()
                return False
    except Exception:
        pass

    return False


def _collect_nvidia(dev_info: dict[str, Any]) -> dict[str, Any]:
    import pynvml

    h = dev_info["handle"]
    name = dev_info["name"]
    sm_count = dev_info["sm_count"]

    try:
        util = pynvml.nvmlDeviceGetUtilizationRates(h)
        sm_util = float(util.gpu)
        mem_util = float(util.memory)
    except Exception:
        sm_util = 0.0
        mem_util = 0.0

    try:
        power_w = pynvml.nvmlDeviceGetPowerUsage(h) / 1000.0
    except Exception:
        power_w = 0.0
    try:
        power_max_w = pynvml.nvmlDeviceGetPowerManagementLimit(h) / 1000.0
    except Exception:
        power_max_w = 0.0

    try:
        clock_core = pynvml.nvmlDeviceGetClockInfo(h, pynvml.NVML_CLOCK_GRAPHICS)
    except Exception:
        clock_core = 0
    try:
        clock_mem = pynvml.nvmlDeviceGetClockInfo(h, pynvml.NVML_CLOCK_MEM)
    except Exception:
        clock_mem = 0

    try:
        temp = pynvml.nvmlDeviceGetTemperature(h, pynvml.NVML_TEMPERATURE_GPU)
    except Exception:
        temp = 0

    try:
        mem_info = pynvml.nvmlDeviceGetMemoryInfo(h)
        mem_used = mem_info.used
        mem_total = mem_info.total
    except Exception:
        mem_used = 0
        mem_total = 0

    pcie_tx_bytes = 0.0
    pcie_rx_bytes = 0.0
    try:
        pcie_tx_kb = pynvml.nvmlDeviceGetPcieThroughput(h, pynvml.NVML_PCIE_UTIL_TX_BYTES)
        pcie_rx_kb = pynvml.nvmlDeviceGetPcieThroughput(h, pynvml.NVML_PCIE_UTIL_RX_BYTES)
        pcie_tx_bytes = float(pcie_tx_kb * 1024)
        pcie_rx_bytes = float(pcie_rx_kb * 1024)
    except Exception:
        pass

    return {
        "index": dev_info.get("index", 0),
        "name": name,
        "sm_util": sm_util,
        "mem_util": mem_util,
        "power_w": power_w,
        "power_max_w": power_max_w,
        "clock_core_mhz": clock_core,
        "clock_mem_mhz": clock_mem,
        "temp_c": temp,
        "mem_used_bytes": mem_used,
        "mem_total_bytes": mem_total,
        "sm_count": sm_count,
        "pcie_tx_bytes_sec": pcie_tx_bytes,
        "pcie_rx_bytes_sec": pcie_rx_bytes,
    }


def _collect_amd(dev_info: dict[str, Any]) -> dict[str, Any]:
    import amdsmi

    h = dev_info["handle"]
    name = dev_info["name"]
    sm_count = dev_info["sm_count"]

    try:
        activity = amdsmi.amdsmi_get_gpu_activity(h)
        sm_util = float(getattr(activity, "gfx_activity", 0))
        mem_util = float(getattr(activity, "mem_activity", 0))
    except Exception:
        sm_util = 0.0
        mem_util = 0.0

    try:
        pwr = amdsmi.amdsmi_get_power_info(h)
        power_w = float(getattr(pwr, "current_socket_power", 0))
        power_max_w = float(getattr(pwr, "max_socket_power", 0))
        if power_max_w <= 0:
            power_max_w = float(getattr(pwr, "average_socket_power", 0))
    except Exception:
        power_w = 0.0
        power_max_w = 0.0

    clock_core = 0
    clock_mem = 0
    try:
        od = amdsmi.amdsmi_get_gpu_od_volt_info(h)
        if hasattr(od, "curr_sclk"):
            clock_core = od.curr_sclk
        if hasattr(od, "curr_mclk"):
            clock_mem = od.curr_mclk
    except Exception:
        pass

    try:
        temp = amdsmi.amdsmi_get_temp_metric(h, 0)
    except Exception:
        temp = 0

    try:
        mem_info = amdsmi.amdsmi_get_gpu_memory_usage(h)
        mem_used = mem_info.get("used", 0)
        mem_total = mem_info.get("total", 0)
    except Exception:
        mem_used = 0
        mem_total = 0

    return {
        "index": dev_info.get("index", 0),
        "name": name,
        "sm_util": sm_util,
        "mem_util": mem_util,
        "power_w": power_w,
        "power_max_w": power_max_w,
        "clock_core_mhz": clock_core,
        "clock_mem_mhz": clock_mem,
        "temp_c": temp,
        "mem_used_bytes": mem_used,
        "mem_total_bytes": mem_total,
        "sm_count": sm_count,
        "pcie_tx_bytes_sec": 0.0,
        "pcie_rx_bytes_sec": 0.0,
    }


def _compute_roofline(data: dict[str, Any], spec: dict[str, Any] | None = None) -> dict[str, Any]:
    if spec is None:
        spec = _find_spec(data.get("name", ""))
    clock_core = data.get("clock_core_mhz", 0)
    clock_mem = data.get("clock_mem_mhz", 0)
    sm_util = data.get("sm_util", 0.0)
    mem_util = data.get("mem_util", 0.0)
    sm_count = data.get("sm_count", 0)
    bus_width = spec.get("bus_width", 256)

    if sm_count == 0 or clock_core == 0 or clock_mem == 0:
        return {
            "gflops_peak_fp32": 0.0,
            "gflops_peak_fp16": 0.0,
            "gflops_achieved": 0.0,
            "gbw_theoretical": 0.0,
            "gbw_achieved": 0.0,
            "arith_intensity": 0.0,
            "ridge_point": 0.0,
            "bound_by": "Idle",
        }

    bus_bytes = bus_width // 8

    gflops_peak_fp32 = sm_count * (clock_core / 1000.0) * spec["flops_fp32"]
    gflops_peak_fp16 = sm_count * (clock_core / 1000.0) * spec["flops_fp16"]
    gflops_achieved = gflops_peak_fp32 * (sm_util / 100.0)

    gbw_theoretical = clock_mem * bus_bytes * 2 / 1000.0  # DDR factor 2
    gbw_achieved = gbw_theoretical * (mem_util / 100.0)

    if gbw_achieved > 0:
        arith_intensity = gflops_achieved / gbw_achieved
    else:
        arith_intensity = 0.0

    if gbw_theoretical > 0:
        ridge_point = gflops_peak_fp32 / gbw_theoretical
    else:
        ridge_point = 0.0

    if sm_util < 5 and mem_util < 5:
        bound_by = "Idle"
    elif arith_intensity > ridge_point and ridge_point > 0:
        bound_by = "Compute"
    else:
        bound_by = "Memory"

    return {
        "gflops_peak_fp32": gflops_peak_fp32,
        "gflops_peak_fp16": gflops_peak_fp16,
        "gflops_achieved": gflops_achieved,
        "gbw_theoretical": gbw_theoretical,
        "gbw_achieved": gbw_achieved,
        "arith_intensity": arith_intensity,
        "ridge_point": ridge_point,
        "bound_by": bound_by,
    }


EMPTY_RESULT: dict[str, Any] = {
    "available": False,
    "vendor": None,
    "name": "",
    "gpu_count": 0,
    "gpus": [],
    "sm_util": 0.0,
    "mem_util": 0.0,
    "power_w": 0.0,
    "power_max_w": 0.0,
    "clock_core_mhz": 0.0,
    "clock_mem_mhz": 0.0,
    "temp_c": 0.0,
    "mem_used_bytes": 0,
    "mem_total_bytes": 0,
    "sm_count": 0,
    "pcie_tx_bytes_sec": 0.0,
    "pcie_rx_bytes_sec": 0.0,
    "gflops_peak_fp32": 0.0,
    "gflops_peak_fp16": 0.0,
    "gflops_achieved": 0.0,
    "gbw_theoretical": 0.0,
    "gbw_achieved": 0.0,
    "arith_intensity": 0.0,
    "ridge_point": 0.0,
    "bound_by": "",
    "roofline_method": "",
}


def collect() -> dict[str, Any]:
    """Collect GPU metrics and compute roofline data for all detected GPUs.

    Returns
    -------
    dict with keys documented in EMPTY_RESULT above, plus a ``gpus`` list
    containing per-device data. Top-level values represent the primary GPU
    (or aggregate) for backward compatibility.
    ``available`` is ``False`` when no GPU or library is accessible.
    """
    if not _ensure_gpu() or not _devices:
        return dict(EMPTY_RESULT)

    gpus_data: list[dict[str, Any]] = []

    for dev in _devices:
        try:
            if _vendor == "nvidia":
                raw = _collect_nvidia(dev)
            else:
                raw = _collect_amd(dev)
            spec = dev.get("spec") or _find_spec(dev.get("name", ""))
            roofline = _compute_roofline(raw, spec)
            card_data = {
                "vendor": _vendor,
                **raw,
                **roofline,
                "roofline_method": "SM_util × theoretical_peak (estimate)",
            }
            gpus_data.append(card_data)
        except Exception:
            continue

    if not gpus_data:
        return dict(EMPTY_RESULT)

    primary = gpus_data[0]

    return {
        "available": True,
        "vendor": _vendor,
        "gpu_count": len(gpus_data),
        "gpus": gpus_data,
        **primary,
    }


def close() -> None:
    global _vendor, _devices
    if _vendor == "nvidia":
        try:
            import pynvml
            pynvml.nvmlShutdown()
        except Exception:
            pass
    elif _vendor == "amd":
        try:
            import amdsmi
            amdsmi.amdsmi_shutdown()
        except Exception:
            pass
    _vendor = None
    _devices = []
