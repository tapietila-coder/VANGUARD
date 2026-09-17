"""Local-machine hardware/OS/GPU detection. Never queries remote hosts.

Uses only the Python standard library, plus `psutil` when installed (optional
dependency — see pyproject `[project.optional-dependencies].detect`). GPU
detection is best-effort: without psutil/pynvml there is no portable stdlib way
to read VRAM or GPU model, so those fields are left None rather than guessed.
"""
from __future__ import annotations

import platform
import socket

from ..core.models import Capability, NodeLocality, NodeRegister

try:
    import psutil  # type: ignore
except ImportError:  # pragma: no cover - exercised in envs without psutil
    psutil = None


def detect_local_node(node_id: str) -> NodeRegister:
    hostname = socket.gethostname()
    os_name = platform.system() or "unknown"
    os_version = platform.version() or ""
    architecture = platform.machine() or ""
    cpu_model = platform.processor() or ""

    cpu_cores_logical = 0
    memory_total_mb = 0
    if psutil is not None:
        cpu_cores_logical = psutil.cpu_count(logical=True) or 0
        memory_total_mb = int(psutil.virtual_memory().total / (1024 * 1024))
    else:
        import os as _os

        cpu_cores_logical = _os.cpu_count() or 0
        # No stdlib-portable way to read total memory without psutil; left at 0.

    capabilities: list[Capability] = [Capability.PYTHON_RUNTIME]
    if os_name == "Windows":
        capabilities.append(Capability.WINDOWS_BUILD)
    elif os_name == "Linux":
        capabilities.append(Capability.LINUX_BUILD)
    elif os_name == "Darwin":
        capabilities.append(Capability.MACOS_BUILD)
    if cpu_cores_logical >= 16:
        capabilities.append(Capability.HIGH_CORE_COUNT)
    if memory_total_mb >= 32 * 1024:
        capabilities.append(Capability.HIGH_MEMORY)

    # Docker/GPU/CUDA detection is intentionally NOT attempted here beyond what's
    # cheaply and honestly verifiable from stdlib/psutil; a node operator can set
    # those capabilities explicitly via the API when known to be true.

    return NodeRegister(
        node_id=node_id,
        hostname=hostname,
        os_name=os_name,
        os_version=os_version,
        architecture=architecture,
        cpu_model=cpu_model,
        cpu_cores_logical=cpu_cores_logical,
        memory_total_mb=memory_total_mb,
        gpu_model=None,
        gpu_vram_mb=None,
        capabilities=capabilities,
        locality=NodeLocality.LOCAL,
        notes="detected via vanguard.nodeops.detect (stdlib" + ("+psutil" if psutil else ", no psutil") + ")",
    )
