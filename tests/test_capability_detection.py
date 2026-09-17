from vanguard.core.models import Capability, NodeLocality
from vanguard.nodeops.detect import detect_local_node


def test_detect_local_node_shape():
    reg = detect_local_node("this-machine")
    assert reg.node_id == "this-machine"
    assert reg.locality == NodeLocality.LOCAL
    assert Capability.PYTHON_RUNTIME in reg.capabilities
    assert reg.hostname
    assert reg.os_name
    # never claims GPU facts it did not actually detect
    assert reg.gpu_model is None
    assert reg.gpu_vram_mb is None
