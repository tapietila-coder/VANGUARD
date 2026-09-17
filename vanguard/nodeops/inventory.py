"""SQLite-backed node inventory: registration, lookup, status/last_seen tracking."""
from datetime import datetime, timezone

from ..core.db import Database, dumps, loads
from ..core.models import Node, NodeRegister, NodeStatus


class NodeInventory:
    def __init__(self, db: Database, stale_after_seconds: int = 300):
        self.db = db
        self.stale_after_seconds = stale_after_seconds

    def register(self, body: NodeRegister) -> Node:
        now = datetime.now(timezone.utc).isoformat()
        existing = self.get(body.node_id)
        registered_at = existing.registered_at if existing else now
        node = Node(
            node_id=body.node_id,
            hostname=body.hostname,
            os_name=body.os_name,
            os_version=body.os_version,
            architecture=body.architecture,
            cpu_model=body.cpu_model,
            cpu_cores_logical=body.cpu_cores_logical,
            memory_total_mb=body.memory_total_mb,
            gpu_model=body.gpu_model,
            gpu_vram_mb=body.gpu_vram_mb,
            capabilities=body.capabilities,
            locality=body.locality,
            status=NodeStatus.ONLINE,
            last_seen=now,
            registered_at=registered_at,
            notes=body.notes,
        )
        with self.db.cursor() as cur:
            cur.execute(
                "INSERT INTO nodes (node_id, data, updated_at) VALUES (?, ?, ?) "
                "ON CONFLICT(node_id) DO UPDATE SET data=excluded.data, updated_at=excluded.updated_at",
                (node.node_id, dumps(node.model_dump()), now),
            )
        return node

    def _status_for(self, node: Node) -> NodeStatus:
        try:
            last_seen = datetime.fromisoformat(node.last_seen)
        except ValueError:
            return NodeStatus.UNKNOWN
        if last_seen.tzinfo is None:
            last_seen = last_seen.replace(tzinfo=timezone.utc)
        age = (datetime.now(timezone.utc) - last_seen).total_seconds()
        if age > self.stale_after_seconds * 3:
            return NodeStatus.OFFLINE
        if age > self.stale_after_seconds:
            return NodeStatus.STALE
        return NodeStatus.ONLINE

    def get(self, node_id: str) -> Node | None:
        with self.db.cursor() as cur:
            cur.execute("SELECT data FROM nodes WHERE node_id = ?", (node_id,))
            row = cur.fetchone()
        if not row:
            return None
        node = Node.model_validate(loads(row["data"]))
        return node.model_copy(update={"status": self._status_for(node)})

    def list(self) -> list[Node]:
        with self.db.cursor() as cur:
            cur.execute("SELECT data FROM nodes ORDER BY node_id")
            rows = cur.fetchall()
        out = []
        for row in rows:
            node = Node.model_validate(loads(row["data"]))
            out.append(node.model_copy(update={"status": self._status_for(node)}))
        return out

    def touch(self, node_id: str) -> Node | None:
        """Update last_seen without changing hardware facts (a lightweight heartbeat)."""
        node = self.get(node_id)
        if not node:
            return None
        now = datetime.now(timezone.utc).isoformat()
        updated = node.model_copy(update={"last_seen": now, "status": NodeStatus.ONLINE})
        with self.db.cursor() as cur:
            cur.execute(
                "UPDATE nodes SET data = ?, updated_at = ? WHERE node_id = ?",
                (dumps(updated.model_dump()), now, node_id),
            )
        return updated
