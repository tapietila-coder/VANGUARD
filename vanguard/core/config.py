"""Runtime configuration. Never hardcode secrets; everything comes from the environment."""
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    db_path: str
    api_token: str
    environment: str = "dev"
    dispatch_base_url: str = "http://127.0.0.1:8787"
    mesh_provider: str = "null"  # "null" or "netbird"
    netbird_base_url: str | None = None
    netbird_api_token: str | None = None
    node_stale_after_seconds: int = 300

    @classmethod
    def from_env(cls) -> "Settings":
        token = os.environ.get("VANGUARD_API_TOKEN", "")
        environment = os.getenv("VANGUARD_ENVIRONMENT", "dev")
        if environment != "dev" and (len(token) < 24 or token == "REPLACE_WITH_RANDOM_SECRET"):
            raise RuntimeError(
                "Set VANGUARD_API_TOKEN to a random 24+ character secret outside dev; see README"
            )
        if not token:
            # dev-only fallback so the service can boot with zero config; mutating
            # routes still require this exact token, so it is not a real auth bypass.
            token = "dev-local-only-insecure-token-000000"
        return cls(
            db_path=os.getenv("VANGUARD_DB_PATH", "./data/vanguard.db"),
            api_token=token,
            environment=environment,
            dispatch_base_url=os.getenv("VANGUARD_DISPATCH_BASE_URL", "http://127.0.0.1:8787"),
            mesh_provider=os.getenv("VANGUARD_MESH_PROVIDER", "null"),
            netbird_base_url=os.environ.get("NETBIRD_BASE_URL") or None,
            netbird_api_token=os.environ.get("NETBIRD_API_TOKEN") or None,
            node_stale_after_seconds=int(os.getenv("VANGUARD_NODE_STALE_SECONDS", "300")),
        )

    def validate(self) -> None:
        if len(self.api_token) < 24:
            raise ValueError("api_token must be at least 24 characters")
        if self.mesh_provider not in ("null", "netbird"):
            raise ValueError("mesh_provider must be 'null' or 'netbird'")
