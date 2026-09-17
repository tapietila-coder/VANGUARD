"""Deterministic readiness evaluation: given a Node and a ReadinessProfile, produce
a ReadinessResult with per-check evidence. No randomness, no network calls."""
from datetime import datetime, timezone

from ..core.db import Database, dumps, loads
from ..core.models import (
    Node,
    NodeStatus,
    ReadinessEvidence,
    ReadinessProfile,
    ReadinessResult,
    ReadinessState,
)

_STATE_RANK = {
    ReadinessState.READY: 0,
    ReadinessState.READY_WITH_WARNING: 1,
    ReadinessState.DEGRADED: 2,
    ReadinessState.NOT_READY: 3,
    ReadinessState.UNKNOWN: 4,
}


def evaluate(node: Node, profile: ReadinessProfile) -> ReadinessResult:
    evidence: list[ReadinessEvidence] = []
    worst = ReadinessState.READY

    for check in profile.checks:
        passed = True
        detail = "ok"

        if check.check_id == "recent_heartbeat":
            passed = node.status == NodeStatus.ONLINE
            detail = f"node status={node.status.value}"
        elif check.check_id == "os_build_capability":
            build_caps = {"WINDOWS_BUILD", "LINUX_BUILD", "MACOS_BUILD"}
            present = {c.value for c in node.capabilities} & build_caps
            passed = bool(present)
            detail = f"present={sorted(present)}" if present else "no OS build capability declared"
        elif check.required_capability is not None:
            passed = check.required_capability in node.capabilities
            detail = (
                f"{check.required_capability.value} declared"
                if passed
                else f"{check.required_capability.value} not declared"
            )
        else:
            passed = True
            detail = "no automated check defined; assumed pass"

        evidence.append(ReadinessEvidence(check_id=check.check_id, passed=passed, detail=detail))
        if not passed and _STATE_RANK[check.severity_if_missing] > _STATE_RANK[worst]:
            worst = check.severity_if_missing

    return ReadinessResult(
        node_id=node.node_id,
        profile_id=profile.profile_id,
        state=worst,
        evidence=evidence,
        evaluated_at=datetime.now(timezone.utc).isoformat(),
    )


class ReadinessStore:
    def __init__(self, db: Database):
        self.db = db

    def save(self, result: ReadinessResult) -> ReadinessResult:
        with self.db.cursor() as cur:
            cur.execute(
                "INSERT INTO readiness_results (node_id, profile_id, data, created_at) VALUES (?, ?, ?, ?)",
                (result.node_id, result.profile_id, dumps(result.model_dump()), result.evaluated_at),
            )
        return result

    def latest_for_node(self, node_id: str) -> list[ReadinessResult]:
        with self.db.cursor() as cur:
            cur.execute(
                "SELECT data FROM readiness_results WHERE node_id = ? ORDER BY id DESC LIMIT 20",
                (node_id,),
            )
            rows = cur.fetchall()
        return [ReadinessResult.model_validate(loads(row["data"])) for row in rows]

    def all_latest(self) -> list[ReadinessResult]:
        with self.db.cursor() as cur:
            cur.execute("SELECT data FROM readiness_results ORDER BY id DESC LIMIT 200")
            rows = cur.fetchall()
        return [ReadinessResult.model_validate(loads(row["data"])) for row in rows]
