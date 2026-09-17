from vanguard.core.db import Database
from vanguard.core.models import ServiceKind, ServiceRegister
from vanguard.service_map.registry import ServiceRegistry, resolveService


def test_register_and_resolve(tmp_path):
    db = Database(str(tmp_path / "svc.db"))
    reg = ServiceRegistry(db)
    reg.register(ServiceRegister(
        service_id="dispatch", name="D27HQ Dispatch", kind=ServiceKind.HTTP_API,
        base_url="http://127.0.0.1:8787", health_path="/health",
    ))
    by_id = resolveService(reg, "dispatch")
    assert by_id is not None
    assert by_id.name == "D27HQ Dispatch"

    by_name = resolveService(reg, "D27HQ Dispatch")
    assert by_name is not None
    assert by_name.service_id == "dispatch"


def test_resolve_missing_returns_none_not_fake(tmp_path):
    db = Database(str(tmp_path / "svc2.db"))
    reg = ServiceRegistry(db)
    assert resolveService(reg, "nonexistent") is None
