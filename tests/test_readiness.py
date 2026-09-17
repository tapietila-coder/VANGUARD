from vanguard.core.models import Capability, Node, NodeLocality, NodeStatus
from vanguard.readiness.engine import evaluate
from vanguard.readiness.profiles import CLASSIFIED_GPU, D27_CONTROL_HOST, GENERAL_WORKER


def _node(**overrides):
    base = dict(
        node_id="n1", hostname="h", os_name="Linux",
        capabilities=[Capability.PYTHON_RUNTIME, Capability.LINUX_BUILD],
        locality=NodeLocality.LOCAL, status=NodeStatus.ONLINE,
    )
    base.update(overrides)
    return Node(**base)


def test_general_worker_ready():
    result = evaluate(_node(), GENERAL_WORKER)
    assert result.state.value == "READY"


def test_control_host_not_ready_without_build_capability():
    node = _node(capabilities=[Capability.PYTHON_RUNTIME])
    result = evaluate(node, D27_CONTROL_HOST)
    assert result.state.value == "NOT_READY"


def test_classified_gpu_not_ready_without_gpu_capability():
    result = evaluate(_node(), CLASSIFIED_GPU)
    assert result.state.value == "NOT_READY"


def test_classified_gpu_ready_with_warning():
    node = _node(capabilities=[
        Capability.PYTHON_RUNTIME, Capability.GPU_INFERENCE,
    ])
    result = evaluate(node, CLASSIFIED_GPU)
    assert result.state.value == "READY_WITH_WARNING"


def test_degraded_when_stale():
    node = _node(status=NodeStatus.STALE)
    result = evaluate(node, GENERAL_WORKER)
    assert result.state.value == "READY_WITH_WARNING"
