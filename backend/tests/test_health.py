def test_health(test_client):
    r = test_client.get("/api/v1/health")
    assert r.status_code == 200
    assert r.json()["ok"] is True
