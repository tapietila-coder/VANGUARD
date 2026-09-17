from vanguard.core.db import Database
from vanguard.core.models import Capability, NodeLocality, NodeRegister, NodeStatus
from vanguard.nodeops.inventory import NodeInventory


def test_register_and_get(tmp_path):
    db = Database(str(tmp_path / "t.db"))
    inv = NodeInventory(db)
    body = NodeRegister(
        node_id="local-1", hostname="desktop-1", os_name="Windows",
        capabilities=[Capability.PYTHON_RUNTIME, Capability.WINDOWS_BUILD],
        locality=NodeLocality.LOCAL,
    )
    node = inv.register(body)
    assert node.status == NodeStatus.ONLINE
    fetched = inv.get("local-1")
    assert fetched is not None
    assert fetched.hostname == "desktop-1"
    assert Capability.WINDOWS_BUILD in fetched.capabilities


def test_list_and_touch(tmp_path):
    db = Database(str(tmp_path / "t2.db"))
    inv = NodeInventory(db)
    inv.register(NodeRegister(node_id="a", hostname="h", os_name="Linux"))
    inv.register(NodeRegister(node_id="b", hostname="h2", os_name="Linux"))
    assert {n.node_id for n in inv.list()} == {"a", "b"}
    touched = inv.touch("a")
    assert touched is not None
    assert inv.touch("does-not-exist") is None


def test_stale_status(tmp_path):
    db = Database(str(tmp_path / "t3.db"))
    inv = NodeInventory(db, stale_after_seconds=0)
    inv.register(NodeRegister(node_id="c", hostname="h", os_name="Linux"))
    node = inv.get("c")
    # with a 0-second stale window, any elapsed time marks it stale or offline
    assert node.status in (NodeStatus.STALE, NodeStatus.OFFLINE)
