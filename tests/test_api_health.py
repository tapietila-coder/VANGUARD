def test_health(client):
    resp = client.get("/api/v1/vanguard/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["mode"] == "single-node-local"


def test_readiness_route_requires_no_auth_but_node_route_requires_token(client, auth_headers):
    # read-only list routes work with no auth
    assert client.get("/api/v1/vanguard/nodes").status_code == 200
    assert client.get("/api/v1/vanguard/services").status_code == 200

    # mutating route rejects missing/garbage tokens
    unauth = client.post("/api/v1/vanguard/nodes", json={
        "node_id": "n1", "hostname": "h", "os_name": "Linux",
    })
    assert unauth.status_code == 401

    ok = client.post(
        "/api/v1/vanguard/nodes",
        json={"node_id": "n1", "hostname": "h", "os_name": "Linux"},
        headers=auth_headers,
    )
    assert ok.status_code == 201
