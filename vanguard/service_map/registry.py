"""Service registry: SQLite-backed, no hardcoded services. resolveService(name) is
the one lookup function everything else should call."""
from datetime import datetime, timezone

from ..core.db import Database, dumps, loads
from ..core.models import Service, ServiceRegister


class ServiceRegistry:
    def __init__(self, db: Database):
        self.db = db

    def register(self, body: ServiceRegister) -> Service:
        now = datetime.now(timezone.utc).isoformat()
        existing = self.get(body.service_id)
        registered_at = existing.registered_at if existing else now
        service = Service(
            service_id=body.service_id,
            name=body.name,
            kind=body.kind,
            node_id=body.node_id,
            base_url=body.base_url,
            health_path=body.health_path,
            owner=body.owner,
            description=body.description,
            registered_at=registered_at,
            updated_at=now,
        )
        with self.db.cursor() as cur:
            cur.execute(
                "INSERT INTO services (service_id, data, updated_at) VALUES (?, ?, ?) "
                "ON CONFLICT(service_id) DO UPDATE SET data=excluded.data, updated_at=excluded.updated_at",
                (service.service_id, dumps(service.model_dump()), now),
            )
        return service

    def get(self, service_id: str) -> Service | None:
        with self.db.cursor() as cur:
            cur.execute("SELECT data FROM services WHERE service_id = ?", (service_id,))
            row = cur.fetchone()
        return Service.model_validate(loads(row["data"])) if row else None

    def list(self) -> list[Service]:
        with self.db.cursor() as cur:
            cur.execute("SELECT data FROM services ORDER BY service_id")
            rows = cur.fetchall()
        return [Service.model_validate(loads(row["data"])) for row in rows]

    def resolve_service(self, name: str) -> Service | None:
        """Resolve a service by service_id first, falling back to an exact name match.
        Returns None (not a fabricated placeholder) when nothing is registered."""
        by_id = self.get(name)
        if by_id:
            return by_id
        for service in self.list():
            if service.name == name:
                return service
        return None


def resolveService(registry: ServiceRegistry, name: str) -> Service | None:
    """camelCase alias matching the spec's naming for the resolver entry point."""
    return registry.resolve_service(name)
