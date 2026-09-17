from vanguard.core.models import MeshConnectionStatus
from vanguard.mesh.provider import NullMeshProvider


def test_null_provider_reports_not_connected_honestly():
    provider = NullMeshProvider()
    status = provider.health()
    assert status.status == MeshConnectionStatus.NOT_CONNECTED
    assert provider.list_nodes() == []
    assert provider.list_routes() == []
    assert provider.list_policies() == []
    assert provider.get_node("anything") is None
    assert provider.resolve_node("anything") is None
    assert provider.get_events() == []


def test_null_provider_refuses_enrollment_rather_than_faking_one():
    provider = NullMeshProvider()
    try:
        provider.create_enrollment("test-node")
        assert False, "expected RuntimeError"
    except RuntimeError:
        pass
