"""Process tracing — event-driven process lifecycle monitoring.

Provides:
- ``create_tracer()`` — returns a started tracer (eBPF via BCC, or /proc fallback)
- ``EbpfTracer`` — kernel-tracepoint-based (requires python3-bpfcc + CAP_BPF)
- ``ProcessTracer`` — /proc polling fallback (no deps, works everywhere)
"""

from visage.tracing.tracer import EbpfTracer, ProcessTracer, create_tracer

__all__ = ["EbpfTracer", "ProcessTracer", "create_tracer"]
