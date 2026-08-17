import pytest
from fastapi.testclient import TestClient
from api.main import app

client = TestClient(app)

def test_api_health_endpoint():
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "redis_connected" in data

def test_api_incidents_endpoint():
    response = client.get("/api/incidents?limit=10")
    assert response.status_code == 200
    assert isinstance(response.json(), list)

def test_api_graph_endpoint():
    response = client.get("/api/graph")
    assert response.status_code == 200
    data = response.json()
    assert "nodes" in data
    assert "edges" in data
