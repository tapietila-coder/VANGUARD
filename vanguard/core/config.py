"""Runtime configuration. Never hardcode secrets; everything comes from the environment."""
import os
from dataclasses import dataclass
from pathlib import Path


def _default_dispatch_dir() -> str:
    """Sibling-project layout on this machine: NCTIAPP/VANGUARD and
    NCTIAPP/Dispatch/D27HQ_DISPATCH live next to each other. Computed relative
    to this file's own location so it isn't tied to one absolute path."""
    return str(Path(__file__).resolve().parents[3] / "Dispatch" / "D27HQ_DISPATCH")


def _default_dispatch_python(dispatch_dir: str) -> str:
    if os.name == "nt":
        return str(Path(dispatch_dir) / ".venv" / "Scripts" / "python.exe")
    return str(Path(dispatch_dir) / ".venv" / "bin" / "python")


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
    # Service Control: where the real local Dispatch process lives and which
    # interpreter runs it. Left blank by default on directly-constructed
    # Settings (e.g. in tests) so no managed process is auto-registered unless
    # from_env() (or the caller) explicitly supplies real paths.
    dispatch_dir: str = ""
    dispatch_python: str = ""

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
        dispatch_dir = os.getenv("VANGUARD_DISPATCH_DIR", "") or _default_dispatch_dir()
        dispatch_python = os.getenv("VANGUARD_DISPATCH_PYTHON", "") or _default_dispatch_python(dispatch_dir)
        return cls(
            db_path=os.getenv("VANGUARD_DB_PATH", "./data/vanguard.db"),
            api_token=token,
            environment=environment,
            dispatch_base_url=os.getenv("VANGUARD_DISPATCH_BASE_URL", "http://127.0.0.1:8787"),
            mesh_provider=os.getenv("VANGUARD_MESH_PROVIDER", "null"),
            netbird_base_url=os.environ.get("NETBIRD_BASE_URL") or None,
            netbird_api_token=os.environ.get("NETBIRD_API_TOKEN") or None,
            node_stale_after_seconds=int(os.getenv("VANGUARD_NODE_STALE_SECONDS", "300")),
            dispatch_dir=dispatch_dir,
            dispatch_python=dispatch_python,
        )

    def validate(self) -> None:
        if len(self.api_token) < 24:
            raise ValueError("api_token must be at least 24 characters")
        if self.mesh_provider not in ("null", "netbird"):
            raise ValueError("mesh_provider must be 'null' or 'netbird'")
