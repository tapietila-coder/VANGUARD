"""Built-in readiness profiles. Deterministic, no invented checks against
integrations that don't exist yet — those checks always evaluate to UNKNOWN."""
from ..core.models import Capability, ReadinessCheckSpec, ReadinessProfile, ReadinessState

D27_CONTROL_HOST = ReadinessProfile(
    profile_id="D27_CONTROL_HOST",
    name="D27 Control Host",
    description="Minimum bar for a machine acting as a local control/coordination host.",
    checks=[
        ReadinessCheckSpec(
            check_id="python_runtime",
            description="Python runtime capability present",
            required_capability=Capability.PYTHON_RUNTIME,
            severity_if_missing=ReadinessState.NOT_READY,
        ),
        ReadinessCheckSpec(
            check_id="os_build_capability",
            description="A recognized OS build capability (Windows/Linux/macOS) is present",
            required_capability=None,
            severity_if_missing=ReadinessState.NOT_READY,
        ),
        ReadinessCheckSpec(
            check_id="recent_heartbeat",
            description="Node has reported within the configured stale window",
            required_capability=None,
            severity_if_missing=ReadinessState.DEGRADED,
        ),
    ],
)

CLASSIFIED_GPU = ReadinessProfile(
    profile_id="CLASSIFIED_GPU",
    name="CLASSIFIED GPU Worker",
    description="Bar for a node volunteering for GPU inference workloads.",
    checks=[
        ReadinessCheckSpec(
            check_id="gpu_inference_capability",
            description="GPU_INFERENCE capability declared",
            required_capability=Capability.GPU_INFERENCE,
            severity_if_missing=ReadinessState.NOT_READY,
        ),
        ReadinessCheckSpec(
            check_id="cuda_capability",
            description="CUDA capability declared",
            required_capability=Capability.CUDA,
            severity_if_missing=ReadinessState.READY_WITH_WARNING,
        ),
        ReadinessCheckSpec(
            check_id="high_memory",
            description="HIGH_MEMORY capability declared",
            required_capability=Capability.HIGH_MEMORY,
            severity_if_missing=ReadinessState.READY_WITH_WARNING,
        ),
        ReadinessCheckSpec(
            check_id="recent_heartbeat",
            description="Node has reported within the configured stale window",
            required_capability=None,
            severity_if_missing=ReadinessState.DEGRADED,
        ),
    ],
)

GENERAL_WORKER = ReadinessProfile(
    profile_id="GENERAL_WORKER",
    name="General Worker",
    description="Minimum bar for any node accepting general local work.",
    checks=[
        ReadinessCheckSpec(
            check_id="python_runtime",
            description="Python runtime capability present",
            required_capability=Capability.PYTHON_RUNTIME,
            severity_if_missing=ReadinessState.NOT_READY,
        ),
        ReadinessCheckSpec(
            check_id="recent_heartbeat",
            description="Node has reported within the configured stale window",
            required_capability=None,
            severity_if_missing=ReadinessState.READY_WITH_WARNING,
        ),
    ],
)

BUILTIN_PROFILES: dict[str, ReadinessProfile] = {
    p.profile_id: p for p in (D27_CONTROL_HOST, CLASSIFIED_GPU, GENERAL_WORKER)
}
